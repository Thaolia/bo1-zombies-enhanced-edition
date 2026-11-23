# ZmClient - launcher for the BO1 zombies client (PC)

A curses program (Python 3, standard library only; `windows-curses` on Windows), built like ZmAdmin
(`tools/zmadmin`) and using its package as a library (widgets, the `getstatus` query, the local server). It sits in a
`make_dist.sh` package folder, next to `BO1Zombies` / `BO1Zombies.exe`, and starts the game three ways:

- **Solo** (offline): a map, the solo mods (horde, nightmare/hell, noperks, mapkit maps, zinfo, hit marker, unlimited
  Pack-a-Punch, faster spawns, quick restart) and god
  mode. The mod flags are those of `tools/mod-launcher.hta`, rule for rule;
- **Join a server**: a saved favourite or a server found on the LAN, with its player password (`g_password`). It
  first asks the server what to load ("Détecter les mods du serveur", on by default: `getmodinfo`, `docs/SERVER.md`)
  and loads the same mods, zones and imported map;
- **Local server + join it**: starts the folder's dedicated server as ZmAdmin does (same state file and rcon password,
  so ZmAdmin administers it) with the Solo view's game (map, mods, start kit), then the game, which joins it once its
  map is loaded and loads what that game needs.

In the two network modes it can also start a **split screen**: two windows of the game for two players on this PC
(see below).

It also edits the player's `players/config.cfg`, adds free dvars to the command line, and installs the game files
from the player's own Black Ops (as `setup.ps1` does for the development tree). The texts it shows are in French, the
players' language.

    python3 tools/zmclient/main.py --dist build/dist/BO1Zombies_linux   # the interface, from the sources
    ./zmclient                                                          # the binary, in a package folder
    ./zmclient --print-cmd        # the command line of the saved profile
    ./zmclient --play             # start the game with the saved profile (solo or join; both windows of a split screen)
    ./zmclient --setup [DIR]      # install the game files from DIR (default: the saved or detected install)

`--dist DIR` the package folder (default: its own folder, then the current one), `--config DIR` its settings folder
(`profile.json`; `%APPDATA%\zmclient` or `~/.config/zmclient`), `--admin-config DIR` ZmAdmin's settings folder (where
the local server's rcon password lives), `--no-mouse` keyboard only.

## Views

