"""Platform layer, tray model and Linux helpers. These run on every OS (OS calls are patched)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_usage.system import linux
from claude_usage.tray import SEPARATOR, Item, find_default
from claude_usage.tray.sni import MenuModel, pixmaps_from_image


class LinuxSystemTests(unittest.TestCase):
    def test_config_dir_honours_xdg(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/xdg-test"}):
            self.assertEqual(linux.data_dir(), Path("/tmp/xdg-test/ClaudeUsageTray"))

    def test_language_detection(self):
        with mock.patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANGUAGE": "", "LANG": "hu_HU.UTF-8"}):
            self.assertEqual(linux.system_language(), "hu")
        with mock.patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANGUAGE": "", "LANG": "de_DE.UTF-8"}):
            self.assertEqual(linux.system_language(), "en")
        with mock.patch.dict(os.environ, {"LC_ALL": "C", "LC_MESSAGES": "", "LANGUAGE": "", "LANG": "hu_HU.UTF-8"}):
            self.assertEqual(linux.system_language(), "hu")   # 'C' says nothing, the next variable decides

    def test_secret_without_keyring_is_kept_and_roundtrips(self):
        with mock.patch.object(linux, "_keyring", return_value=None):
            stored = linux.protect("session_key", "sk-secret")
            self.assertEqual(linux.unprotect(stored), "sk-secret")
            self.assertEqual(linux.protect("x", ""), "")

    def test_secret_goes_to_the_keyring_when_available(self):
        fake = mock.Mock()
        fake.get_password.return_value = "sk-secret"
        with mock.patch.object(linux, "_keyring", return_value=fake):
            stored = linux.protect("session_key", "sk-secret")
            self.assertEqual(stored, "keyring:session_key")
            fake.set_password.assert_called_once_with("ClaudeUsageTray", "session_key", "sk-secret")
            self.assertEqual(linux.unprotect(stored), "sk-secret")

    def test_keyring_failure_falls_back_to_plain(self):
        fake = mock.Mock()
        fake.set_password.side_effect = RuntimeError("locked")
        with mock.patch.object(linux, "_keyring", return_value=fake):
            self.assertEqual(linux.protect("k", "v"), "v")

    def test_windows_dpapi_values_are_not_decryptable_here(self):
        self.assertEqual(linux.unprotect("dpapi:AQAAANCM"), "")

    def test_autostart_file_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": folder}):
            self.assertFalse(linux.autostart_enabled())
            linux.set_autostart(True, '"/opt/claude/ClaudeUsageTray"')
            self.assertTrue(linux.autostart_enabled())
            text = (Path(folder) / "autostart" / "ClaudeUsageTray.desktop").read_text(encoding="utf-8")
            self.assertIn('Exec="/opt/claude/ClaudeUsageTray"', text)
            self.assertIn("Type=Application", text)
            linux.set_autostart(False, "")
            self.assertFalse(linux.autostart_enabled())
            linux.set_autostart(False, "")      # disabling twice is harmless

    def test_work_area_from_xprop(self):
        out = "_NET_WORKAREA(CARDINAL) = 0, 27, 1920, 1053, 0, 27, 1920, 1053"
        with mock.patch.object(linux, "_run", return_value=out):
            self.assertEqual(linux.work_area(), (0, 27, 1920, 1080))

    def test_work_area_falls_back_to_the_screen(self):
        window = mock.Mock()
        window.winfo_screenwidth.return_value, window.winfo_screenheight.return_value = 1366, 768
        with mock.patch.object(linux, "_run", return_value=""):
            self.assertEqual(linux.work_area(window), (0, 0, 1366, 768))

    def test_dark_mode_detection_order(self):
        def run_with(answers):
            def fake(command, timeout=2.0):
                return answers.get(command[0], "")
            return mock.patch.object(linux, "_run", side_effect=fake)

        with run_with({"gdbus": "(<<uint32 1>>,)"}):
            self.assertTrue(linux._detect_dark())
        with run_with({"gdbus": "(<<uint32 2>>,)"}):
            self.assertFalse(linux._detect_dark())
        with run_with({"gsettings": "'prefer-dark'\n"}):
            self.assertTrue(linux._detect_dark())
        with run_with({"gsettings": "'default'\n"}):
            self.assertFalse(linux._detect_dark())
        with run_with({"kreadconfig6": "BreezeDark\n"}):
            self.assertTrue(linux._detect_dark())
        with run_with({}), mock.patch.dict(os.environ, {"GTK_THEME": "Adwaita:dark"}):
            self.assertTrue(linux._detect_dark())
        with run_with({}), mock.patch.dict(os.environ, {"GTK_THEME": ""}):
            self.assertFalse(linux._detect_dark())


class MenuModelTests(unittest.TestCase):
    def setUp(self):
        self.state = {"on": True, "mode": "a"}
        self.clicked = []
        self.items = [
            Item(lambda: "Session: 25%"),
            SEPARATOR,
            Item("Details", lambda: self.clicked.append("details"), default=True),
            Item("Notifications", lambda: None, checked=lambda: self.state["on"]),
            Item("Mode", children=[
                Item("A", lambda: None, checked=lambda: self.state["mode"] == "a", radio=True),
                Item("B_x", lambda: None, checked=lambda: self.state["mode"] == "b", radio=True)]),
            Item("Hidden", lambda: None, visible=lambda: False),
        ]
        self.model = MenuModel(self.items)

    def test_ids_are_stable_and_unique(self):
        ids = sorted(self.model._by_id)
        self.assertEqual(ids, list(range(len(ids))))
        before = {i: id(item) for i, item in self.model._by_id.items()}
        self.model.layout(0, -1)
        self.assertEqual(before, {i: id(item) for i, item in self.model._by_id.items()})

    def test_layout_structure(self):
        revision, (root_id, props, children) = self.model.layout(0, -1)
        self.assertEqual((revision, root_id), (1, 0))
        self.assertEqual(props["children-display"], ("s", "submenu"))
        self.assertEqual(len(children), len(self.items))
        signature, first = children[0]
        self.assertEqual(signature, "(ia{sv}av)")
        self.assertEqual(first[1]["label"], ("s", "Session: 25%"))
        self.assertEqual(first[1]["enabled"], ("b", False))          # informational line: no action

    def test_properties(self):
        details = self.model.properties(self.items[2])
        self.assertEqual(details["enabled"], ("b", True))
        self.assertEqual(self.model.properties(self.items[1])["type"], ("s", "separator"))
        check = self.model.properties(self.items[3])
        self.assertEqual((check["toggle-type"], check["toggle-state"]), (("s", "checkmark"), ("i", 1)))
        radio = self.model.properties(self.items[4].children[1])
        self.assertEqual((radio["toggle-type"], radio["toggle-state"]), (("s", "radio"), ("i", 0)))
        self.assertEqual(radio["label"], ("s", "B__x"))               # underscore is a mnemonic marker
        self.assertEqual(self.model.properties(self.items[5])["visible"], ("b", False))
        self.assertEqual(self.model.properties(self.items[4])["children-display"], ("s", "submenu"))

    def test_properties_are_live(self):
        self.state["on"] = False
        self.assertEqual(self.model.properties(self.items[3])["toggle-state"], ("i", 0))

    def test_depth_limits_the_tree(self):
        _, (_, _, children) = self.model.layout(0, 1)
        submenu_node = children[4][1]
        self.assertEqual(submenu_node[2], [])                        # grandchildren cut at depth 1

    def test_group_properties_and_default(self):
        ids = [i for i, it in self.model._by_id.items() if it is self.items[2]]
        group = self.model.group_properties(ids)
        self.assertEqual(group[0][0], ids[0])
        self.assertIs(find_default(self.items), self.items[2])


class PixmapTests(unittest.TestCase):
    def test_argb_network_order(self):
        from PIL import Image
        image = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
        for width, height, data in pixmaps_from_image(image, sizes=(8, 16)):
            self.assertEqual(len(data), width * height * 4)
            self.assertEqual(data[:4], bytes([255, 10, 20, 30]))      # A, R, G, B


if __name__ == "__main__":
    unittest.main()
