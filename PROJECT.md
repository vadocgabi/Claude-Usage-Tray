# Claude Usage Tray – fejlesztői leírás

Windows tálcaprogram, ami a **claude.ai** előfizetés használati korlátait mutatja. Felhasználói leírás: `README.md`. Ez a fájl a fejlesztőknek (és a Claude Code-nak) szól.

## Működés röviden

- **Adatforrások** (`claude_usage/sources.py`), mindkettő nem dokumentált, belső végpont:
  - **OAuth:** `GET https://api.anthropic.com/api/oauth/usage`, fejlécek: `Authorization: Bearer <token>`, `anthropic-beta: oauth-2025-04-20`. A token a Claude Code bejelentkezéséből jön: Windows Credential Manager (`Claude Code-credentials`), majd `~/.claude/.credentials.json` (`CLAUDE_CONFIG_DIR` felülírhatja). **A tokent csak olvassuk, soha nem frissítjük** (a forgatás kijelentkeztetné a Claude Code-ot). Lejárt tokennél nem hívunk, a felhasználó nyissa meg a Claude Code-ot.
  - **Süti:** `GET https://claude.ai/api/organizations/<org_id>/usage`, `sessionKey` sütivel, `curl_cffi` + `impersonate="chrome"` (Cloudflare miatt).
  - **Auth mód:** `auto` (OAuth, ha van, különben süti) / `oauth` / `cookie`. 429-nél nem próbáljuk a másik végpontot.
- **Egységes értelmező:** `parse_usage()` mindkét válaszból `Usage` objektumot készít (`five_hour`/`seven_day`, `seven_day_sonnet|opus`, `limits[]` `weekly_scoped`, `extra_usage`, `seven_day_breakdown`). A `utilization` már százalék, **nem szabad** „tört vagy százalék” heurisztikát bevezetni (az 1.0 = 1%).
- **Elemzés** (`insights.py`): tempó (az időablak hány %-a telt el), előrejelzés (mikor éri el a 100%-ot, ha a reset előtt), `AlertTracker` (80/90/100% küszöb, hiszterézis, ablakonként egyszer, reset-értesítés, első olvasásnál nem szól), `poll_delay` (jitter, `Retry-After` back-off, a reset utánra időzítés).
- **Helyi statisztika** (`localstats.py`): `~/.claude/projects/**/*.jsonl`, üzenet-azonosító szerinti deduplikálás (a legnagyobb tokenszám nyer), fájlonkénti gyorsítótár. Token = input + output + cache creation (cache read nélkül). Költséget szándékosan nem becslünk (az árlista elavulna).

## Fájlok

| Fájl | Szerep |
|---|---|
| `claude_usage_tray.py` | belépési pont (PyInstaller ezt építi) |
| `claude_usage/` | a program csomagja (lásd lent) |
| `tests/test_core.py` | egységtesztek (`python -m unittest discover tests`) |
| `build.bat` | tesztek + PyInstaller exe + Inno Setup telepítő + SHA256 |
| `installer.iss`, `info_hu.txt`, `info_en.txt` | Inno Setup telepítő (Program Files, HU/EN) |
| `make_icon.py` | `app.ico` + a telepítő képei (generált, nem commitoljuk) |
| `version_info.txt` | az exe verzióinformációja |
| `config.json` | **titkos**: org_id, kulcsok (DPAPI), auth mód. Soha nem kerül Git-be |

Modulok: `sources` (adatforrások, hiba: `UsageError(key, arg, retry_after)`), `model` (`Limit`, `Usage`, `Snapshot`), `insights`, `localstats`, `config` (config.json + settings.json), `dpapi`, `i18n` (HU/EN, kulcsok azonosak, ezt teszt őrzi), `fmt`, `icon`, `autostart`, `updates` (kézi frissítés-ellenőrzés), `ui_common` (design tokenek, világos/sötét, `Bar`), `ui_details` (flyout), `ui_settings`, `app` (tálca + munkaszál), `cli`.

## Konvenciók

- Hibák **kulcsként** tárolódnak (`UsageError.key`), így nyelvváltáskor újrafordíthatók. Új szöveg: mindkét nyelven, az `i18n.STRINGS`-ben.
- A tkinter ablakok **saját szálban** futnak (a főszál a `pystray`). Egyszerre egy ablak/fajta.
- Adatok az exe-nél `%APPDATA%\ClaudeUsageTray`, forrásból futtatva a projektmappa.
- pystray menüelem-visszahívások pontosan 2 paraméteresek legyenek (nem lehet alapértelmezett argumentum, zárványt használj).

## Build

```
pip install -r requirements.txt pyinstaller
build.bat        # dist\ClaudeUsageTray.exe, installer\ClaudeUsageTray-Setup-1.0.0.exe
```

Az exe-hez `--collect-all curl_cffi` és `--hidden-import pystray._win32` kell. A telepítőhöz Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

## Biztonsági szabályok

- A kulcsot és a tokent **soha** nem naplózzuk, nem írjuk ki, nem csomagoljuk az exe-be, nem commitoljuk.
- Hálózat: csak `api.anthropic.com` / `claude.ai`; `api.github.com` kizárólag a „Frissítések keresése” kattintásra.
- A projekt **nem hivatalos**, nincs kapcsolatban az Anthropic-kal.

## Ötletek a későbbi verziókhoz

Több fiók (`--config-dir`), kompakt lebegő widget, eseményparancsok (script futtatás küszöbnél), kódaláírás (SignPath Foundation), költségbecslés külön, frissíthető árlistával.
