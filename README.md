# BO1 Zombies

Black Ops 1 Zombies with its engine decompiled, so mods can change the engine itself, not just scripts and maps.
This fork (branch `switch`) also runs it in 64-bit on Windows, Linux, OpenBSD and the Nintendo Switch, adds a dedicated
server, and brings Black Ops II maps and weapons into it.

![](images/1.webp)

![](images/2.webp)

> **No game data is included.** Every package is built from *your own* Black Ops (and Black Ops II for the BO2
> content). Keep the packages for your own devices and never publish them.

French version: `README.fr.md`. The full, detailed reference is [below](#detailed-reference-original-readme).

## Contents

- [What you get](#what-you-get)
- [Platforms](#platforms)
- [Getting started](#getting-started)
- [Black Ops II content](#black-ops-ii-content)
- [Tools](#tools)
- [Building](#building)
- [Documentation](#documentation)
- [Detailed reference (original README)](#detailed-reference-original-readme)

## What you get

- **The ten zombies maps and Dead Ops Arcade**, solo or online.
- **A dedicated server** for Windows and Linux. Players can join a game in progress, and up to 32 can play. It comes
  with admin commands (`zm_god`, `zm_points`, `zm_perk`, `zm_round`...) and an admin console (`zmadmin`).
- **A player launcher** (`zmclient`). It plays solo with mods, joins servers, opens a two-window split screen, and
  installs the game files from your own copy.
- **Mods** that stack: horde, nightmare, MapKit, no perks, zombie counter, the BO2 weapons, dual-wield Pack-a-Punch
  weapons, hit marker, unlimited Pack-a-Punch, faster zombie spawns.
- **Black Ops II maps**: Nuketown, TranZit, Mob of the Dead and Buried, as native BO1 maps.
- **Speedrun info**: the settings that change a run and a SHA-512 over the program and its zones, shown on screen.

## Platforms

| Platform | Status | Notes |
|---|---|---|
| Windows 64-bit | playable | the original D3D9 renderer; `Play.bat`, `zmclient.exe` |
| Windows 32-bit | reference build | the retail layout; `Play.bat offline` without Steam |
| Linux x86-64 | work in progress | OpenGL 4.3 client, dedicated server and headless client; no sound or gamepad yet |
| OpenBSD/amd64 | compiles | cross-built from Linux; not yet run on a real machine |
| Nintendo Switch 1 | playable homebrew | `.nro` for Atmosphère, deko3d or OpenGL, start menu on the console |

## Getting started

1. **Get a package.** Build one with `tools/make_dist.sh` (see [Packages](#packages) below). A GitHub release
   holds the same packages without game files.
2. **Add your game files.** With a package that has no game files, ZmClient's *Installation* view copies them from
   your Black Ops install and converts the zones. On the Switch, `Setup-Switch.bat` (Windows) or
   `./setup_switch.sh` (Linux) completes the SD card folder.
3. **Play.**
   - **Windows / Linux**: run `zmclient`, or `Play.bat` / `play.sh`.
   - **Switch**: launch the `.nro` in application mode (hold R while starting a game). The start menu picks the
     map, the server to join, aim assist, god mode, the start kit (points, power, Pack-a-Punch, perks), graphics,
     controls and controllers. **+** starts the game.
   - **Server**: `Server.bat [map] [port]` or `./server.sh [map] [port]`. Players join with
     `Play.bat net <address>:<port>`, from ZmClient, or from the Switch's **Serveur** screen.

## Black Ops II content

Extracted from your own Black Ops II with `tools/bo2` (OpenAssetTools plus a world dumper) and packaged with
`make_dist.sh --bo2`:

| Map | What works | Not there |
|---|---|---|
| Nuketown | the whole map, its props and BO2's baked light, embers, fires, smoke, sparks, light rays, fog and clouds (BO1 effects on BO2's spots); self-test 107/107 | the meteors' impacts, the water |
| TranZit (classic) | doors, power, perks, Pack-a-Punch, barricades, the bridge, the bus and the bank; ash, fires, smoke, fog, light rays and the lamps' glow (BO1 effects) | Denizens, buildables, the lava's glow |
| Mob of the Dead | cell blocks, doors, perks, Pack-a-Punch, the gondola (running from the start); fires, embers, fog, steam, light rays, sparks, the lamps' glow (BO1 effects) | afterlife, the plane, Brutus, the candles |
| Buried | town, cave and mansion, perks, Pack-a-Punch; the power is on from the start; fog, light rays and their dust, steam, smoke, the lamps' glow (BO1 effects) | Leroy, ghosts, the maze puzzles, buildables |

The BO2 weapons (36 box weapons and their Pack-a-Punch versions) come as the `bo2weapons` mod. In ZmClient's Solo view
the maps are listed as « Mapkit : … native (Black Ops II, monde BSP) ». Details: `docs/BO2_MAPS.md`,
`docs/BO2_WEAPONS.md`.

## Tools

| Tool | What it does |
|---|---|
| `tools/ffconv` | converts your install's fastfiles to the 64-bit format and translates the shaders (`--verify` checks each zone) |
| `tools/zmclient` | player launcher: solo with mods, servers, split screen, installation |
| `tools/zmadmin` | server admin console: players, game, settings, rcon, log |
| `tools/make_dist.sh` | builds the ready-to-copy packages of every platform |
| `tools/bo2` | turns a Black Ops II map into a MapKit layout and a native BO1 map |
| `tools/dualwield` | builds the dual-wield Pack-a-Punch mod from your zones |
| `tools/unlimitedpap` | writes the unlimited Pack-a-Punch mod's script from your zones |
| `tools/switch_setup` | completes a Switch SD card folder from your install |
| `tools/server_status.py`, `tools/server_rcon.py` | query a server, send rcon commands |

## Building

```sh
# zones: from your install, never written into it
build\ffconv\ffconv.exe --verify --game "C:\...\Call of Duty Black Ops" --out build\zones64

# Windows 64-bit
cmake --preset win64-msvc && cmake --build --preset win64-msvc-release      # then Play.bat x64

# Linux
cmake --preset linux64-clang -DDXSDK_DIR=<June 2010 DirectX SDK> && cmake --build --preset linux64-clang

# every package (bash, from WSL)
tools/make_dist.sh
```

The Switch build uses devkitPro (devkitA64, libnx) and is driven by `make_dist.sh`. Prerequisites and every option
are in the [detailed reference](#detailed-reference-original-readme) and in `docs/PORTING.md`.

## Documentation

| Question | Read |
|---|---|
| Port plan, status, decisions | `docs/PORTING.md` |
| How the port is layered | `docs/ARCHITECTURE.md` |
| Renderer backends | `docs/RENDERER.md` |
| Dedicated server | `docs/SERVER.md` |
| Black Ops II maps / weapons | `docs/BO2_MAPS.md`, `docs/BO2_WEAPONS.md` |
| Mods | `mods/*/README.md`, `mods/mapkit/MAPKIT.md` |

---

## Detailed reference (original README)

The README as it was before this summary, kept in full.

### BO1 Zombies

Decompiled engine code for Black Ops 1 Zombies, so mods can change the engine itself, not just scripts and maps.

![](images/1.webp)

![](images/2.webp)

#### Nintendo Switch port (branch `switch`)

This fork ports the engine to Nintendo Switch 1 homebrew (`.nro`, AArch64, libnx). The v1 target is solo offline
zombies on the base maps. It is a work in progress: see `docs/PORTING.md` for the plan and status, and
`docs/ARCHITECTURE.md` for how the port is layered.

On the console the game starts in a text menu, where you choose:
- a solo game, or a dedicated server to join: the **Serveur** line opens its own screen, with the connection on or
  off, the server's IP address and port (typed with the console's keyboard), your player name, a search of the local
  network that lists its servers (on as the screen opens, or on demand), and the console's own network address
  (`docs/SERVER.md`, "Joining from a Switch");
- the map (the ten zombies maps and Dead Ops Arcade);
- the aim assist and its slowdown, lock-on and auto-aim;
- god mode;
- the zombie counter beside the scoreboard (mods/zinfo: zombies alive and left this round), on by default;
- the start kit: one screen for the points (1 000 to 100 000 instead of the game's 500), the power on from the start,
  a Pack-a-Punch always on at the start points, and the perks a solo player gets on arrival (mods/admin's
  `zm_startpoints` / `zm_startpower` / `zm_startpap` / `zm_startperks`; a perk only when the map has its machine), and
  the far zombies' replacement (`zm_farrespawn`); the same screen stacks the hit marker (mods/hitmarker), the unlimited
  Pack-a-Punch (mods/unlimitedpap, when its script is on the SD card) and the faster spawns (mods/spawnrate: 2 to 10
  times, with or without the sprint to the barriers);
- the renderer (deko3d or OpenGL), the resolution (720p, or 540p / 480p for more frames, 540p advised online: the console scales the image to the
  screen), the frame-rate cap, shadows, the props' distance (normal, reduced or short: `r_lodScaleRigid` 1, 1.5 or 2,
  scenery objects drawn simpler and less far for more frames on the native BO2 maps), texture filtering and the
  FPS/battery counter;
- the speedrun info (`bo1_runinfo`, also a ZmClient launch setting): the settings that change a run (mods, god mode,
  aim assist, start kit, timescale...) and a SHA-512 over the program and the zones it loaded, at the bottom of the
  loading screen (default), or also in a corner in game; the full hash goes to the log (`runinfo:` lines), with the program's own SHA-512 (`sha512sum`'s). It tells
  apart runs played with different files; it proves nothing, since a modified program can print any hash;
- the pad's buttons: one screen lists each game action (fire, aim, jump, reload, grenade, knife, sprint...) with the
  Switch button that does it; left/right changes the button and the action that had it takes the old one, so no
  action is left without a button. The game's menus follow; the start menu itself always keeps the console's buttons,
  so a layout gone wrong is fixed there;
- the controllers (the list of detected pads, and the system screen to connect them).

**+** starts the game straight on the map, or opens the game's menu, which then joins the server by itself. The choices are kept in `sdmc:/switch/bo1zm/menu.cfg`, and Start writes
`launch.cfg` and `gfx.cfg`. An empty `skip_menu` file there boots without the menu, on those two files as they are
(handy on an emulator). `docs/ARCHITECTURE.md` lists the files.

In a game, leaving it from the pause menu (Start, then the leave game entry) closes the application cleanly and goes
back to the homebrew menu, rather than to BO1's main menu (`bo1_quitOnDisconnect`, on by default on the console only).
HOME still suspends the game as usual.

No game data is distributed. A converter run on your own PC (`tools/ffconv`) turns your Steam install's
fastfiles into the 64-bit format the port loads, and translates their shaders to GLSL:

    cd tools/ffconv && cmake --preset ffconv && cmake --build --preset ffconv      # from WSL or Linux, MinGW + python3-clang
    build\ffconv\ffconv.exe --verify --game "C:\...\Call of Duty Black Ops" --out C:\bo1zm

It reads the zones of every zombies map (about 3 GB) and writes `zone\` and `shaders.pack` to `--out`, never to the
install. `--verify` reads each written zone back and checks it against the original.

On Windows, the port's offline build (no Steam, Bink, NVAPI, DemonWare or voice chat) can already be played on the
files `setup.ps1` copied: `cmake --preset win32-msvc-offline`, `cmake --build --preset win32-msvc-offline-release`,
then `Play.bat offline`.

The 64-bit build (work in progress: Kino der Toten loads and plays for a minute; longer games are not tested yet)
runs on converted zones: convert into `build/zones64` with `ffconv --verify --game <install> --out build\zones64`,
build with `cmake --preset win64-msvc` and `cmake --build --preset win64-msvc-release`, then `Play.bat x64`.

On Linux x86-64 (work in progress) the engine runs as a dedicated server, a headless client that draws nothing, or
a windowed client rendering with OpenGL 4.3 core (keyboard and mouse; no sound or gamepad yet): `cmake --preset
linux64-clang -DDXSDK_DIR=<June 2010 DirectX SDK>` and `cmake --build --preset linux64-clang` (clang, Ninja, the
development files of SDL2 and GL (`libsdl2-dev`, `libgl-dev`), and python3-clang for the zone layout check). It reads
the same converted zones. Run it from a folder holding the program, your install's `localization.txt`, a `zone`
folder of converted zones and the converter's `shaders.pack`: `./BO1Zombies +set fs_b <install> +set fs_h <that
folder> +devmap zombie_theater` for the windowed client, with `+set bo1_headless 1` for the dedicated server (and
`+set bo1_headless_client 1` for the headless client). `BO1_GFX_BACKEND=null` forces the backend that draws nothing,
`BO1_GL_DEBUG=1` logs OpenGL's debug messages. Converted zones from before 2026-10-24 need a new `shaders.pack`
(`ffconv` again).

On OpenBSD/amd64 the same posix build compiles as well (not yet run on an OpenBSD machine here). It cross-compiles
from Linux with an OpenBSD clang/lld toolchain whose sysroot holds the official sets and the `sdl2` package: pass that
toolchain's CMake file (`-DCMAKE_TOOLCHAIN_FILE=...`) and `-DSDL2_DIR=<sysroot>/usr/local/lib/cmake/SDL2`. The OS
differences are under `#if defined(__OpenBSD__)` in `src/platform/posix` (sysctl instead of `/proc`, `funopen`,
`getthrid`, no CPU affinity); `src/platform/openbsd/include` stands in for the glibc headers OpenBSD lacks.

A dedicated zombies server (work in progress, branch `server`) is the same program started with `+set bo1_server 1`
on Windows or Linux: no window, listening on UDP on every interface, `server.cfg` for its settings. `Server.bat
[map] [port]` and `./Server.sh [map] [port]` start one. Clients join with `Play.bat net <address>:<port> [name]`
(or `Launch.bat net ...`), with `connect <address>:<port>`, or by themselves with `+set cl_autoConnect
<address>:<port>` in a `launch.cfg` next to the program, and `tools/server_status.py <address>` shows the map and
players. Admin commands typed in its console (or over rcon, `tools/server_rcon.py`): `zm_god`, `zm_points`, `zm_perk`,
`zm_revive`, `zm_kill`, `zm_respawn`, `zm_round`, `zm_reset`, `zm_map`, `zm_mods`, and `zm_startpoints` /
`zm_startperks` / `zm_startpower` / `zm_startpap` for the start of a game, `zm_farrespawn` for far zombies. Any player, solo too, can type `zm_where` in their own
console: every living zombie's position and distance, nearest first. Players can join a game in progress (`zm_jip_mode immediate` or
`nextround`), and `sv_maxclients` lets more than 4 play (up to 32; characters repeat past 4). Each client's
console log is sent to the server (UDP game port + 1) and
written to its `logs/` folder; Tab in the server's console shows the selected player's. `tools/zmadmin` is an
admin console for it (curses, Python, built with Nuitka into `zmadmin` / `zmadmin.exe` in the packages): players,
game, settings saved with a button, rcon console, and the local server's log; in a package folder it also starts
that folder's server with an rcon password. See `docs/SERVER.md` and `tools/zmadmin/README.md`.

`tools/zmclient` is the same kind of program for players (`zmclient` / `zmclient.exe` in the packages): it plays solo
with the solo mods of `tools/mod-launcher.hta` (horde, nightmare, mapkit, noperks, zinfo), joins a server (favourites
and LAN servers with their live status), or starts the folder's server and joins it, alone or in a split screen of two windows (keyboard and mouse plus a
controller, or two controllers); it also edits
`players/config.cfg`, adds free dvars, and installs the game files from the player's own Black Ops (copy, then zone
conversion with the shipped `ffconv.exe`). See `tools/zmclient/README.md`.

Black Ops II zombies maps (experimental, branch `bo2`): `tools/bo2` extracts a map from the player's own Black Ops II
(with a world and collision dumper added to OpenAssetTools, GPL v3, built separately) and writes it as a MapKit layout
on an empty Five base: BO2's own collision, zones, spawns, risers, pathnodes, traversals, the box, wall buys, perks and
Pack-a-Punch. Nuketown Zombies runs headless (the self-test buys the box, every perk, every wall buy and Pack-a-Punch there, and a
zombie climbs out of each of its 36 risers and reaches the player along BO2's own node graph, jumping up to the houses'
upper floors and over its fences and windows) and is drawn textured
with its props and its world lit with BO2's baked light (lightmaps, lamps and vertex light), its decals, its glass and its sky; its props block players and bullets. TranZit comes the same way, classic mode:
its doors (the power ones open with the power), Juggernog, Quick Revive, Speed Cola, Double Tap, Stamin-Up (with
Ascension's zone loaded), Pack-a-Punch and the power switch where BO2 builds them, its barricades (boards zombies tear
off and players rebuild), its bridge and its bus, which drives the loop
through the depot, diner, farm, power station and town and carries the players standing in it, waits at each stop with
its doors open, rings before it leaves, shuts its doors on the way (a free button by the driver's seat opens them for a
few seconds, to jump off between stops) and comes to a stop whose lever a player pulls once the power is on (zombies do not board it, and its props are still unlit), and its bank: deposits and withdrawals at
the vault's deposit boxes and the farmhouse's weapon locker, kept between games. See `docs/BO2_MAPS.md`.
Nuketown also runs as a native BO1 map (experimental, branch `bspnuked`): `tools/bo2/bo2_bsp.py` writes its world,
props, collision and BO2's baked light into a BO1 BSP, and `+set bo1_bspworld maps/zombie_bo2nuked.d3dbsp` plays
MapKit's Nuketown gameplay on it (the self-test passes 106 of 106 checks; models are not lit yet). `make_dist.sh --bo2`
packages it and ZmClient's Solo view offers it as "Mapkit : Nuketown native (Black Ops II, monde BSP)".

#### Packages

`tools/make_dist.sh` (bash, from WSL) turns a source tree where `setup.ps1` has copied the game into ready-to-copy
folders and archives in `build/dist`, one per platform:

| Package | Holds | Archive |
|---|---|---|
| `BO1Zombies_windows/` | the 64-bit client and dedicated server, `Play.bat` (`Play.bat net <address[:port]> [name]` joins a server), `Server.bat [map] [port]`, `zmclient.exe`, `zmadmin.exe`, `ffconv.exe`, the 64-bit runtime DLLs, `switch-tools\uam.exe` (below) | `.zip` |
| `BO1Zombies_linux/` | the Linux client and dedicated server, `play.sh` (`./play.sh net ...`), `server.sh [map] [port]`, `zmclient`, `zmadmin`, `ffconv.exe`, `shaders.pack` | `.tar.gz` |
| `BO1Zombies_switch/` | an SD card tree, `switch/bo1zm/` with the `.nro`, `shaders.pack` and `shaders.dksh` | `.zip` |
| `BO1Zombies_openbsd/` | the OpenBSD/amd64 client and dedicated server, `BO1Zombies-8.0` (the release) and `BO1Zombies-current`, `play.sh` and `server.sh` (POSIX sh: they pick the running system's program and raise the data size limit), `shaders.pack`; only when asked (`tools/make_dist.sh openbsd`) | `.tar.gz` |

Each also holds the converted zones, the install's `main/*.iwd` and `localization.txt` (and `main/video` on PC), a
`LISEZMOI.txt` and a `VERSION.txt` (commit, date, NRO link time). With `--no-game-data` the packages go to
`BO1Zombies_<platform>_nodata/` and hold no file of the game: the player installs the windows and linux ones with
ZmClient's Installation view, from their own Black Ops. The switch one holds the `.nro`, `mods/` and the tools that
complete its SD card folder from the player's own install (`tools/switch_setup`): `Setup-Switch.bat ["<install>"]` on
Windows, `./setup_switch.sh <install>` on Linux. They copy `localization.txt` and `main/*.iwd`, convert the zones with
`ffconv` (through wine or WSL on Linux), and compile `shaders.dksh` with `uam` and `make_dksh_pack` (a Nuitka `.exe`
on Windows, `python3` on Linux; `tools/uam/build.sh` builds both uams, `tools/switch_setup/build.sh` the `.exe`).

    tools/make_dist.sh                       # windows, linux and switch
    tools/make_dist.sh switch linux          # some
    tools/make_dist.sh --openbsd-cross /opt/openbsd-cross openbsd
    tools/make_dist.sh --no-build windows    # package what is built, fail on anything missing or out of date

Unless `--no-build`, it builds what the packages need, incrementally: the `win64-msvc` preset, the Linux and Switch
programs in `--work` (an ext4 folder, `~/.cache/bo1zm-dist`), the converted zones when they are missing or older than
the converter's sources (`ffconv --verify`, then `check_shader_pack.py`; the old zones stay until the new ones
pass), and `shaders.dksh` when its `shaders.pack` changed (it fails if uam rejects a shader). Other options:
`--out`, `--game`, `--zones`, `--dxsdk`, `--archive auto|zip|tar|none`, `--jobs`; `--help` lists them. The OpenBSD
programs build with the cross toolchain of [cross-compiler-openbsd](https://github.com/Thaolia/cross-compiler-openbsd)
(`--openbsd-cross <prefix>` or `OPENBSD_CROSS`: its `install.sh` prefix, with the `8.0` and `current` sysroots and
their `sdl2` package). There is no ZmClient or ffconv for OpenBSD: the `_nodata` OpenBSD package takes the game files
of a Windows or Linux install made with ZmClient (its `LISEZMOI.txt` lists them). The packages
hold your own game files: keep them for your own devices, never publish them (the `_nodata` ones hold none).

`switch-tools\uam.exe` in the Windows package is deko3d's offline shader compiler, which devkitPro ships for Linux
only, built for Windows by `tools/uam/build.sh` (MinGW-w64, uam v1.1.0). With Python 3 it makes a Switch package's
`shaders.dksh` on Windows: `python switch-tools\make_dksh_pack.py shaders.pack shaders.dksh --uam
switch-tools\uam.exe`. Like devkitPro's uam, its code can differ from run to run (it depends on heap addresses) and
there is no `setarch -R` on Windows to pin it.

Under wine, a crash or a black screen at start-up inside wine's `xaudio2_7.dll` (seen with OpenBSD's experimental
wine) is avoided by a `launch.cfg` next to `BO1Zombies.exe` holding `nosnd`, the game's own switch: it starts without
any sound driver, as on a PC without a sound device.

`--bo2 DIR` also puts your own Black Ops II map extraction (`docs/BO2_MAPS.md`, "Running it") into the windows and linux
packages. It takes `DIR/mods/mapkit/layouts/bo2_*.json` and `DIR/mods/mapkit/imports/`, and ZmClient's Solo view then
offers "Mapkit : Nuketown (Black Ops II)" and "Mapkit : TranZit (Black Ops II)" (which also loads Ascension's zone
for Stamin-Up). The extraction is game data, so `--bo2` cannot be combined with
`--no-game-data`. `--dualwield DIR` does the same for your own build of `mods/dualwield` (dual-wield Ray Gun
and Thundergun after Pack-a-Punch, made by `tools/dualwield/dualwield_mod.py` from your game's zones alone, or from
your copy of the "Relaxing Dual Wield" mod, which adds the PPSh; see `mods/dualwield/README.md`), in every package,
Switch included. Every package with game data also gets `mods/unlimitedpap`'s Pack-a-Punch script, written from your
`common_zombie_patch.ff` by `tools/unlimitedpap/make_perks.py` (the retail script with the mod's 13 changed lines;
`mods/unlimitedpap/README.md`). Nuketown has over 2 000 props: ZmClient's Lancement view, "Modèles affichés par image" at 4096
(`r_mod_sceneModels`), draws them all; 1024 (retail) drops the farthest.

##### Release on GitHub

`.github/workflows/release.yml` builds the programs of the four platforms on GitHub's machines and publishes a release, "BO1 Zombies
Enhanced edition version <tag>", holding one archive per platform (`BO1Zombies_<tag>_windows.zip`, `_linux`,
`_switch`, and `BO1Zombies_<tag>_openbsd.tar.gz`: OpenBSD's base system has tar, not unzip), each the `_nodata`
package. It starts by hand only: Actions, "Release", "Run workflow", with the tag to
create (e.g. `v0.1.0`). It downloads the June 2010 DirectX SDK from Microsoft, builds `win64-msvc` with ZmClient and
ZmAdmin (Nuitka) on Windows, the Linux program, `ffconv.exe` and the Linux ZmClient and ZmAdmin on Ubuntu, the `.nro`
in devkitPro's `devkita64` container, the OpenBSD programs for 8.0 and -current with cross-compiler-openbsd (pinned
to a commit; the 8.0 sysroot is cached, -current's is fetched each run), then packages them with `tools/make_dist.sh --no-build --no-game-data`, as on a
PC. The release holds no file of the game.

French version: `README.fr.md`.
