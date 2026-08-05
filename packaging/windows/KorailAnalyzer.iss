#define MyAppName "Korail 지장수목 분석"
#define MyAppPublisher "Korail Analyzer Project"
#define MyAppExeName "KorailAnalyzer.exe"
#define MyAppVersion GetEnv("KORAIL_APP_VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "1.0.0"
#endif
#define MySourceDir "..\..\dist\KorailAnalyzer"
#define MyOutputDir "..\..\dist\installer"

[Setup]
AppId={{8CC21993-AB68-43E5-B56E-8EC49B8CF9BB6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Korail Analyzer
DefaultGroupName=Korail Analyzer
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename=KorailAnalyzerSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupLogging=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Korail 지장수목 분석"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Korail 지장수목 분석"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Korail 지장수목 분석}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\output"
