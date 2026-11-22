# ZmAdmin - admin console for the BO1 zombies dedicated server

A curses program (Python 3, standard library only; `windows-curses` on Windows) that drives a dedicated zombies
server (`docs/SERVER.md`) over its UDP queries: `getstatus` for the players, rcon for every command. The texts it
shows are in French, the players' language.

    python3 tools/zmadmin/main.py                          # the interface
    python3 tools/zmadmin/main.py 192.168.1.20 -p secret   # connect at once (port 3074 unless host:port)
    python3 tools/zmadmin/main.py --status 192.168.1.20    # status only, no curses, no password
    python3 tools/zmadmin/main.py --rcon zm_admin 192.168.1.20 -p secret

`--admin-poll SECONDS` sets how often the Players and Game views read `zm_admin` (5 by default, 0 never),
`--dist DIR` the folder whose servers it may start, `--config DIR` its settings folder, `--no-mouse` keyboard only.

    python3 tools/zmadmin/main.py --start kino                    # start profile "kino" as saved, then show it
    python3 tools/zmadmin/main.py --start default --start kino --detach   # start both, no interface
    python3 tools/zmadmin/main.py --list-profiles                 # name, port, map, state

`--start PROFILE` (repeatable) starts a local server profile with its saved game, port and password, without a single
dialog, then opens the interface connected to the first one; `--detach` starts and exits (a scheduled task, a
service). An unknown profile, one never set up (its game never chosen) or a busy port: a message and exit code 2.

## Views

| key | view | what it does |
| --- | --- | --- |
| F1 | Servers | the local server profiles when ZmAdmin sits in a `make_dist.sh` folder (new, configure, start as saved, connect, stop, remove), then the saved remote servers (`servers.json`) |
| F2 | Players | each slot: state, health, points, ping, god/demigod/notarget/noclip/frozen; one key per `zm_*` action on the selected player, `a` for all |
| F3 | Game | map, mods, start settings; go to a round, power on, reset, change map, change mods |
| F4 | Settings | a form of the live settings (`sv_hostname`, `g_password`, `rcon_password`, `zm_startpoints`, `zm_startperks`, `zm_jip_mode`, `zm_debug_revive`, `zm_clientcheats`, `zm_clientlogs`, `bo1_mod_priority`, `g_inactivity`, `sv_maxclients`, `fs_mods`, `bo2weapons_box`) |
| F5 | Console | any command over rcon, with its reply and a saved history |
| F6 | Log | the local server's `console_mp.log`, live, with a filter |

**Mouse or keyboard.** A click picks a tab, a row, a button or an action of the Players legend, a double click opens
or runs the row (connect, launch, edit a setting, run a game action), the wheel scrolls; each dialog has its buttons
(`[ OK ]`, `[ Annuler ]`, ...) and the message line `[ Aide ]` / `[ Quitter ]`. Clicks act on release (a slow click
never acts twice). The terminal then keeps its own text selection behind Shift; `--no-mouse` leaves the mouse to it.

`?` (or F9) explains every key of the view; the Settings view explains the selected setting below the form (what it
does, its values and default, when it takes effect).

**Settings are saved with a button.** An edited line is marked `*` and nothing is sent until **[ Sauvegarder ]**
(or Ctrl+S): it lists the commands, sends the `set`s in one rcon command (`a;b;c`), reads every edited dvar back and
marks each line applied or refused, with the server's output. `rcon_password` goes last, and ZmAdmin switches to the
new one once the server answered. `sv_maxclients` takes effect at the next map load (Save offers `zm_reset`);
`fs_mods` is applied with `zm_mods`, which reloads the map.

**Applied settings are kept by ZmAdmin.** Every value Save applied is kept in `servers.json` with the server it was
sent to: the local profile, or the saved remote server. A local profile's `server.cfg` (`<its folder>/main/`) is
rebuilt from them after each Save, before each start of the profile, and with **[ Reconstruire server.cfg ]**: an
existing `set` line is rewritten in place, a new one goes before the first map load, other lines are kept. For a
remote server, **[ Exporter server.cfg ]** writes `<ZmAdmin's folder>/<name>_server.cfg` to copy to its machine.
`rcon_password` is never written (the profile's goes on the command line), nor `fs_mods` for a local profile (its
mods come from its game on the command line, and a `server.cfg` `fs_mods` would replace them). `server.cfg` runs after
the command line, so a kept setting wins over the same dvar of the profile's game (start points or perks, the BO2
box); choosing the game again (`l`, `e`) drops the kept settings its new line sets: the latest choice wins.

## The server's limits it works with

- **One rcon command every 500 ms**, all senders together (`SVC_RemoteCommand`): a command sent sooner is dropped
  without a reply. ZmAdmin spaces its commands by 550 ms, retries once on silence, and shows how many wait. Several
  commands in one rcon (`;`) count as one.
