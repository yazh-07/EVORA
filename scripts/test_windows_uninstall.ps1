# Real Inno install/uninstall with the actual desktop/updater and synthetic data.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot/..").Path
$scratch = Join-Path $env:RUNNER_TEMP ('evora-uninstall-' + [guid]::NewGuid())
$fixture = Join-Path $scratch 'package'
$install = Join-Path $scratch 'installed'
$profile = Join-Path $scratch 'profile'
$originalAppData = $env:APPDATA
$process = $null
function Require-Success($message) { if ($LASTEXITCODE -ne 0) { throw $message } }
try {
  New-Item -ItemType Directory -Force "$fixture/desktop", "$fixture/installer", "$fixture/dist/evora", "$profile/EVORA/data" | Out-Null
  Copy-Item "$repo/installer/setup.iss" "$fixture/installer/setup.iss"
  Copy-Item "$repo/desktop/icon.ico" "$fixture/desktop/icon.ico"
  go -C "$repo/desktop" build -o "$fixture/desktop/evora-workstation.exe" .
  Require-Success 'Desktop build failed'
  go -C "$repo/desktop" build -o "$fixture/desktop/evora-updater.exe" ./cmd/updater
  Require-Success 'Updater build failed'
  go -C "$repo/desktop" build -o "$fixture/dist/evora/evora.exe" ./testdata/uninstall-backend
  Require-Success 'Fixture backend build failed'
  python "$repo/scripts/build_incremental.py" --backend "$fixture/dist/evora" --desktop "$fixture/desktop/evora-workstation.exe" --helper "$fixture/desktop/evora-updater.exe" --icon "$fixture/desktop/icon.ico" --output "$fixture/dist"
  Require-Success 'Fixture inventory failed'
  $iscc = "${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe"
  if (!(Test-Path $iscc)) { choco install innosetup --no-progress -y; Require-Success 'Inno Setup install failed' }
  & $iscc "$fixture/installer/setup.iss"
  Require-Success 'Installer compile failed'
  $setup = Start-Process "$fixture/dist/EVORA-Setup-Windows-x64.exe" -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=`"$install`"",'/TASKS=desktopicon,startupicon',"/LOG=`"$scratch/install.log`"") -Wait -PassThru
  if ($setup.ExitCode -ne 0) { throw "Install failed: $($setup.ExitCode)" }
  # Simulate a new library introduced by an incremental update, absent in Inno's log.
  Set-Content "$fixture/dist/evora/added-by-update.dll" 'synthetic update library'
  python "$repo/scripts/build_incremental.py" --backend "$fixture/dist/evora" --desktop "$fixture/desktop/evora-workstation.exe" --helper "$fixture/desktop/evora-updater.exe" --icon "$fixture/desktop/icon.ico" --output "$fixture/dist"
  Require-Success 'Updated inventory failed'
  Copy-Item "$fixture/dist/evora/added-by-update.dll" "$install/backend/added-by-update.dll"
  Copy-Item "$fixture/dist/EVORA-Update-Windows-x64.json" "$install/evora-install.json" -Force
  Set-Content "$install/backend/user-notes.txt" 'preserve these notes'
  Set-Content "$profile/EVORA/data/cases.sqlite3" 'synthetic case database'
  $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $probe.Start(); $port = $probe.LocalEndpoint.Port; $probe.Stop()
  @{mode='browser';port=$port;ai_provider='ollama'} | ConvertTo-Json | Set-Content "$profile/EVORA/config.json"
  $env:APPDATA = $profile
  $process = Start-Process "$install/EVORA.exe" -PassThru
  $deadline = (Get-Date).AddSeconds(30)
  $ready = $false
  while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) { throw 'Desktop exited before uninstall test' }
    $backendLog = "$profile/EVORA/backend.log"
    try { $response = Invoke-WebRequest "http://127.0.0.1:$port/" -TimeoutSec 1 -UseBasicParsing; if ($response.Content -eq 'synthetic backend ready') { $ready=$true;break } } catch {}
    Start-Sleep -Milliseconds 100
  }
  if (!$ready) { throw 'Synthetic backend did not start' }
  $uninstall = Start-Process "$install/unins000.exe" -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=`"$scratch/uninstall.log`"") -Wait -PassThru
  if ($uninstall.ExitCode -ne 0) { throw "Uninstall failed: $($uninstall.ExitCode)" }
  if (!$process.WaitForExit(10000)) { throw 'Uninstall left the desktop running' }
  foreach ($name in @('EVORA.exe','evora-updater.exe','backend/evora.exe','backend/added-by-update.dll','evora-install.json')) {
    if (Test-Path "$install/$name") { throw "Uninstall left a managed program file: $name" }
  }
  if (!(Test-Path "$profile/EVORA/data/cases.sqlite3") -or !(Test-Path "$profile/EVORA/config.json") -or !(Test-Path "$install/backend/user-notes.txt")) { throw 'Uninstall removed user data' }
  foreach ($path in @("$env:USERPROFILE/Desktop/EVORA.lnk", "$originalAppData/Microsoft/Windows/Start Menu/Programs/Startup/EVORA.lnk")) {
    if (Test-Path $path) { throw "Uninstall left shortcut: $path" }
  }
  Write-Output 'PASS: real installer/uninstaller stopped EVORA, removed tracked and update-added program files and shortcuts, and preserved user data.'
} finally {
  if ($process -and !$process.HasExited) { Stop-Process -Id $process.Id -Force }
  $env:APPDATA = $originalAppData
  Write-Output "Uninstall test artifacts: $scratch"
}
