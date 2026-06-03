; UFX-MG インストーラー設定（Inno Setup）
; ビルド: ISCC.exe installer.iss  →  installer\UFX-MG-Setup.exe
; 事前に PyInstaller(onedir) で dist\UFX-MG\ を生成しておくこと。

#define MyAppName "UFX-MG"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "Kanunsanun"
#define MyAppExeName "UFX-MG.exe"
#define MyAppURL "https://github.com/Kanunsanun/mgufx"

[Setup]
AppId={{DE57BE10-F7D8-4FCF-80AB-AD942F8FBE39}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
; --- ユーザー単位インストール（管理者不要・UAC を出さない） ---
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; --- 出力 ---
OutputDir=installer
OutputBaseFilename=UFX-MG-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller onedir 出力をまるごと同梱
Source: "dist\UFX-MG\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
