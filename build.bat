@echo off
rem Builds dist\ClaudeUsageTray.exe (requires Python 3.9+ on PATH)
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python make_icon.py || exit /b 1
python -m PyInstaller --noconfirm --onefile --noconsole --name ClaudeUsageTray ^
  --icon app.ico --collect-all curl_cffi --hidden-import pystray._win32 ^
  claude_usage_tray.py || exit /b 1
echo.
echo Done: dist\ClaudeUsageTray.exe

rem Installer (optional, requires Inno Setup 6: winget install JRSoftware.InnoSetup)
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" ("%ISCC%" installer.iss && echo Installer: installer\ClaudeUsageTray-Setup-1.0.0.exe) else echo Inno Setup not found - installer skipped.
