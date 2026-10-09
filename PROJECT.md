# Claude Usage Tray – projektleírás

> Ez a fájl a fejlesztéshez készült (VS Code / Claude Code). A cél: a meglévő Python-programból **futtatható (.exe) Windows-alkalmazást** készíteni. Ha Claude Code-dal dolgozol, átnevezheted `CLAUDE.md`-re, hogy automatikusan beolvassa.

## 1. Mit csinál a program

Windows 11 tálcaikon (system tray), ami a **claude.ai** előfizetés két használati értékét mutatja, folyamatosan frissítve:

- **Current session** (5 órás ablak) → API: `five_hour.utilization`
- **This week** (7 napos ablak) → API: `seven_day.utilization`

Megjelenítés:

- Az ikon két színes sáv: felül a session, alul a hét százaléka (`icon_mode: "both"`), vagy egyetlen szám (`"session"`). Szín: kék < 70%, narancs ≥ 70%, piros ≥ 90%, szürke „!” ha még nincs adat.
- Tooltip: `Munkamenet: 25% | Hét: 24%` / `Session: 25% | Week: 24%`
- Jobb gombos menü: session sor + visszaállási idő, heti sor + visszaállási idő, frissítés ideje (hiba esetén hibaüzenet is), **Frissítés most**, **Usage oldal megnyitása**, **Nyelv / Language** (rádiógombok: Magyar / English), **Kilépés**.
- Kétnyelvű (hu/en) felület, a választás a `settings.json`-ban marad meg. Első indításkor a Windows UI nyelvét követi (magyar → `hu`, különben `en`).
- Hiba esetén az utolsó jó érték marad látható, a tooltip jelzi a hibát.

## 2. Fájlok

| Fájl | Szerep | Git |
|---|---|---|
| `claude_usage_tray.py` | a teljes program (egyetlen fájl) | igen |
| `config.example.json` | konfigurációs sablon | igen |
| `config.json` | **valódi konfig, benne a `sessionKey` süti – titok!** | **soha** |
| `settings.json` | menüből választott nyelv (automatikusan jön létre) | nem |
| `requirements.txt` | `pystray`, `pillow`, `curl_cffi` | igen |
| `README.md` | felhasználói leírás (HU + EN) | igen |
| `PROJECT.md` | ez a fejlesztői leírás | igen |
| `.gitignore` | kizárja a `config.json`-t, `settings.json`-t, build kimenetet | igen |

## 3. Adatforrás (nem hivatalos, nem dokumentált!)

A claude.ai webes Usage oldala ezt a belső végpontot hívja:

```
GET https://claude.ai/api/organizations/<org_id>/usage
```

Hitelesítés: a böngésző `sessionKey` sütije (`sk-ant-sid02-...`). Opcionálisan `cf_clearance` is kellhet, ha a Cloudflare blokkol (HTTP 403).

A program a `curl_cffi` csomaggal, `impersonate="chrome"` beállítással hívja (böngésző TLS-ujjlenyomat, mert a sima `requests`-et a Cloudflare valószínűleg blokkolná).

Fontosabb fejlécek: `accept: */*`, `content-type: application/json`, `anthropic-client-platform: web_claude_ai`, `referer: https://claude.ai/settings/usage`.

### A válasz (releváns része, lerövidítve)

```json
{
  "five_hour": { "utilization": 25.0, "resets_at": "2026-10-09T17:20:00.606556+00:00" },
  "seven_day": { "utilization": 24.0, "resets_at": "2026-10-12T20:00:00.606575+00:00" },
  "limits": [
    { "kind": "session",    "group": "session", "percent": 25, "resets_at": "...", "is_active": true },
    { "kind": "weekly_all", "group": "weekly",  "percent": 24, "resets_at": "...", "is_active": false }
  ],
  "seven_day_breakdown": { "rows": [ { "key": "claude_code", "display_name": "Claude Code", "percent": 75 } ] }
}
```

