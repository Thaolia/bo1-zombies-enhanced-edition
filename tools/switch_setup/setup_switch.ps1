# setup_switch.ps1 - completes the Switch package (BO1Zombies_switch_nodata) with the player's own Call of Duty:
# Black Ops: localization.txt, main\*.iwd, the zones converted by ffconv, shaders.pack and shaders.dksh (uam).
#
#   Setup-Switch.bat ["D:\Games\Call of Duty Black Ops"]
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup_switch.ps1 [-GameDir <install>]
#
# The install is only read. Its result is switch\bo1zm\ in this folder, ready to copy to the SD card's root. The new
# zones replace zone\ only once ffconv succeeded, so a failed run keeps the previous ones. Windows PowerShell 5.1.
param(
    [Parameter(Position = 0)]
    [string]$GameDir = 'C:\Program Files (x86)\Steam\steamapps\common\Call of Duty Black Ops'
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$sd = Join-Path $root 'switch\bo1zm'
$tools = Join-Path $root 'tools\windows'
$log = Join-Path $root 'setup_switch.log'

function Step($text) { Write-Host ''; Write-Host "== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host ''; Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

if (-not (Test-Path (Join-Path $sd 'BO1Zombies.nro'))) { Fail "no switch\bo1zm\BO1Zombies.nro beside this script" }
foreach ($t in 'ffconv.exe', 'uam.exe', 'make_dksh_pack.exe') {
    if (-not (Test-Path (Join-Path $tools $t))) { Fail "missing tool: tools\windows\$t" }
}
if (-not ((Test-Path (Join-Path $GameDir 'zone')) -and (Test-Path (Join-Path $GameDir 'localization.txt')) -and
          (Get-ChildItem (Join-Path $GameDir 'main') -Filter *.iwd -ErrorAction SilentlyContinue))) {
    Fail "no Black Ops installation in '$GameDir' (zone\, main\*.iwd, localization.txt). Give the folder that holds BlackOps.exe: Setup-Switch.bat `"D:\...\Call of Duty Black Ops`""
}
Set-Content -Path $log -Value "setup_switch $(Get-Date -Format s) from $GameDir"

Step '1/3 copying the game files (localization.txt, main\*.iwd)'
New-Item -ItemType Directory -Force (Join-Path $sd 'main') | Out-Null
Copy-Item (Join-Path $GameDir 'localization.txt') $sd -Force
robocopy (Join-Path $GameDir 'main') (Join-Path $sd 'main') *.iwd /NDL /NFL /NJH /NP /R:1 /W:1 | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "copying the .iwd files failed (robocopy $LASTEXITCODE)" }

Step '2/3 converting the zones (ffconv, about 6 minutes)'
$new = Join-Path $sd 'zone.setup-new'
if (Test-Path $new) { Remove-Item -Recurse -Force $new }
New-Item -ItemType Directory -Force $new | Out-Null
& (Join-Path $tools 'ffconv.exe') --verify --game $GameDir --out $new | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE) { Fail "ffconv failed (code $LASTEXITCODE): the previous zones are kept; details in setup_switch.log" }
$zones = Get-ChildItem (Join-Path $new 'zone') -Recurse -Filter *.ff -ErrorAction SilentlyContinue
if (-not $zones -or -not (Test-Path (Join-Path $new 'shaders.pack'))) { Fail "ffconv produced no zones and no shaders.pack" }
$zone = Join-Path $sd 'zone'
if (Test-Path $zone) { Remove-Item -Recurse -Force $zone }
Move-Item (Join-Path $new 'zone') $zone
Move-Item (Join-Path $new 'shaders.pack') (Join-Path $sd 'shaders.pack') -Force
Remove-Item -Recurse -Force $new
Write-Host "$($zones.Count) zones converted"

Step '3/3 compiling shaders.dksh (uam, a few minutes)'
$tmp = Join-Path $sd 'shaders.dksh.tmp'
$out = & (Join-Path $tools 'make_dksh_pack.exe') (Join-Path $sd 'shaders.pack') $tmp --uam (Join-Path $tools 'uam.exe')
$code = $LASTEXITCODE
$out | Tee-Object -FilePath $log -Append
# A shader uam rejects makes the deko3d backend skip every draw that needs it: missing walls on the console.
if ($code -or -not ($out -match ' 0 rejected by uam')) { Fail "uam rejected shaders or failed; details in setup_switch.log" }
Move-Item $tmp (Join-Path $sd 'shaders.dksh') -Force

Step 'done'
Write-Host "Copy the 'switch' folder of $root to the ROOT of the SD card (it merges with /switch)."
Write-Host 'Then start BO1 Zombies while HOLDING R on an installed game (application mode). See README.txt.'