| key | view | what it does |
| --- | --- | --- |
| F1 | Jouer | the mode, a summary, Launch / Stop the game / Stop the local server, the state of the game files, and the exact command line |
| F2 | Serveurs | favourites and LAN servers with their live status (name, map, players, ping); add, edit, remove, join |
| F3 | Solo | map (base maps, Dead Ops Arcade, the package's mapkit layouts, Black Ops II's Nuketown and TranZit when `make_dist.sh --bo2` packaged them, and the native Nuketown when its zone and BSP are there (`bo1_mod_zones zombie_bo2nuked`, `bo1_bspworld`); TranZit also loads Ascension's zone for Stamin-Up), god mode, zinfo, noperks, hit marker (mods/hitmarker), unlimited Pack-a-Punch (mods/unlimitedpap, greyed without its script `mods/unlimitedpap/maps/_zombiemode_perks.gsc`, which `tools/unlimitedpap/make_perks.py` writes from your zones), zombie spawn speed (mods/spawnrate: off, 2, 3, 5 or 10 times, `spawnrate_mult`; the sprint to the barriers, `spawnrate_rush`), these three stacked on `fs_mods` after the others, quick restart, start points, power and perks (mods/admin's `zm_startpoints` / `zm_startpower` / `zm_startperks`, stacked on the line's `fs_mods`), Black Ops II's weapons (mods/bo2weapons, when `mods/bo2weapons/mod.ff` is there: in the box with the map's, alone plus the map's special weapons, or alone; `bo2weapons` stacked on `fs_mods`, `bo2weapons_box`), horde settings, difficulty; rows a map does not use are greyed with the reason |
| F4 | Lancement | player name, window mode and size, the graphics API (the default renderer, or Vulkan: `r_mod_gfxApi vulkan` on win64, `BO1_GFX_BACKEND=vulkan` on Linux; it needs `shaders.spv`, docs/VULKAN.md) and under Vulkan the upscaling (`r_mod_upscale` off/ultra/quality/balanced/performance/native (Arm ASR as anti-aliasing at the window's size)/ssaa_1.5x/ssaa_2x (supersampling: rendered 1.5 or 2 times larger, averaged down), `r_mod_upscaler` FSR 1.0 or Arm ASR's quality/balanced/performance shaders, `r_mod_upscaleSharpness`), the split screen (mode, layout, player 2's name and sound), the port's FPS counter, the models drawn per frame (1024, 2048 or 4096: `r_mod_sceneModels` with a model lighting pool to match, for maps imported by MapKit), gamepad aim assist (each "game setting" / on / off), the local server's game (the Solo view's: Entrée goes there), port and rcon password |
| F5 | Config du jeu | a form of `players/config.cfg`: mouse, gamepad, FOV, vsync, FPS cap, gamma, MSAA, anisotropy, texture quality, shadows, depth of field, blood, subtitles; any other dvar; key binds. Its Résolution row is the Launch view's (below), not a `config.cfg` line |
| F6 | Dvars libres | free command lines, each one a `+line` before the map or the connection, enabled one by one; a Description column explains the dvars ZmClient knows (`zmclient/dvarhelp.py`: `bo1_netlog`, `r_shaderWarming`, `bo1_frameperf`, ...), and Add lists them first |
| F7 | Installation | the Black Ops install (found in Steam's libraries, picked in a folder browser, or typed), the state of each part, Install, progress. Install copies the game's files, converts the zones with the package's ffconv (which also writes `shaders.pack`) and compiles `shaders.pack` to `shaders.spv` for Vulkan (`zmclient/spirvpack.py`, shared with `tools/ffconv/gen/make_spirv_pack.py`) with the Windows package's `glslang.exe` or, on Linux, the system's glslang (`glslang-tools`); `s` leaves that step out. `shaders.spv` is compiled again only when it is missing or older than `shaders.pack`. Without glslang the rest installs and the game keeps its default renderer |
| F8 | Journal | the running game's `console_mp.log`, live, with a filter |

Mouse and keyboard work as in ZmAdmin: a click picks, a double click edits or runs, the wheel scrolls; `?` (or F9)
explains the view, each row's help shows below the list.

## The command line

The base is `Play.bat` / `play.sh`'s: `bo1_zombies 1`, `fs_b` and `fs_h` the folder, `logfile 2`, plus
`bo1_mod_sharedconfig 1` (one `players/config.cfg` for every mod, as the `.hta` does). Solo adds `net_ip 127.0.0.1`
(nobody else can join, no firewall prompt) and ends with `+devmap <map>`; the two network modes end with
`cl_allowWanConnect 1` and `cl_autoConnect <address>` (it retries while a local server is still loading), and never
set god mode: the server decides. They load what the server's clients must load (its `fs_game`, `fs_mods`,
`bo1_mod_zones`, `bo1_mod_mapkit`, `bo1_bspworld`): the local server's game in host mode, a remote server's
`getmodinfo` answer in Join mode. Without an answer (an older server) or on a refused password, Join loads the manual
choices "Armes de Black Ops II" and "Armes doublées": a client without a server's `mod.ff` goes back to the menu on
entering, with a message naming the missing weapon. A launch is refused when the package lacks a file the server
loads. When `fs_mods` stacks `bo2weapons` or `dualwield` and the line sets no `bo1_mod_zones`, ZmClient adds
`bo1_mod_pools 1`: the engine then takes its larger asset pools, as with `bo1_mod_zones` (Shangri-La with both mods
overflowed the retail 500 `fx`).

Two engine limits are checked before a launch: `Com_ParseCommandLine` cuts the line at **every** `+` (so no value
may contain one, the folder's path included) and keeps 64 pieces, the text before the first `+` being one: ZmClient
refuses a line of more than 63 commands, counting those of a `launch.cfg` next to the program, which the engine puts
first.

## Split screen

"Écran partagé (2 joueurs)" (Jouer and Lancement views) starts two windows of the game, each a client of the same
server, in the modes "Serveur local + le rejoindre" and "Rejoindre" (not Solo: its listen server takes one player):

- **clavier/souris + manette**: player 1 on the keyboard and mouse, player 2 on the first controller;
- **deux manettes**: player 1 on the first controller, player 2 on the second.

"Disposition" puts the windows side by side (each half of the primary monitor's width) or one above the other. Each
window is frameless on its half (`r_borderless 1`, `r_borderlessRect`, `vid_xpos`/`vid_ypos` 0: the primary monitor)
and gets its input with `bo1_splitInput` (`kbm`, `pad0`, `pad1`): a controller's window reads its controller even
when it does not have the focus and ignores the keyboard and mouse; the keyboard window never reads a controller. The
window and size settings of the Lancement view do not apply then.

Player 2 runs with `fs_h` = `split2/` in the game folder (its own `players/config.cfg`, profile and log), the name
"Nom du joueur 2" (default `Joueur2`), and the sound off unless "Son du joueur 2" is on (both windows play the same
game: every sound twice). Its process is followed through `main/zmclient_client2.json`. ZmClient starts player 2
first, so that the keyboard window, started last, has the focus; Stop closes both. Engine side: `docs/SERVER.md`,
"Split screen".

## config.cfg

The game writes `players/config.cfg` when it quits, so ZmClient refuses to save while the game runs. Edits are
marked `*` and written with **Sauvegarder** (Ctrl+S): an existing `seta` or `bind` line is rewritten in place, a new
one goes after the last of its kind, every other line is kept, and the file keeps its line ends. `bo1_mod_fov` is
also written to `players/bo1_shared.cfg`, which the engine reads after `config.cfg`. "Qualité des textures" writes
`r_picmip_manual` and the `r_picmip*` family together (`r_picmip` alone is read-only while `r_picmip_manual` is 0).

The resolution is not a `config.cfg` line: `R_SetWndParms` takes the monitor's size in borderless (ZmClient's
default), `r_customMode` in a window and `r_mode` only in fullscreen, so a `seta r_mode` alone changed nothing in the
two first modes. The Config view's "Résolution" row and the Launch view's are the same profile value (`window_size`),
saved at once and given on the command line, after `config.cfg`: `r_customMode` in a window, `r_mode` in fullscreen
(a size the monitor does not offer falls back to the engine's default mode).

## Installing the game files

The install is found in Steam's libraries, typed, or picked in a folder browser (`dirbrowser.py`): arrows and Enter go
into a folder, Backspace or Left up to its parent (on Windows, above a drive's root, the list of drives), a letter
jumps to the next folder starting with it, Space picks the folder shown. Each folder that is a Black Ops install is
marked, and the browser opens on the chosen install, else on a Steam library's `steamapps/common`. Hidden and system
folders (`.*`, `$*`, `System Volume Information`) are left out; the install marks are not looked up in a folder of
more than 300 subfolders.

From the player's Call of Duty: Black Ops install (Steam's `libraryfolders.vdf` is read to find it), the Installation
view copies `localization.txt`, `main/*.iwd` and, optionally, `main/video/`, then converts the zombies zones with the
package's `ffconv.exe --verify --game <install> --out <temporary folder>`. The new `zone/` (and `shaders.pack`, which
the Linux GL renderer reads) replace the old ones only when ffconv succeeded. A file already copied (same size and
date) is skipped. `zone/zmclient_setup.json` records the ffconv that made the zones: a package with another ffconv
shows them as to be converted again. The install is only read. The log is `main/zmclient_setup.log`.

ffconv is a Windows program: on Linux ZmClient runs it through WSL's interop when it runs in WSL, else with `wine`
(paths through `wslpath -w` / `winepath -w`), or asks to convert on a Windows PC and copy `zone/` and `shaders.pack`.
An install without the DLCs has only Kino, Five and Dead Ops: ZmClient marks the other maps "non installée" (no
`zone/*/<map>.ff`) and refuses to launch them, solo or as the local server's map. `tools/make_dist.sh --no-game-data` makes packages
(`BO1Zombies_<platform>_nodata/`) with no game file at all, for players who install from their own copy.

## Building (Nuitka, a zipapp for OpenBSD)

    tools/zmclient/build.sh [linux] [windows] [openbsd]
        # build/zmclient/linux/zmclient, build/zmclient/windows/zmclient.exe, build/zmclient/openbsd/zmclient

As ZmAdmin's `build.sh`, with ZmAdmin's package compiled in (put in the zipapp for OpenBSD). On OpenBSD the
Installation view copies the game files but converts no zones: ffconv is a 32-bit Windows program and OpenBSD's wine
runs 64-bit ones only. `tools/make_dist.sh` rebuilds it when a `.py` file of
`tools/zmclient` or `tools/zmadmin/zmadmin`, or this `build.sh`, is newer than the binary.

## Tests

    python3 -m unittest discover -s tests/zmclient -v

The solo flags are compared with `tools/mod-launcher.hta`'s own `refresh()` and `args()`, run under node with a
stubbed DOM (`tests/zmclient/hta_args.js`), on every map of the `.hta` and several mod combinations; the horde and
nightmare flags with `horde_flags.js` and `nightmare_flags.js` on a matrix of inputs. The other tests cover the
command line of each mode and its refusals, the profile file, `config.cfg` rewriting, the server browser against fake
servers (broadcast, favourites, the one query per round), the installation with a fake install and a fake ffconv
(success, failure keeping the old zones, a new ffconv), and the client process (start, found again, stop).
