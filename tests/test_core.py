"""Unit tests for the pure logic (no network, no GUI). Run: python -m unittest discover tests"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from claude_usage import fmt, updates
from claude_usage.config import load_config, save_credentials, save_preferences
from claude_usage.i18n import STRINGS, tr
from claude_usage.insights import AlertTracker, pace_pct, poll_delay, seconds_to_limit
from claude_usage.localstats import LocalStats, parse_log, short_model
from claude_usage.model import Limit, Usage
from claude_usage.sources import (UsageError, _retry_after, parse_credentials, parse_usage, plan_label)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def iso(delta: timedelta) -> str:
    return (NOW + delta).isoformat()


class ParseUsageTests(unittest.TestCase):
    def test_top_level_fields(self):
        data = {"five_hour": {"utilization": 25.0, "resets_at": "2026-10-09T17:20:00+00:00"},
                "seven_day": {"utilization": 24.0, "resets_at": "2026-10-12T20:00:00+00:00"},
                "seven_day_sonnet": {"utilization": 12.0, "resets_at": "2026-10-12T20:00:00+00:00"},
                "seven_day_opus": None,
                "extra_usage": {"is_enabled": True, "utilization": 3.5}}
        usage = parse_usage(data, "oauth", "Max 5x")
        self.assertEqual((usage.session.pct, usage.weekly.pct), (25.0, 24.0))
        self.assertEqual([m.label for m in usage.models], ["Sonnet"])
        self.assertEqual(usage.extra.pct, 3.5)
        self.assertEqual((usage.source, usage.plan), ("oauth", "Max 5x"))

    def test_falls_back_to_limits_array_and_reads_breakdown(self):
        data = {"five_hour": None, "seven_day": None,
                "limits": [{"kind": "session", "percent": 25, "resets_at": "x"},
                           {"kind": "weekly_all", "percent": 24},
                           {"kind": "weekly_scoped", "percent": 40,
                            "scope": {"model": {"display_name": "Opus"}}}],
                "seven_day_breakdown": {"rows": [{"key": "claude_code", "display_name": "Claude Code",
                                                  "percent": 75}]}}
        usage = parse_usage(data, "cookie")
        self.assertEqual((usage.session.pct, usage.weekly.pct), (25.0, 24.0))
        self.assertEqual([(m.label, m.pct) for m in usage.models], [("Opus", 40.0)])
        self.assertEqual(usage.breakdown, [("Claude Code", 75.0)])

    def test_model_listed_twice_is_deduplicated(self):
        data = {"five_hour": {"utilization": 1}, "seven_day_sonnet": {"utilization": 5},
                "limits": [{"kind": "weekly_scoped", "percent": 5,
                            "scope": {"model": {"display_name": "sonnet"}}}]}
        self.assertEqual(len(parse_usage(data).models), 1)

    def test_unusable_response_raises(self):
        for bad in ({}, {"unrelated": 1}, [], None):
            with self.assertRaises(UsageError):
                parse_usage(bad)

    def test_sub_one_percent_is_not_inflated(self):
        usage = parse_usage({"five_hour": {"utilization": 1.0}})
        self.assertEqual(usage.session.pct, 1.0)


class CredentialTests(unittest.TestCase):
    def test_parses_millisecond_expiry_and_plan(self):
        text = json.dumps({"claudeAiOauth": {"accessToken": "t", "expiresAt": 1_800_000_000_000,
                                             "subscriptionType": "max", "rateLimitTier": "default_claude_max_5x"}})
        creds = parse_credentials(text)
        self.assertEqual(creds.plan, "Max 5x")
        self.assertEqual(creds.expires_at.year, 2027)

    def test_second_expiry_and_expired_flag(self):
        creds = parse_credentials(json.dumps({"claudeAiOauth": {"accessToken": "t", "expiresAt": 1_000_000_000}}))
        self.assertTrue(creds.is_expired(NOW))
        self.assertFalse(parse_credentials(json.dumps({"claudeAiOauth": {"accessToken": "t"}})).is_expired(NOW))

    def test_invalid_input(self):
        for text in ("", "not json", "{}", json.dumps({"claudeAiOauth": {}})):
            self.assertIsNone(parse_credentials(text))

    def test_plan_label(self):
        self.assertEqual(plan_label("pro", ""), "Pro")
        self.assertEqual(plan_label("max", "default_claude_max_20x"), "Max 20x")
        self.assertEqual(plan_label("", ""), "")

    def test_retry_after(self):
        self.assertEqual(_retry_after("120"), 120)
        self.assertEqual(_retry_after("999999"), 3600)
        self.assertEqual(_retry_after("5"), 30)
        self.assertEqual(_retry_after(None), 600)
        self.assertEqual(_retry_after("garbage"), 600)


class InsightTests(unittest.TestCase):
    def session(self, pct, elapsed_hours):
        remaining = timedelta(hours=5 - elapsed_hours)
        return Limit("session", "", pct, iso(remaining), 5)

    def test_pace(self):
        self.assertAlmostEqual(pace_pct(self.session(10, 2.5), NOW), 50.0)

    def test_forecast_only_when_limit_comes_before_reset(self):
        self.assertAlmostEqual(seconds_to_limit(self.session(50, 1), NOW) / 3600, 1.0)
        self.assertIsNone(seconds_to_limit(self.session(30, 4), NOW))       # slow burn, resets first
        self.assertIsNone(seconds_to_limit(self.session(10, 1), NOW))       # too little usage to extrapolate
        self.assertIsNone(seconds_to_limit(self.session(60, 0.05), NOW))    # too little history
        self.assertEqual(seconds_to_limit(self.session(100, 1), NOW), 0.0)

    def test_poll_delay(self):
        usage = Usage(session=self.session(10, 4.99))
        self.assertAlmostEqual(poll_delay(300, usage, NOW), 41.6, delta=1)   # lands just after the reset
        self.assertEqual(poll_delay(300, None, NOW, jitter=10), 310)
        self.assertEqual(poll_delay(300, usage, NOW, backoff=900), 900)      # back-off wins
        self.assertEqual(poll_delay(10, None, NOW), 15)


class AlertTests(unittest.TestCase):
    def usage(self, pct, resets="r1"):
        return Usage(session=Limit("session", "", pct, resets, 5))

    def kinds(self, tracker, pct, resets="r1"):
        return [(a.kind, a.value) for a in tracker.check(self.usage(pct, resets), NOW)]

    def test_threshold_fires_once_and_not_at_startup(self):
        tracker = AlertTracker((80, 90, 100))
        self.assertEqual(self.kinds(tracker, 85), [])              # first reading only seeds the state
        self.assertEqual(self.kinds(tracker, 86), [])
        self.assertEqual(self.kinds(tracker, 91), [("threshold", 90)])
        self.assertEqual(self.kinds(tracker, 92), [])

    def test_hysteresis_prevents_flapping(self):
        tracker = AlertTracker((80,))
        self.kinds(tracker, 10)
        self.assertEqual(self.kinds(tracker, 81), [("threshold", 80)])
        self.assertEqual(self.kinds(tracker, 78), [])              # still within the hysteresis band
        self.assertEqual(self.kinds(tracker, 81), [])
        self.assertEqual(self.kinds(tracker, 70), [])              # falls well below: re-armed
        self.assertEqual(self.kinds(tracker, 82), [("threshold", 80)])

    def test_reset_notification_and_rearm(self):
        tracker = AlertTracker((80,))
        self.kinds(tracker, 10)
        self.kinds(tracker, 85)
        self.assertEqual(self.kinds(tracker, 2, resets="r2"), [("reset", 0.0)])
        self.assertEqual(self.kinds(tracker, 83, resets="r2"), [("threshold", 80)])

    def test_forecast_once_per_window(self):
        tracker = AlertTracker((80, 90, 100))
        limit = Limit("session", "", 50, iso(timedelta(hours=4)), 5)
        kinds = lambda: [a.kind for a in tracker.check(Usage(session=limit), NOW)]
        self.assertEqual(kinds(), ["forecast"])
        self.assertEqual(kinds(), [])
        later = Limit("session", "", 50, iso(timedelta(hours=4)).replace("2026", "2027"), 5)   # next window
        self.assertEqual([a.kind for a in tracker.check(Usage(session=later), NOW + timedelta(days=365))],
                         ["forecast"])


class LocalStatsTests(unittest.TestCase):
    def write(self, path: Path, rows: list):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")

    def assistant(self, msg_id, tokens_out, when, model="claude-sonnet-4-6-20260101"):
        return {"type": "assistant", "timestamp": when.isoformat(), "sessionId": "s1",
                "message": {"id": msg_id, "model": model,
                            "usage": {"input_tokens": 10, "output_tokens": tokens_out,
                                      "cache_creation_input_tokens": 5, "cache_read_input_tokens": 99999}}}

    def test_short_model(self):
        self.assertEqual(short_model("claude-sonnet-4-6-20260101"), "Sonnet 4.6")
        self.assertEqual(short_model("claude-opus-4-1"), "Opus 4.1")
        self.assertEqual(short_model(None), "?")

    def test_repeated_message_ids_keep_the_largest_count(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a.jsonl"
            self.write(path, [self.assistant("m1", 4, NOW), self.assistant("m1", 500, NOW)])
            parsed = parse_log(path)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed["m1"][2], 10 + 500 + 5)       # cache reads excluded

    def test_scan_today_and_week_across_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            local_now = NOW.astimezone()
            self.write(root / "p1" / "a.jsonl", [self.assistant("m1", 100, local_now),
                                                 self.assistant("old", 1000, local_now - timedelta(days=3))])
            self.write(root / "p2" / "b.jsonl", [self.assistant("m1", 100, local_now)])   # same id: counted once
            stats = LocalStats(root).scan(local_now)
            self.assertEqual(stats.today, 115)
            self.assertEqual(stats.week, 115 + 1015)
            self.assertEqual(stats.top_models[0][0], "Sonnet 4.6")

    def test_missing_directory(self):
        self.assertIsNone(LocalStats(Path("does-not-exist")).scan(NOW))


class ConfigTests(unittest.TestCase):
    def test_credentials_roundtrip_is_encrypted(self):
        with tempfile.TemporaryDirectory() as folder:
            config, settings = Path(folder) / "config.json", Path(folder) / "settings.json"
            save_credentials({"auth_mode": "cookie", "org_id": "org", "session_key": "sk-secret",
                              "cf_clearance": ""}, config)
            self.assertNotIn("sk-secret", config.read_text(encoding="utf-8"))
            save_preferences({"language": "hu", "notifications": False, "interval_seconds": 120,
                              "icon_mode": "session"}, settings)
            cfg = load_config(config, settings)
            self.assertEqual((cfg["session_key"], cfg["org_id"], cfg["auth_mode"]), ("sk-secret", "org", "cookie"))
            self.assertEqual((cfg["language"], cfg["notifications"], cfg["interval_seconds"], cfg["icon_mode"]),
                             ("hu", False, 120, "session"))

    def test_plain_legacy_config_still_loads_and_bad_values_are_fixed(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            config.write_text(json.dumps({"org_id": "o", "session_key": "plain", "interval_seconds": 5,
                                          "auth_mode": "nonsense"}), encoding="utf-8")
            cfg = load_config(config, Path(folder) / "none.json")
            self.assertEqual(cfg["session_key"], "plain")
            self.assertEqual((cfg["auth_mode"], cfg["interval_seconds"]), ("auto", 60))


class TextTests(unittest.TestCase):
    def test_both_languages_define_the_same_keys(self):
        self.assertEqual(set(STRINGS["hu"]), set(STRINGS["en"]))

    def test_every_string_formats_with_its_placeholders(self):
        sample = dict(p=1, t=1, e=1, s=1, w=1, m=1, at=1, today=1, week=1, src=1, name=1, v=1, n=1, a=1, y=1,
                      plan="")
        for lang, table in STRINGS.items():
            for key, value in table.items():
                if isinstance(value, str):
                    value.format(**sample)

    def test_fallback_for_unknown_language(self):
        self.assertEqual(tr("xx", "quit"), "Quit")

    def test_formatting_helpers(self):
        self.assertEqual(fmt.duration(3 * 3600 + 5 * 60), "3h 05m")
        self.assertEqual(fmt.duration(2 * 86400 + 3 * 3600), "2d 3h")
        self.assertEqual(fmt.duration(12 * 60, ("n", "ó", "p")), "12p")
        self.assertEqual(fmt.tokens(1_250_000), "1.25M")
        self.assertEqual(fmt.tokens(48_000), "48.0K")
        self.assertIsNone(fmt.parse_iso("nonsense"))

    def test_version_comparison(self):
        self.assertTrue(updates.is_newer("1.0.1", "1.0.0"))
        self.assertTrue(updates.is_newer("v2.0", "1.9.9"))
        self.assertFalse(updates.is_newer("1.0.0", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
