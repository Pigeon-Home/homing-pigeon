; Homing Pigeon: the Microsoft Store route A installer (DRAFT)
; Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
;
; DRAFT. Nothing compiles this script yet, nothing is signed,
; and nothing here has been submitted anywhere. It is the
; packaging draft for the unpackaged installer route (Store
; policy 10.2.9) whose record stands in
; docs/steady/design/app-stores-design.md: that route submits
; one standalone installer .exe at a versioned address, and
; this script, compiled with Inno Setup 6, is how the tree the
; build lays out becomes that .exe.
;
; INPUT. The build-windows-onedir job in
; .github/workflows/build.yml freezes the runner and the
; install program as one-directory trees and zips them under a
; versioned top folder (homing-pigeon-windows-x86_64-onedir-
; <version>), with the example config and BUILD-PROVENANCE.json
; beside the two program folders; the zip rides the run as the
; artifact named windows-onedir-installer-input. Extract it and
; compile with its folder as SourceDir:
;
;   iscc /DAppVersion=3.17.32.3 /DSourceDir=<extracted folder> ^
;        packaging\windows\homing-pigeon.iss
;
; The output is HomingPigeon-Setup-<version>.exe. Under
; /VERYSILENT it installs without a wizard (an elevation
; prompt may still show; the route allows one), and nothing
; in this script asks a question the silent flags cannot
; answer.
;
; UNSIGNED. No signature is applied by this script, and the
; output is not signed. The route requires the installer and
; every PE file in it to carry a signature chaining to a
; Microsoft trusted root; the certificate is a purchase in
; the conductor's name, recorded as owner only in the design
; notes. Signing the compiled installer is a step of the
; route's build out, after that purchase, not of this draft.
;
; WHAT IT DOES. Lays the tree into a versioned folder
; ({autopf}\Homing Pigeon\<version>), seeds config.json from
; the example into one fixed home that no version number
; enters ({commonappdata}\Homing Pigeon\config.json, in a
; folder restricted to administrators and SYSTEM) and never
; overwrites an existing one, and registers the same startup
; task the install program registers today
; (runner/ops/install.py): the task is named HomingPigeon,
; runs at startup as SYSTEM at the HIGHEST run level, and its
; command is the installed runner exe with --config pointing
; at the config in its fixed home, quoted the way install.py
; quotes it. A wizard page names the SYSTEM choice and what
; follows from it before anything is installed. Both task
; entries are gated on the setup being finished (the
; ConfigIsSetUp check in [Code]): while the config still
; carries the example's placeholder values, the installer
; registers nothing and starts nothing, and a closing message
; tells the operator to edit the config and run this
; installer again. With a finished config the task registers
; and starts at once, as it does under install.py.
; Uninstalling deletes the task and the laid-down files; the
; seeded config stays, as it does under install.py
; --uninstall, which likewise leaves files and state behind.
;
; OPEN POINTS, recorded so they are decided before a
; submission and not discovered after one:
; - The config home question is decided (2026-11-23, with
;   the record in docs/steady/design/windows-installer-
;   hardening.md): programs stay one folder per version (an
;   upgrade leaves the previous version's folder in place;
;   UsePreviousAppDir is off, so a version always lands in
;   its own folder), and the config lives in the fixed home
;   above, so an operator's edited config.json carries
;   itself into the next version untouched. One legacy case
;   stands: an install made from this script's earlier draft
;   shape seeded config.json inside its versioned folder.
;   The operator upgrading from that shape
;   copies that file once by hand
;   into {commonappdata}\Homing Pigeon, before or after the
;   upgrade; the installer does no silent migration.
; - The store-facing identity strings below (publisher,
;   names) are placeholders of the ordinary kind until the
;   conductor's name reservation issues the real ones.
; - There are no Start Menu shortcuts: the product is a
;   machine level service, and its operator surface is the
;   install program's own commands (--check, --console,
;   --logs), which this installer lays down beside the
;   runner.

#ifndef AppVersion
  #define AppVersion "0.0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "."
#endif
#define AppName "Homing Pigeon"

[Setup]
AppId={{BBDCF95A-8537-4B25-956E-03803BB24554}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Pigeon Home
DefaultDirName={autopf}\Homing Pigeon\{#AppVersion}
UsePreviousAppDir=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
OutputBaseFilename=HomingPigeon-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\homing-pigeon\homing-pigeon.exe

[Dirs]
Name: "{commonappdata}\Homing Pigeon"; Permissions: admins-full system-full

[Files]
Source: "{#SourceDir}\homing-pigeon\*"; DestDir: "{app}\homing-pigeon"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\install\*"; DestDir: "{app}\install"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\config.example.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\BUILD-PROVENANCE.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\config.example.json"; DestDir: "{commonappdata}\Homing Pigeon"; DestName: "config.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Run]
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /TN HomingPigeon /TR ""\""{app}\homing-pigeon\homing-pigeon.exe\"" --config \""{commonappdata}\Homing Pigeon\config.json\"""" /SC ONSTART /RU SYSTEM /RL HIGHEST /F"; Flags: runhidden waituntilterminated; StatusMsg: "Registering the HomingPigeon startup task..."; Check: ConfigIsSetUp
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN HomingPigeon"; Flags: runhidden waituntilterminated; Check: ConfigIsSetUp

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN HomingPigeon /F"; Flags: runhidden waituntilterminated

[Code]
var
  SystemChoicePage: TOutputMsgWizardPage;

function ConfigFileName: String;
begin
  Result := ExpandConstant('{commonappdata}\Homing Pigeon\config.json');
end;

{ The setup counts as finished only when the config in its
  fixed home carries none of the example's placeholder
  values: the mailbox password, the shared secret, and the
  example mailbox user. The [Run] entries carry this check,
  so an unfinished setup registers and starts nothing. }
function ConfigIsSetUp: Boolean;
var
  Contents: AnsiString;
begin
  Result := False;
  if LoadStringFromFile(ConfigFileName, Contents) then
    Result := (Pos('paste-app-password-here-in-plaintext', Contents) = 0) and
              (Pos('generate-with-openssl-rand-hex-32', Contents) = 0) and
              (Pos('homing-pigeon-runner@gmail.com', Contents) = 0);
end;

procedure InitializeWizard;
begin
  SystemChoicePage := CreateOutputMsgPage(wpWelcome,
    'The startup task runs as SYSTEM',
    'What that choice means for this machine',
    'This installer can register a startup task named HomingPigeon. ' +
    'The task runs as SYSTEM, the machine account, at the highest run ' +
    'level, whether or not anyone is signed in, and it starts at every ' +
    'boot. The runner it starts can carry out signed jobs with the full ' +
    'rights of that account, so only finish the setup on a machine whose ' +
    'operator means to run it that way. Deleting the task stops it: run ' +
    'the uninstaller, or end the HomingPigeon task in Task Scheduler.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not ConfigIsSetUp) then
    MsgBox('Setup is not finished. The files are installed, but no startup task was registered, because the configuration at ' + ConfigFileName + ' still carries the example values. Edit that file with the mailbox and secret for this machine, then run this installer again to register and start the task.', mbInformation, MB_OK);
end;
