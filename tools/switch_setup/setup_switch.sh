#!/bin/bash
# setup_switch.sh - completes the Switch package (BO1Zombies_switch_nodata) with the player's own Call of Duty:
# Black Ops: localization.txt, main/*.iwd, the zones converted by ffconv, shaders.pack and shaders.dksh (uam).
#
#   ./setup_switch.sh "/path/to/Call of Duty Black Ops"
#
# ffconv is a Windows program: it runs through WSL's interop on WSL, else under wine (wine and winepath needed), as
# ZmClient does. shaders.dksh needs python3. The install is only read. The result is switch/bo1zm/ in this folder,
# ready to copy to the SD card's root. The new zones replace zone/ only once ffconv succeeded.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SD="$ROOT/switch/bo1zm"
TOOLS="$ROOT/tools"
LOG="$ROOT/setup_switch.log"

step() { printf '\n== %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

GAME="${1:-}"
[ -n "$GAME" ] || fail "usage: ./setup_switch.sh \"/path/to/Call of Duty Black Ops\" (the folder of BlackOps.exe)"
GAME="$(cd "$GAME" 2> /dev/null && pwd)" || fail "folder not found: $1"
[ -f "$SD/BO1Zombies.nro" ] || fail "no switch/bo1zm/BO1Zombies.nro beside this script"
for t in windows/ffconv.exe linux/uam linux/make_dksh_pack.py; do
    [ -f "$TOOLS/$t" ] || fail "missing tool: tools/$t"
done
command -v python3 > /dev/null || fail "python3 not found (it compiles shaders.dksh)"
if [ ! -d "$GAME/zone" ] || [ ! -f "$GAME/localization.txt" ] || ! ls "$GAME"/main/*.iwd > /dev/null 2>&1; then
    fail "no Black Ops installation in '$GAME' (zone/, main/*.iwd, localization.txt)"
fi
# ffconv.exe: through WSL's interop, else wine; it takes Windows paths
if [ -e /proc/sys/fs/binfmt_misc/WSLInterop ] && command -v wslpath > /dev/null; then
    RUN=() WINPATH=(wslpath -w)
elif command -v wine > /dev/null && command -v winepath > /dev/null; then
    RUN=(wine) WINPATH=(winepath -w)
else
    fail "ffconv is a Windows program: install wine (with winepath), or run Setup-Switch.bat on Windows"
fi
chmod +x "$TOOLS/linux/uam"
echo "setup_switch $(date -Iseconds) from $GAME" > "$LOG"

step "1/3 copying the game files (localization.txt, main/*.iwd)"
mkdir -p "$SD/main"
cp -f "$GAME/localization.txt" "$SD/"
cp -f "$GAME"/main/*.iwd "$SD/main/"

step "2/3 converting the zones (ffconv, about 6 minutes)"
new="$SD/zone.setup-new"
rm -rf "$new"
mkdir -p "$new"
# < /dev/null: a Windows program run from WSL otherwise reads the caller's stdin
if ! "${RUN[@]}" "$TOOLS/windows/ffconv.exe" --verify --game "$("${WINPATH[@]}" "$GAME")" \
        --out "$("${WINPATH[@]}" "$new")" < /dev/null 2>&1 | tee -a "$LOG"; then
    fail "ffconv failed: the previous zones are kept; details in setup_switch.log"
fi
count="$(find "$new/zone" -name '*.ff' 2> /dev/null | wc -l)"
[ "$count" -gt 0 ] && [ -f "$new/shaders.pack" ] || fail "ffconv produced no zones and no shaders.pack; details in setup_switch.log"
rm -rf "$SD/zone"
mv "$new/zone" "$SD/zone"
mv -f "$new/shaders.pack" "$SD/shaders.pack"
rm -rf "$new"
echo "$count zones converted"

step "3/3 compiling shaders.dksh (uam, a few minutes)"
# A shader uam rejects makes the deko3d backend skip every draw that needs it: missing walls on the console.
if ! python3 "$TOOLS/linux/make_dksh_pack.py" "$SD/shaders.pack" "$SD/shaders.dksh.tmp" --uam "$TOOLS/linux/uam" \
        2>&1 | tee -a "$LOG" || ! grep -q ' 0 rejected by uam' "$LOG"; then
    fail "uam rejected shaders or failed; details in setup_switch.log"
fi
mv -f "$SD/shaders.dksh.tmp" "$SD/shaders.dksh"

step "done"
echo "Copy the 'switch' folder of $ROOT to the ROOT of the SD card (it merges with /switch)."
echo "Then start BO1 Zombies while HOLDING R on an installed game (application mode). See README.txt."
