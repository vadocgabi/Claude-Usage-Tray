; Claude Usage Tray installer (Inno Setup 6) - Vadóc Gábor, 2026
#define AppName "Claude Usage Tray"
#define AppVersion "1.0.0"
#define AppExe "ClaudeUsageTray.exe"

[Setup]
AppId={{B7C1E5A2-4F0D-4C7B-9E55-3A6D2C8F1A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Vadóc Gábor
AppPublisherURL=https://github.com/vadocgabi/claude.ai_usage_systemtray
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UsedUserAreasWarning=no
AppMutex=Local\ClaudeUsageTray_SingleInstance
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=app.ico
OutputDir=installer
OutputBaseFilename=ClaudeUsageTray-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=installer_side.bmp
WizardSmallImageFile=installer_small.bmp
DisableWelcomePage=no
DisableReadyPage=yes
ShowLanguageDialog=auto
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Vadóc Gábor
VersionInfoDescription={#AppName} Setup
VersionInfoCopyright=© 2026 Vadóc Gábor

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"; InfoBeforeFile: "info_hu.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "info_en.txt"

[Tasks]
Name: "autostart"; Description: "{cm:AutoStart}"; Flags: checkedonce
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[CustomMessages]
hungarian.AutoStart=Indítás a Windows-szal
english.AutoStart=Start with Windows
hungarian.CreateDesktopIcon=Parancsikon az asztalon
english.CreateDesktopIcon=Create a desktop shortcut

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "ClaudeUsageTray"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