- A `fetch_usage()` először a `five_hour` / `seven_day` objektumot nézi, ha ott `null`, akkor a `limits[]` tömbből veszi (`kind == "session"` / `"weekly_all"`).
- Az `utilization` lebegőpontos (`25.0`), a program egészre kerekít.
- Az időpontok UTC-ben jönnek (`resets_at`), a program helyi időre alakítja.
- Sok más mező `null` (pl. `seven_day_opus`); a `seven_day_breakdown` a heti használat megoszlását adja (Claude Code / Chats / Cowork) – jelenleg nem használt, jövőbeli bővítési lehetőség.

## 4. Konfiguráció (`config.json`)

| Mező | Jelentés | Alapérték |
|---|---|---|
| `org_id` | szervezeti azonosító (UUID az API URL-ből) | – |
| `session_key` | `sessionKey` süti értéke | – |
| `cf_clearance` | opcionális Cloudflare süti | `""` |
| `interval_seconds` | frissítési időköz (min. 15) | `60` |
| `icon_mode` | `"both"` vagy `"session"` | `"both"` |
| `language` | opcionális `"hu"`/`"en"` (a `settings.json` felülírja) | rendszernyelv |

Nyelvválasztás sorrendje: `settings.json` → `config.json["language"]` → Windows UI nyelv.

## 5. Felépítés (`claude_usage_tray.py`)

- **`STRINGS` / `LANGS`** – a teljes UI szövegkészlete `hu` és `en` nyelven (kulcsok mindkét nyelven azonosak). Új nyelv: új kulcs a két szótárban + a `LANGS`-ban.
- **`detect_system_language()`, `load_language()`, `save_language()`** – nyelv felismerése és mentése.
- **`set_autostart(enable)`** – a Windows Registry `HKCU\...\Run` kulcsába ír (`--autostart` / `--no-autostart` parancssori kapcsoló).
- **`UsageError(key, arg)`** – fordítható hiba: a hiba **kulcsként** tárolódik, így nyelvváltáskor azonnal újrafordítódik a menüben.
- **`fetch_usage(cfg)`** – a lekérés és a JSON-értelmezés, `{"s", "s_reset", "w", "w_reset"}` szótárat ad vissza.
- **`make_icon(state, mode)`** – a 64×64-es ikon rajzolása Pillow-val (Arial Bold / Segoe UI Bold betűtípus a Windows-ból, fallback: Pillow alapfont).
- **`App`** – a tálcaikon (`pystray.Icon`), a menü (hívható szövegekkel, így nyelvváltáskor újrarajzolódik), a háttérszál (`worker`: lekérés → `wake.wait(interval)`), a „Frissítés most” az `Event`-tel ébreszti a szálat.

Szálkezelés: a fő szál a `pystray` eseményhurka, a lekérés egy `daemon` szálban fut.

## 6. Fejlesztői környezet

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json   # majd töltsd ki
python claude_usage_tray.py            # konzollal, hibakereséshez
pythonw claude_usage_tray.py           # konzol nélkül
```

Minimális Python: 3.9 (a fájl elején `from __future__ import annotations` van, így a `str | None` jelölés régebbi Pythonon is működik).

## 7. FELADAT: futtatható (.exe) verzió

Cél: egy `ClaudeUsageTray.exe`, ami Python telepítése nélkül fut, tálcaikonnal, konzolablak nélkül.

### 7.1 Javasolt build (PyInstaller)

```
pip install pyinstaller
pyinstaller --onefile --noconsole --name ClaudeUsageTray ^
  --collect-all curl_cffi --hidden-import pystray._win32 ^
  --icon app.ico claude_usage_tray.py
