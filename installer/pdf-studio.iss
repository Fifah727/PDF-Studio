; Script Inno Setup — installateur Windows de PDF Studio
; Appelé par le workflow GitHub avec : /DAppExe=<nom de l'exe> /DAppVersion=<version>

#define AppName "PDF Studio"
#ifndef AppExe
  #define AppExe "pdf_studio.exe"
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
; Ne changez jamais cet identifiant : il permet les mises à jour et la désinstallation.
AppId={{B394DACD-74BC-428E-A36B-A04CA8CE1326}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Fifaliana Sarobidy
DefaultDirName={autopf}\PDF Studio
DefaultGroupName=PDF Studio
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=PDF-Studio-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Installation pour l'utilisateur courant, sans demande d'administrateur.
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; Flags: unchecked

[Files]
Source: "..\build\windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PDF Studio"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\PDF Studio"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer PDF Studio"; Flags: nowait postinstall skipifsilent
