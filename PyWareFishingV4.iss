#define MyAppName "PyWare Fishing V4"
#define MyAppVersion "4.0"
#define MyAppPublisher "PyWare"
#define MyAppExeName "PyWareFishingV4.exe"

[Setup]
AppId={{C4D15A52-96B5-4A17-98E6-9A9E8D9A1234}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

PrivilegesRequired=lowest

DefaultDirName={localappdata}\Programs\PyWare Fishing V4
DefaultGroupName={#MyAppName}

OutputDir=build
OutputBaseFilename=Windows (4.0 setup)

Compression=lzma2
SolidCompression=yes

WizardStyle=modern

[Types]
Name: "full"; Description: "Full Installation"
Name: "custom"; Description: "Custom Installation"; Flags: iscustom

[Components]
Name: "configs"; Description: "Configuration Files"; Types: full custom
Name: "images"; Description: "Images"; Types: full custom
Name: "ui"; Description: "User Interface Files"; Types: full custom

[Files]

; Main executable
Source: "dist\PyWareFishingV4.exe"; DestDir: "{app}"; Flags: ignoreversion

; Configs -> AppData\Roaming
Source: "dist\configs\*"; DestDir: "{userappdata}\PyWare Fishing V4\configs"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Components: configs

; Images -> beside EXE
Source: "dist\images\*"; DestDir: "{app}\images"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Components: images

; UI -> beside EXE
Source: "dist\ui\*"; DestDir: "{app}\ui"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Components: ui

[Icons]
Name: "{group}\PyWare Fishing V4"; Filename: "{app}\PyWareFishingV4.exe"
Name: "{autodesktop}\PyWare Fishing V4"; Filename: "{app}\PyWareFishingV4.exe"

[Run]
Filename: "{app}\PyWareFishingV4.exe"; \
    Description: "Launch PyWare Fishing V4"; \
    Flags: nowait postinstall skipifsilent