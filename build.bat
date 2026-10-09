@echo off
rem Builds dist\ClaudeUsageTray.exe and installer\ClaudeUsageTray-Setup-1.0.0.exe (Python 3.9+ on PATH).
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m unittest discover tests || exit /b 1
python make_icon.py || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name ClaudeUsageTray ^
  --icon app.ico --version-file version_info.txt ^
  --collect-all curl_cffi --hidden-import pystray._win32 ^
  claude_usage_tray.py || exit /b 1

rem Installer (optional, needs Inno Setup 6: winget install JRSoftware.InnoSetup)
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" ("%ISCC%" installer.iss) else echo Inno Setup not found - installer skipped.

echo.
echo Checksums (SHA256):
certutil -hashfile dist\ClaudeUsageTray.exe SHA256 | findstr /v ":"
certutil -hashfile installer\ClaudeUsageTray-Setup-1.0.0.exe SHA256 | findstr /v ":"