```

- A `curl_cffi` natív könyvtárat (libcurl-impersonate) tartalmaz → `--collect-all curl_cffi` kell.
- A `pystray` a Windows-backendet dinamikusan tölti → `--hidden-import pystray._win32`.
- Ha a `--onefile` kibontása lassú vagy a víruskereső téves riasztást ad, használj `--onedir` kimenetet, és csomagold telepítővé (Inno Setup).

### 7.2 Kötelezően javítandó a kódban (frozen mód)

1. **`BASE` útvonal.** Jelenleg `Path(__file__).resolve().parent`. `--onefile` esetén ez egy ideiglenes `_MEI...` mappa → a `config.json` és `settings.json` ott nem található. Javítás:
   ```python
   BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
   ```
2. **Autostart.** A `set_autostart()` most `pythonw.exe + script` parancsot ír a Registry-be. Frozen módban csak az exe kell:
   ```python
   cmd = f'"{sys.executable}"' if getattr(sys, "frozen", False) else f'"{pyw}" "{Path(__file__).resolve()}"'
   ```
3. **Hiányzó `config.json`.** Jelenleg kivétellel leáll. Legyen barátságos kezelés (lásd 7.3).
4. **Egy példány.** Védd named mutexszel (`ctypes.windll.kernel32.CreateMutexW`), hogy ne indulhasson kétszer.

### 7.3 Ajánlott fejlesztések az exe-hez

- **Első indítás varázsló** (`tkinter` ablak): bekéri az `org_id`-t és a `sessionKey`-t, ellenőrzi egy próbalekéréssel, majd menti. Így nem kell kézzel `config.json`-t szerkeszteni.
- **A süti biztonságos tárolása**: ne sima szövegben. Lehetőségek: Windows Credential Manager (`keyring` csomag) vagy DPAPI (`win32crypt.CryptProtectData`).
- **Menüpont „Indítás a Windows-szal”** (pipálható), a `--autostart` kapcsoló helyett/mellett.
- **Frissítési időköz és ikonmód a menüből** állítható (mentés a `settings.json`-ba).
- **Értesítés** (Windows toast) 80% / 90% átlépésekor.
- **Ikon olvashatóság**: a tálcaikon 16×16–32×32 px-en jelenik meg; ellenőrizd Windows 11-en több DPI-n, szükség esetén egyszerűsítsd (nagyobb/vastagabb számok).
- **`app.ico`** az exe-hez (a tálcaikon továbbra is dinamikusan rajzolt).
- **Naplózás** fájlba (de **soha ne naplózd a sütit**), hibakereséshez.
- Opcionálisan GitHub Actions workflow, ami Windows-on buildel és a Releases alá teszi az exe-t.

## 8. Ismert korlátok és kockázatok

- A végpont **nem hivatalos és nem dokumentált**; az Anthropic bármikor megváltoztathatja. Ha a válasz szerkezete változik, a program „Ismeretlen válaszformátum” hibát jelez (`err_format`).
- A `sessionKey` idővel lejár → `HTTP 401/403`, a program „!” ikont mutat (ha még nem volt sikeres lekérés), vagy az utolsó jó értéket + hibajelzést. Megoldás: új süti beírása.
- A Cloudflare blokkolhat → `cf_clearance` süti hozzáadása; ha így sem megy, alternatíva: böngészőbővítmény, ami a bejelentkezett oldalról olvassa ki az adatot, és egy helyi (localhost) tálcaprogramnak küldi.
- A claude.ai felhasználási feltételeinek betartása a felhasználó felelőssége; a projekt **nem hivatalos**, nincs kapcsolatban az Anthropic-kal.

## 9. Biztonsági szabályok (fejlesztéshez)

- A `config.json` **soha nem kerülhet Git-be**, és exe-be sem szabad belecsomagolni a sütit.
- A sütit ne írd ki konzolra/naplóba, és hibajelentésben se szerepeljen.
- Ha egy süti kiszivárgott: Claude → Settings → Account → kijelentkezés az összes eszközről.

## 10. Kész prompt VS Code-hoz / Claude Code-hoz

```
Olvasd el a PROJECT.md-t és a claude_usage_tray.py-t. Készíts belőle futtatható
Windows exe-t PyInstallerrel a 7. fejezet szerint: javítsd a BASE útvonalat és az
autostartot frozen módra, add hozzá az egypéldányos védelmet és egy első indítási
beállító ablakot (org_id + sessionKey, próbalekéréssel), majd írj build.bat-ot, ami
létrehozza a dist\ClaudeUsageTray.exe fájlt. A sütit ne naplózd és ne csomagold az
exe-be. A felület maradjon kétnyelvű (hu/en).
```
