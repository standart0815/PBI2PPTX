; Inno Setup script: installs the PyInstaller folder dist\PBI2PPTX for the current user only,
; so no administrator rights are needed. Built by packaging/build_windows.ps1 or the Release workflow:
;   iscc /DAppVersion=0.1.0 packaging\windows\pbi2pptx.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Keep this AppId forever: Windows uses it to recognise updates and the uninstaller.
AppId={{167D3CEC-B68C-4D36-A9F1-958A82977320}
AppName=PBI2PPTX
AppVersion={#AppVersion}
AppVerName=PBI2PPTX {#AppVersion}
DefaultDirName={localappdata}\Programs\PBI2PPTX
DefaultGroupName=PBI2PPTX
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=PBI2PPTX-{#AppVersion}-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\PBI2PPTX.exe
; The app may be running in the tray during an update or uninstall.
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\PBI2PPTX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PBI2PPTX"; Filename: "{app}\PBI2PPTX.exe"
Name: "{group}\{cm:UninstallProgram,PBI2PPTX}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\PBI2PPTX"; Filename: "{app}\PBI2PPTX.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PBI2PPTX.exe"; Description: "{cm:LaunchProgram,PBI2PPTX}"; Flags: nowait postinstall skipifsilent
