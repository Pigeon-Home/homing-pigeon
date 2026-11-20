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
; the example and never overwrites an existing one, and
; registers the same startup task the install program
; registers today (runner/ops/install.py): the task is named
; HomingPigeon, runs at startup as SYSTEM at the HIGHEST run
; level, and its command is the installed runner exe with
; --config pointing at the seeded config, quoted the way
; install.py quotes it. The task starts at once, as it does
; under install.py. Uninstalling deletes the task and the
; laid-down files; the seeded config stays, as it does under
; install.py --uninstall, which likewise leaves files and
; state behind.
;
; OPEN POINTS, recorded so they are decided before a
; submission and not discovered after one:
; - One folder per version means an operator's edited
;   config.json does not carry itself into the next version's
;   folder, and an upgrade leaves the previous version's
;   folder in place (UsePreviousAppDir is off, so a version
;   always lands in its own folder). Whether the shipped
;   installer keeps this shape or moves the config to a fixed
;   home, the way install.py's one-home layout does, is a
;   decision for the route's build out.
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

[Files]
Source: "{#SourceDir}\homing-pigeon\*"; DestDir: "{app}\homing-pigeon"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\install\*"; DestDir: "{app}\install"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\config.example.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\BUILD-PROVENANCE.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\config.example.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Run]
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /TN HomingPigeon /TR ""\""{app}\homing-pigeon\homing-pigeon.exe\"" --config \""{app}\config.json\"""" /SC ONSTART /RU SYSTEM /RL HIGHEST /F"; Flags: runhidden waituntilterminated; StatusMsg: "Registering the HomingPigeon startup task..."
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN HomingPigeon"; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN HomingPigeon /F"; Flags: runhidden waituntilterminated
