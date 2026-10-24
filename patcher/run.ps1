# Finds Legends of Idleon and runs the installer with the game's own Electron (Node mode).
#   run.ps1 install | ensure | uninstall  [-Game <folder or LegendsOfIdleon.exe>]
param(
    [Parameter(Position = 0)][string]$Mode = 'install',
    [string]$Game = ''
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot

function Test-Game($dir) {
    return $dir -and (Test-Path -LiteralPath (Join-Path $dir 'LegendsOfIdleon.exe')) -and
        (Test-Path -LiteralPath (Join-Path $dir 'resources'))
}

function Find-Game {
    if ($Game) {
        if ((Test-Path -LiteralPath $Game -PathType Leaf)) { $Game = Split-Path -Parent $Game }
        if (Test-Game $Game) { return $Game }
    }
    # the translation folder may have been unpacked inside the game folder
    foreach ($d in @((Split-Path -Parent $root), $root)) { if (Test-Game $d) { return $d } }
    # Steam libraries
    $libs = @()
    foreach ($key in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
        try {
            $p = Get-ItemProperty -Path $key -ErrorAction Stop
            foreach ($v in $p.SteamPath, $p.InstallPath) { if ($v) { $libs += ($v -replace '/', '\') } }
        } catch {}
    }
    foreach ($s in @($libs)) {
        $vdf = Join-Path $s 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $libs += ($m.Groups[1].Value -replace '\\\\', '\')
            }
        }
    }
    foreach ($l in ($libs | Select-Object -Unique)) {
        $d = Join-Path $l 'steamapps\common\Legends of Idleon'
        if (Test-Game $d) { return $d }
    }
    return $null
}

$dir = Find-Game
if (-not $dir) {
    Write-Host 'Не нашёл игру Legends of Idleon.' -ForegroundColor Yellow
    $dir = Read-Host 'Вставьте путь к папке игры (где лежит LegendsOfIdleon.exe)'
    $dir = $dir.Trim('"')
    if (-not (Test-Game $dir)) { Write-Host 'В этой папке игры нет.' -ForegroundColor Red; exit 1 }
}

if ($Mode -ne 'ensure' -and (Get-Process -Name 'LegendsOfIdleon' -ErrorAction SilentlyContinue)) {
    Write-Host 'Сначала закройте игру.' -ForegroundColor Yellow
    exit 2
}

$env:ELECTRON_RUN_AS_NODE = '1'
$env:IDLEON_RU_LOG_ONLY = '1'
$p = Start-Process -FilePath (Join-Path $dir 'LegendsOfIdleon.exe') -Wait -PassThru -NoNewWindow `
    -ArgumentList @('"' + (Join-Path $root 'patcher\main.js') + '"', $Mode, '--game', '"' + $dir + '"')
$code = $p.ExitCode
Remove-Item Env:\ELECTRON_RUN_AS_NODE, Env:\IDLEON_RU_LOG_ONLY
# the game exe is a GUI program, its console output is unreliable: show the log file instead
$log = Join-Path $root 'patcher\last-run.log'
if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
exit $code
