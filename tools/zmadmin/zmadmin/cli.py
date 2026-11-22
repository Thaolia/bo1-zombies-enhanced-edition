"""Command line: the curses UI by default, --status / --rcon for scripts and smoke tests of the built binary."""
import argparse
import curses
import locale
import os
import sys

from . import __version__
from . import help as H
from .config import Config
from .launcher import LocalServer, find_dist
from .profiles import local_game, profile_configured, start_profile
from .protocol import DEFAULT_PORT, ProtocolError, RconClient, parse_target, query_status, strip_colors

DESCRIPTION = """ZmAdmin: administration console for the BO1 zombies dedicated server (docs/SERVER.md).

  zmadmin                              the interface; the Servers view lists the saved servers
  zmadmin 192.168.1.20 -p secret       connect at once (port 3074 unless given as host:port)
  zmadmin --status 192.168.1.20        print the server's status and exit (no rcon needed)
  zmadmin --rcon "zm_admin" HOST -p PW print one rcon command's output and exit

Next to BO1Zombies and server.sh / Server.bat (a make_dist.sh folder) it also starts that folder's servers, one per
profile (Servers view: n for a new one):
  zmadmin --start kino                 start profile "kino" as saved, no question asked, then show it
  zmadmin --start default --start kino --detach
                                       start both and exit (a scheduled task, a service)
  zmadmin --list-profiles              the folder's profiles: port, map, state"""


def print_status(target, timeout):
    host, port = parse_target(target, DEFAULT_PORT)
    try:
        st = query_status((host, port), timeout=timeout)
    except (ProtocolError, OSError) as e:
        print(f"no answer: {e}")
        return 1
    print(f"server: {st.get('sv_hostname')}")
    print(f"map: {H.map_label(st.get('mapname'))}")
    print(f"players: {len(st.players)}/{st.max_clients}")
    for p in st.players:
        print(f"  #{p.slot} {p.name}: {p.score} points, ping {p.ping}, {p.state_name}")
    return 0


def run_rcon(target, password, command, timeout):
    host, port = parse_target(target, DEFAULT_PORT)
    client = RconClient((host, port), password, timeout=timeout)
    try:
        sys.stdout.write(strip_colors(client.command(command)))
    except (ProtocolError, OSError) as e:
        print(f"rcon: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zmadmin", description=DESCRIPTION,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", help="server address, host[:port]")
    parser.add_argument("-p", "--password", default="", help="the server's rcon_password")
    parser.add_argument("--status", action="store_true", help="print the status of TARGET and exit")
    parser.add_argument("--rcon", metavar="COMMAND", help="send COMMAND to TARGET over rcon, print the reply, exit")
    parser.add_argument("--timeout", type=float, default=2.0, help="seconds to wait for --status / --rcon")
    parser.add_argument("--dist", help="the BO1Zombies folder whose server ZmAdmin may start (default: its own "
                                       "folder, or the current one)")
    parser.add_argument("--admin-poll", type=float, default=5.0, metavar="SECONDS",
                        help="how often the Players and Game views read zm_admin (0: never; each read is one rcon "
                             "command, logged by the server)")
    parser.add_argument("--no-mouse", action="store_true",
                        help="keyboard only: leave the mouse to the terminal (text selection without Shift)")
    parser.add_argument("--config", help="ZmAdmin's settings folder (servers.json, history)")
    parser.add_argument("--start", action="append", metavar="PROFILE",
                        help="start this local server profile with its saved game, port and password (repeatable)")
    parser.add_argument("--detach", action="store_true", help="with --start: start, print, exit without the interface")
    parser.add_argument("--list-profiles", action="store_true", help="print the folder's local server profiles, exit")
    parser.add_argument("--version", action="version", version=f"zmadmin {__version__}")
    args = parser.parse_args(argv)

    if args.status or args.rcon:
        if not args.target:
            parser.error("--status and --rcon need a TARGET")
        if args.rcon:
            return run_rcon(args.target, args.password, args.rcon, args.timeout)
        return print_status(args.target, args.timeout)

    initial = None
    if args.target:
        try:
            host, port = parse_target(args.target, DEFAULT_PORT)
        except ValueError as e:
            parser.error(str(e))
        initial = (host, port, args.password, ("cli", {"host": host, "port": port}))
    if args.detach and not args.start:
        parser.error("--detach goes with --start")
    if args.start and args.target:
        parser.error("--start connects to the profile it starts: no TARGET")
    dist = find_dist(args.dist)
    if args.dist and not dist:
        parser.error(f"{args.dist} is not a BO1Zombies folder (BO1Zombies, server script and zone/ needed)")
    if (args.start or args.list_profiles) and not dist:
        parser.error("no BO1Zombies folder here: run it from one, or give --dist")
    config = Config(args.config)
    if args.list_profiles:
        return list_profiles(config, dist)
    if args.start:
        code = start_profiles(config, dist, args.start)
        if code or args.detach:
            return code

    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")  # Esc closes a dialog at once instead of after 1 s
    from .app import App

    def run(scr):
        app = App(scr, config, dist, initial, args.admin_poll, not args.no_mouse)
        if args.start:
            app.connect_local(args.start[0])
        return app.run()
    return curses.wrapper(run) or 0


def list_profiles(config, dist):
    print(f"{dist.root}:")
    for name, local in config.local_profiles(dist.root):
        server = LocalServer(dist, name)
        if server.running():
            state = f"running, PID {server.pid}, port {server.port}"
        else:
            state = "stopped" if profile_configured(local) else "stopped, never set up"
        print(f"  {name:<20} port {local['port']:<6} {H.map_label(local_game(local).get('map', '')):<28} {state}")
    return 0


def start_profiles(config, dist, names):
    """Starts each profile as saved (profiles.start_profile), before the interface. 0, or 2 on the first that cannot
    start: an unknown name, a profile never set up (its game was never chosen), a busy port."""
    for name in dict.fromkeys(names):
        local = config.local_profile(dist.root, name)
        if local is None:
            known = ", ".join(n for n, _ in config.local_profiles(dist.root))
            print(f"zmadmin: no profile {name!r} in {dist.root} (profiles: {known})", file=sys.stderr)
            return 2
        if not profile_configured(local):
            print(f"zmadmin: profile {name!r} was never set up: choose its game once in the Servers view "
                  "(l or Enter)", file=sys.stderr)
            return 2
        server = LocalServer(dist, name)
        if server.running():
            print(f"{name}: already running, PID {server.pid}, port {server.port}")
            continue
        why = start_profile(config, dist, server, name)
        if why:
            print(f"zmadmin: {name}: {why}", file=sys.stderr)
            return 2
        print(f"{name}: started, PID {server.pid}, port {server.port}, {H.map_label(server.map)}, "
              f"log {server.home.log}")
    try:
        config.save()       # a password local_settings generated must stay the server's
    except OSError as e:
        print(f"zmadmin: servers.json not written: {e}", file=sys.stderr)
    return 0