- **rcon returns only the command's immediate output.** The `admin: ...` replies of mods/admin come one frame later,
  in the server's log: ZmAdmin shows them only for the local server, whose `console_mp.log` it follows. For a remote
  server, the Players view shows the result at the next `zm_admin` read.
- **Every rcon command is logged by the server** (`Rcon from ...`): the `zm_admin` reads add one line every few
  seconds while the Players or Game view is open (`--admin-poll` to change or stop them).

## The local servers

ZmAdmin finds a `make_dist.sh` folder (`BO1Zombies` or `BO1Zombies.exe`, `server.sh` or `Server.bat`, `zone/`) in
its own folder or the current one. That folder runs one server per **profile**, several at once: a profile is a name,
a game, a port, an rcon password and the kept settings, in `servers.json`. The profile `default` is the one older
ZmAdmins, `server.sh` / `Server.bat` and ZmClient's local server use; F1 `n` makes others. The engine has no
single-instance lock, but each server needs its own folder (`fs_h`: `server/` for `default`, `servers/<name>/`
otherwise; its `console_mp.log`, `server.cfg`, the players' `logs/` and the TranZit bank `mapkit_bank.txt`) and its
own ports: the game port and port + 1 (the players' logs). ZmAdmin keeps two ports between profiles (3074, 3076, ...),
refuses a port that touches a running profile's, and tests that both UDP ports are free before a start: the engine
would otherwise silently take the next free port and ZmAdmin would talk to another server. Enter on a stopped profile
starts it as saved; `l` asks its game again first. The Log view follows the last local profile connected to.

It starts a server as that folder's script does (`fs_b` the folder, `fs_h` the profile's folder, `bo1_server 1`,
`net_ip 0.0.0.0`, `+devmap <map>`), with `bo1_tui 0` (no window; output in
`<profile folder>/main/zmadmin_server_output.log`) and the rcon password twice: `+set rcon_password` is applied before
`server.cfg` runs, and the `+rcon_password <pw>` command after it, so a `server.cfg` password never locks ZmAdmin out.
The launch asks the game as ZmClient's Solo view sets it (`zmadmin/gamemods.py`, which ZmClient uses too): the map,
the package's MapKit maps included (Black Ops II's native Nuketown, TranZit, Mob of the Dead, Buried), then the mods
(zinfo, noperks, hit marker, unlimited Pack-a-Punch, horde), then each choice that applies: Normal / Nightmare / Hell
on Kino and Five, the horde's size, the spawn speed, Black Ops II's weapons and what the box gives (with
`mods/bo2weapons/mod.ff`, `docs/BO2_WEAPONS.md`), dual wield (with `mods/dualwield/mod.ff`). The answers are kept in
`servers.json` with the profile. The mods' `mod.ff` load at start-up only, so `zm_mods` cannot add them later. Players joining with
ZmClient or the Switch menu load the same mods and map by themselves (`getmodinfo`, `docs/SERVER.md`).
The password is generated once per profile and kept in `servers.json`; the PID, port and map in
`<profile folder>/main/zmadmin_server.json`, so a later ZmAdmin finds the servers that kept running (it checks the
PID's program is that folder's). Quitting asks whether to stop them; a stop sends `quit` and kills the process after
15 s.
On Windows the server runs without a window (`CREATE_NO_WINDOW`); the first start from a new folder showed Windows'
firewall question for `BO1Zombies.exe`: allow it for players on other machines.

## Building (Nuitka)

    tools/zmadmin/build.sh [linux] [windows]      # build/zmadmin/linux/zmadmin, build/zmadmin/windows/zmadmin.exe

One file per platform, with Python inside. Linux: a venv and a copy of the sources on ext4 (`$ZMADMIN_WORK`, default
`~/.cache/zmadmin`), gcc and patchelf. Windows, from WSL: a venv of the Windows Python 3.13 in
`build\zmadmin\venv-win` with `nuitka` and `windows-curses`, compiled with MSVC. `tools/make_dist.sh` runs it when a
`.py` file or `build.sh` is newer than the binary, and puts the binaries in `BO1Zombies_linux/` and
`BO1Zombies_windows/`. The Linux binary needs the glibc of the machine that built it (2.38 here; the game itself
needs 2.43).

## Tests

    python3 -m unittest discover -s tests/zmadmin -v

A fake UDP server answers as the real one does (formats checked on a win64 server): getstatus, rcon replies split
over several packets, `a;b` batches, the 500 ms limit, a refused password. The tests cover the parsers, the Settings
form and its commands, `server.cfg` rewriting, the network thread (events, offline then back), the log follower
(truncation), the launcher's command line, and the profiles: `servers.json` of an older ZmAdmin, ports two apart,
each profile's `fs_h`, a busy port, kept settings and the `server.cfg` rebuilt from them, `--start` / `--detach` /
`--list-profiles`, the new-profile dialog.
