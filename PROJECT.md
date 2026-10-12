# Claude Usage Tray – fejlesztői leírás

Windows és Linux tálcaprogram, ami a **claude.ai** előfizetés használati korlátait mutatja. Felhasználói leírás: `README.md`. Ez a fájl a fejlesztőknek (és a Claude Code-nak) szól.

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

### Platformréteg és tálca (Windows + Linux)

- **`system/`**: minden operációs rendszer-specifikus hívás itt van, egyetlen interfész mögött (`__init__.py` dokumentálja): adatmappa, titkok védelme (`protect`/`unprotect`), natív Claude-bejelentkezés, autostart, egypéldányos zár, rendszernyelv, sötét mód, ablakstílus, munkaterület. `windows.py` (DPAPI, Credential Manager, registry, DWM), `linux.py` (XDG, keyring/Secret Service vagy `0600` fájl, `.desktop` autostart, `flock`, portal/gsettings/KDE sötét mód, `_NET_WORKAREA`), `fallback.py` (egyéb platform: az app elindul, natív funkciók nélkül).
- **`tray/`**: semleges menümodell (`Item`) és backendek. Windows: `pystray_backend.py`. Linux: `sni.py` = saját **StatusNotifierItem + com.canonical.dbusmenu** megvalósítás (jeepney), amivel GNOME (AppIndicator bővítmény), KDE, XFCE, Cinnamon, MATE, LXQt, waybar mind működik, csomagolt binárisból is (nem kell GTK/PyGObject). Választás: `linux_select.py` (SNI watcher → XEmbed (pystray `xorg`) → nincs tálca: a részletek ablak jelenik meg). Értesítés Linuxon: `notifier.py` (`org.freedesktop.Notifications`).
- A `jeepney` blokkoló kapcsolata a váratlan bejövő hívásokat **eldobja**, ha `send_and_get_reply`-ra vár: ezért az `SniTray` egyetlen saját üzenethurkot használ, minden D-Bus műveletet ez a szál végez, a többi szál csak a `_outbox`-ba tesz.
- Linuxon a részletek ablak normál ablak (a keret nélküli, fókuszvesztésre záródó flyout csak Windowson, `system.FLYOUT_BORDERLESS`).
- `--diagnose [--out FILE]`: szöveges jelentés a rendszerről (Tk, tálca, kulcstartó, bejelentkezés).

### Linux build és tesztek

- `packaging/linux/build.sh`: Debian 11 (glibc 2.31) konténerben PyInstaller `--onedir`, majd `.tar.gz` (+`install.sh`), `.deb` és AppImage. Futtatás: lásd README „Fejlesztés”.
- `tests/linux/`: `Dockerfile.ubuntu` (Xvfb, D-Bus, `snixembed` mint valódi harmadik féltől származó SNI-gazda, stalonetray, dunst, gnome-keyring), `gui_test.py` (forgatókönyvek: `sni`, `xembed`, `nowatch`, `nobus`, `firstrun`; hamis loopback OAuth-végpont a `CLAUDE_USAGE_TEST_API` környezeti változóval, csak `http://127.0.0.1:<port>` fogadható el), `distro_smoke.sh` (Ubuntu 22.04/24.04, Debian 12, Fedora 41, Arch: bináris, `.deb`, AppImage, `install.sh`), `keyring_test.sh`.
- Windowson a Linux-tesztek Dockerben futnak (`docker run -v <repo>:/src:ro ...`); Git-bashban az `MSYS_NO_PATHCONV=1` kell az `/src` útvonalakhoz.

Modulok: `sources` (adatforrások, hiba: `UsageError(key, arg, retry_after)`), `model` (`Limit`, `Usage`, `Snapshot`), `insights`, `localstats`, `config` (config.json + settings.json), `system` (OS-réteg), `tray` (tálca-backendek), `diagnose`, `i18n` (HU/EN, kulcsok azonosak, ezt teszt őrzi), `fmt`, `icon`, `autostart`, `updates` (kézi frissítés-ellenőrzés), `ui_common` (design tokenek, világos/sötét, `Bar`), `ui_details` (flyout), `ui_settings`, `app` (alkalmazás + munkaszál), `cli`.

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
