# hp-remote-upgrade-apply.ps1 -- host half of the remote upgrade
# procedure on Windows. A signed job stages a release zip in its work
# directory (the one place a confined job can write that persists)
# and leaves a trigger file beside it. This applier, fired every
# minute by the HomingPigeonRemoteUpgrade scheduled task, re-verifies
# the staged zip against a freshly fetched SHA384SUMS before it swaps
# anything, then stops the runner task, runs the release's own
# installer, and starts the runner again. Same contract as the Linux
# applier (hp-remote-upgrade-apply); only the service control, the
# archive tool and the hash tool differ.
#
# Install once, from an elevated PowerShell:
#   Copy-Item hp-remote-upgrade-apply.ps1 C:\ProgramData\homing-pigeon\
#   schtasks /Create /TN HomingPigeonRemoteUpgrade /SC MINUTE /MO 1 `
#     /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProgramData\homing-pigeon\hp-remote-upgrade-apply.ps1" /RU SYSTEM
$ErrorActionPreference = "Stop"
$Home2 = Join-Path $env:USERPROFILE ".homing-pigeon"
if (-not (Test-Path $Home2)) { $Home2 = "C:\ProgramData\homing-pigeon" }
$Work = Join-Path $Home2 "work"
$Log = Join-Path $Home2 "remote-upgrade-applier.log"
function Log($m) { Add-Content -Path $Log -Value $m }
Log "=== applier $(Get-Date -Format o)"
$payload = Get-ChildItem -Path $Work -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName "remote-upgrade" } |
    Where-Object { Test-Path (Join-Path $_ "trigger") } |
    Sort-Object { (Get-Item $_).LastWriteTime } -Descending |
    Select-Object -First 1
if (-not $payload) { Log "no triggered payload"; exit 0 }
Remove-Item (Join-Path $payload "trigger") -Force
function Fail($m) {
    Set-Content -Path (Join-Path $payload "outcome.txt") -Value "FAILED: $m"
    Log "applier FAILED: $m"
    exit 0
}
$zip = Get-ChildItem -Path $payload -Filter "homing-pigeon-windows-*-*.zip" |
    Select-Object -First 1
if (-not $zip) { Fail "no zip staged" }
if ($zip.Name -notmatch "^homing-pigeon-windows-.+-(.+)\.zip$") {
    Fail "cannot read the version from $($zip.Name)"
}
$ver = $Matches[1]
try {
    $sums = (Invoke-WebRequest -UseBasicParsing `
        "https://github.com/Pigeon-Home/homing-pigeon/releases/download/v$ver/SHA384SUMS").Content
    if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
} catch { Fail "cannot fetch SHA384SUMS for v$ver" }
$line = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($zip.Name) } |
    Select-Object -First 1)
if (-not $line) { Fail "no sums line for $($zip.Name)" }
$want = ($line -split "\s+")[0].ToLower()
$got = (Get-FileHash -Algorithm SHA384 $zip.FullName).Hash.ToLower()
if ($got -ne $want) { Fail "staged zip fails the fresh SHA384SUMS check" }
$ex = Join-Path $Home2 ("extract-" + [guid]::NewGuid().ToString("N"))
Expand-Archive -Path $zip.FullName -DestinationPath $ex
$dir = Get-ChildItem -Path $ex -Directory -Recurse |
    Where-Object { Test-Path (Join-Path $_.FullName "install.exe") } |
    Select-Object -First 1
if (-not $dir) { Fail "no release directory in the zip" }
$cfgPath = Join-Path $Home2 "config.json"
$profileBefore = $null
if (Test-Path $cfgPath) {
    $profileBefore = (Get-Content $cfgPath -Raw | ConvertFrom-Json).profile
}
# The running runner holds its own program file open, and replacing
# an executing file fails. Stop the runner task before the install;
# if the install fails, start it again on the previous version so a
# bad upgrade never leaves the box without its runner.
schtasks /End /TN HomingPigeon | Out-Null
taskkill /F /IM homing-pigeon.exe 2>$null | Out-Null
for ($i = 0; $i -lt 20; $i++) {
    if (-not (Get-Process -Name "homing-pigeon" -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds 1
}
try {
    $p = Start-Process -FilePath (Join-Path $dir.FullName "install.exe") `
        -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) { throw "installer exited $($p.ExitCode)" }
    Log "applier: install ok"
} catch {
    schtasks /Run /TN HomingPigeon | Out-Null
    Fail "the installer failed (runner restarted on the previous version)"
}
if (Test-Path $cfgPath) {
    $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
    if ($profileBefore -and $cfg.profile -ne $profileBefore) {
        $cfg.profile = $profileBefore
        $cfg | ConvertTo-Json -Depth 20 | Set-Content $cfgPath
        Log "applier: restored profile $profileBefore"
    }
}
schtasks /Run /TN HomingPigeon | Out-Null
Start-Sleep -Seconds 5
$v = (& (Join-Path $Home2 "homing-pigeon.exe") --version | Select-Object -First 1)
Set-Content -Path (Join-Path $payload "outcome.txt") -Value "upgraded: $v"
Log "applier done: $v"
