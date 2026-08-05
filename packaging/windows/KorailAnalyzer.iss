#define MyAppName "Korail Analyzer"
#define MyAppPublisher "Korail Analyzer Project"
#define MyAppExeName "KorailAnalyzer.exe"
#define MyAppVersion GetEnv("KORAIL_APP_VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "1.0.1"
#endif
#define MySourceDir "..\..\dist\KorailAnalyzer"
#define MyOutputDir "..\..\dist\installer"

[Setup]
AppId={{8CC21993-AB68-43E5-B56E-8EC49B8CF9BB6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/creno-va/korail-program
AppSupportURL=https://github.com/creno-va/korail-program/issues
AppUpdatesURL=https://github.com/creno-va/korail-program/releases
DefaultDirName={localappdata}\Programs\Korail Analyzer
DefaultGroupName=Korail Analyzer
DisableProgramGroupPage=yes
DisableWelcomePage=no
DisableReadyPage=no
ShowLanguageDialog=no
OutputDir={#MyOutputDir}
OutputBaseFilename=KorailAnalyzerSetup-{#MyAppVersion}
Compression=lzma2/fast
SolidCompression=no
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\output"
