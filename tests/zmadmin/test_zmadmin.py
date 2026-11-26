"""ZmAdmin's protocol, parsers, Settings form, log follower and launcher, against a fake server.

    python3 -m unittest discover -s tests/zmadmin -v

The fake server answers as the real one does (formats checked on a win64 server, 2026-10-29): getstatus, rcon with
'"name" is: "value^7" default: ...' lines, several dvars in one rcon ("a;b"), "Invalid password.", one command per
500 ms (a sooner one gets no reply), and replies split over several print packets.
"""
import errno
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "zmadmin"))

from zmadmin import gamemods, launcher, protocol  # noqa: E402
from zmadmin.i18n import set_language  # noqa: E402
from zmadmin.link import ServerLink  # noqa: E402
from zmadmin.logtail import LogTail  # noqa: E402
from zmadmin.model import merge_players, parse_dvars, parse_zm_admin  # noqa: E402
from zmadmin.settings import APPLIED, REFUSED, Form, update_server_cfg  # noqa: E402
from zmadmin.widgets import ChecklistDialog, ConfirmDialog, HitMap, mouse_kind  # noqa: E402


def setUpModule():
    # ZmAdmin runs in French (cli.main sets it): its tests see the texts it shows
    set_language("fr")


def tearDownModule():
    set_language("en")


OOB = b"\xff\xff\xff\xff"
ZM_ADMIN = ('zm_admin: start points 0, start perks "jugg", join in progress immediate, fs_mods ""\n'
            "   0 Alpha                    playing    health  100 god\n"
            "   1 Bravo the second         down       health   12 notarget frozen\n"
            "   2 Charlie                  loading    health    0\n")


class FakeServer(threading.Thread):
    def __init__(self, password="test", split=False):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.05)
        self.addr = self.sock.getsockname()
        self.password = password
        self.split = split
        self.dvars = {"sv_hostname": "Fake^1Server", "g_password": "", "sv_maxclients": "4", "zm_jip_mode": "immediate"}
        self.mods = {"fs_game": "mods/mapkit", "fs_mods": "mapkit bo2weapons", "bo1_mod_mapkit": "bo2_zm_transit_bsp",
                     "bo1_mod_zones": "zombie_bo2transit zombie_cosmodrome zombie_bo2fx",
                     "bo1_bspworld": "maps/zombie_bo2transit.d3dbsp"}
        self.commands = []
        self.last_rcon = 0.0
        self.dropped = 0
        self.running = True
        self.start()

    def stop(self):
        self.running = False
        self.join()
        self.sock.close()

    def reply(self, text, to):
        chunks = [text[:20], text[20:]] if self.split and len(text) > 20 else [text]
        for c in chunks:
            self.sock.sendto(OOB + b"\x01print\n" + c.encode("latin-1"), to)

    def run_command(self, cmd):
        out = []
        for part in cmd.split(";"):
            words = part.strip().split(" ", 2)
            if not words[0]:
                continue
            if words[0] == "set" and len(words) == 3:
                self.dvars[words[1]] = words[2].strip('"')
            elif words[0] in self.dvars and len(words) == 1:
                out.append(f'"{words[0]}" is: "{self.dvars[words[0]]}^7" default: "x^7"\n    Domain is any text\n')
            elif words[0] == "zm_admin":
                out.append(ZM_ADMIN)
            else:
                out.append(f'Unknown command "{words[0]}"\n')
        return "".join(out)

    def run(self):
        while self.running:
            try:
                data, src = self.sock.recvfrom(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if data == OOB + b"getstatus":
                info = "\\sv_hostname\\Fake^1Server\\mapname\\zombie_theater\\sv_maxclients\\4"
                body = f"statusResponse\n{info}\n0 500 31 5 \"Alpha\"\n1 1200 40 5 \"Bravo the second\"\n"
                self.sock.sendto(OOB + body.encode(), src)
            elif data.startswith(OOB + b"getmodinfo"):
                # SV_ModInfoRequest: the settings to the player password (or to anyone without one), else "refused"
                sent = data[len(OOB) + len(b"getmodinfo"):].decode("latin-1").strip().strip('"')
                if self.dvars["g_password"] and sent != self.dvars["g_password"]:
                    self.sock.sendto(OOB + b"modinfoResponse\nrefused\n", src)
                    continue
                info = "".join(f"\\{k}\\{self.mods[k]}" for k in self.mods)
                self.sock.sendto(OOB + f"modinfoResponse\n{info}\n".encode("latin-1"), src)
            elif data.startswith(OOB + b"rcon "):
                now = time.monotonic()
                if now - self.last_rcon < 0.5:
                    self.dropped += 1
                    continue
                self.last_rcon = now
                _, password, cmd = data[len(OOB):].decode("latin-1").split(" ", 2)
                if password != self.password:
                    self.reply("Invalid password.\n", src)
                    continue
                self.commands.append(cmd)
                self.reply(self.run_command(cmd), src)


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.server = FakeServer(split=True)

    def tearDown(self):
        self.server.stop()

    def test_status(self):
        st = protocol.query_status(self.server.addr)
        self.assertEqual(st.get("sv_hostname"), "FakeServer")
        self.assertEqual(st.max_clients, 4)
        self.assertEqual([(p.slot, p.name, p.score, p.state_name) for p in st.players],
                         [(0, "Alpha", 500, "active"), (1, "Bravo the second", 1200, "active")])

    def test_rcon_spacing_and_split_replies(self):
        client = protocol.RconClient(self.server.addr, "test")
        self.addCleanup(client.close)
        start = time.monotonic()
        for _ in range(3):
            text = client.command("sv_hostname;sv_maxclients")
            self.assertEqual(parse_dvars(text), {"sv_hostname": "FakeServer", "sv_maxclients": "4"})
        self.assertGreaterEqual(time.monotonic() - start, 1.0)
        self.assertEqual(self.server.dropped, 0)

    def test_bad_password(self):
        client = protocol.RconClient(self.server.addr, "nope")
        # protocol.py's texts are English with a French table: ZmAdmin shows them in French
        with self.assertRaisesRegex(protocol.RconAuthError, "mot de passe rcon refusé"):
            client.command("status")
        client.close()

    def test_no_server(self):
        free = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        free.bind(("127.0.0.1", 0))
        addr = free.getsockname()
        free.close()
        with self.assertRaises(protocol.RconTimeout):
            protocol.query_status(addr, timeout=0.3)
        client = protocol.RconClient(addr, "test", timeout=0.3)
        with self.assertRaises(protocol.RconTimeout):
            client.command("status")
        client.close()

    def test_modinfo(self):
        mods = protocol.query_modinfo(self.server.addr)
        self.assertFalse(mods.refused)
        self.assertEqual(mods.args(), ["+set", "fs_game", "mods/mapkit", "+set", "fs_mods", "mapkit bo2weapons",
                                       "+set", "bo1_mod_zones", "zombie_bo2transit zombie_cosmodrome zombie_bo2fx",
                                       "+set", "bo1_bspworld", "maps/zombie_bo2transit.d3dbsp",
                                       "+set", "bo1_mod_mapkit", "bo2_zm_transit_bsp"])
        # a server with a player password answers only to it
        self.server.dvars["g_password"] = "secret"
        self.assertTrue(protocol.query_modinfo(self.server.addr, "wrong").refused)
        self.assertEqual(protocol.query_modinfo(self.server.addr, "secret").get("fs_mods"), "mapkit bo2weapons")
        self.assertEqual(protocol.modinfo_request("secret"), OOB + b'getmodinfo "secret"')
        # a server with nothing to load: an empty list, and other dvars of an answer are ignored
        none = protocol.parse_modinfo(OOB + b"modinfoResponse\n\\sv_hostname\\x\n")
        self.assertEqual((none.refused, none.args()), (False, []))
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_modinfo(OOB + b"statusResponse\n")

    def test_modinfo_no_answer(self):
        # an older server ignores getmodinfo
        free = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        free.bind(("127.0.0.1", 0))
        self.addCleanup(free.close)
        with self.assertRaises(protocol.RconTimeout):
            protocol.query_modinfo(free.getsockname(), timeout=0.3)

    def test_parse_target(self):
        self.assertEqual(protocol.parse_target("10.0.0.5"), ("10.0.0.5", 3074))
        self.assertEqual(protocol.parse_target("10.0.0.5:29070"), ("10.0.0.5", 29070))
        with self.assertRaises(ValueError):
            protocol.parse_target("10.0.0.5:x")


class ParserTest(unittest.TestCase):
    def test_zm_admin(self):
        rep = parse_zm_admin(ZM_ADMIN)
        self.assertEqual(rep.settings["zm_startperks"], "jugg")
        self.assertEqual(rep.players[0].flags, ["god"])
        self.assertEqual((rep.players[1].name, rep.players[1].state, rep.players[1].health), ("Bravo the second", "down", 12))
        self.assertEqual(rep.players[1].flags, ["notarget", "frozen"])
        self.assertEqual(rep.players[2].state, "loading")
        self.assertIsNone(parse_zm_admin('Unknown command "zm_admin"\n'))

    def test_dvars_latched(self):
        text = '"sv_maxclients" is: "4^7" default: "18^7"\nlatched: "8"\n    Domain is any integer from 1 to 32\n'
        self.assertEqual(parse_dvars(text), {"sv_maxclients": "8"})

    def test_merge_drops_left_players(self):
        st = protocol.parse_status(OOB + b'statusResponse\n\\sv_maxclients\\4\n0 500 31 5 "Alpha"\n')
        rows = merge_players(st, parse_zm_admin(ZM_ADMIN))
        self.assertEqual([(r.slot, r.display_state, r.health) for r in rows], [(0, "playing", 100)])


class FormTest(unittest.TestCase):
    def test_pending_commands_and_check(self):
        form = Form()
        form.load({"sv_hostname": "A", "rcon_password": "old", "sv_maxclients": "4", "fs_mods": "",
                   "zm_startperks": "jugg revive"})
        form.set("sv_hostname", "B")
        form.set("zm_startperks", "revive jugg")      # same perks in another order: no change
        form.set("rcon_password", "new")
        form.set("sv_maxclients", "8")
        self.assertEqual(set(form.edits), {"sv_hostname", "rcon_password", "sv_maxclients"})
        self.assertEqual(form.commands(reset=True), ['set sv_hostname "B"', 'set sv_maxclients "8"',
                                                     'set rcon_password "new"', "zm_reset"])
        form.set("fs_mods", "horde")
        self.assertEqual(form.commands(reset=True)[-1], 'zm_mods "horde"')
        form.check({"sv_hostname": "B", "sv_maxclients": "4", "rcon_password": "new"},
                   names=["sv_hostname", "sv_maxclients", "rcon_password"])
        self.assertEqual(form.status["sv_hostname"][0], APPLIED)
        self.assertEqual(form.status["sv_maxclients"][0], REFUSED)
        self.assertEqual(set(form.edits), {"sv_maxclients", "fs_mods"})

    def test_validation(self):
        form = Form()
        for name, value in [("sv_maxclients", "40"), ("zm_startpoints", "abc"), ("rcon_password", ""),
                            ("rcon_password", "a b"), ("sv_hostname", 'a"b'), ("zm_jip_mode", "later")]:
            with self.assertRaises(ValueError, msg=(name, value)):
                form.set(name, value)

    def test_server_cfg(self):
        text = ('// my server\nset sv_hostname "Old"\nset g_password ""\nseta sv_hostname "Older"\n'
                "devmap zombie_theater\n")
        out = update_server_cfg(text, {"sv_hostname": "New", "zm_startpoints": "1500"})
        self.assertEqual(out, '// my server\nset sv_hostname "New"\nset g_password ""\n'
                              'set zm_startpoints "1500"\ndevmap zombie_theater\n')


class LinkTest(unittest.TestCase):
    def test_events(self):
        server = FakeServer()
        link = ServerLink("127.0.0.1", server.addr[1], "test", status_every=0.2, admin_every=0.6)
        link.admin_wanted = True
        link.send("zm_god 0", tag="action")
        seen = {}
        end = time.monotonic() + 5
        while time.monotonic() < end and len(seen) < 3:
            try:
                ev = link.events.get(timeout=0.1)
            except Exception:
                continue
            seen.setdefault(ev[0], ev)
        link.close()
        server.stop()
        self.assertIsNotNone(seen["status"][1])
        self.assertEqual(seen["reply"][1:3], ("action", "zm_god 0"))
        self.assertEqual(seen["admin"][1].players[0].name, "Alpha")
        self.assertIn("zm_admin", server.commands)

    def test_offline_then_back(self):
        server = FakeServer()
        port = server.addr[1]
        server.stop()
        link = ServerLink("127.0.0.1", port, "test", status_every=0.2)
        time.sleep(1.2)
        self.assertFalse(link.online)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))
        sock.settimeout(2)
        data, src = sock.recvfrom(100)
        self.assertEqual(data, OOB + b"getstatus")
        sock.sendto(OOB + b'statusResponse\n\\sv_hostname\\X\n', src)
        time.sleep(0.3)
        self.assertTrue(link.online)
        sock.close()
        link.close()


class LogTailTest(unittest.TestCase):
    def test_follow_and_truncate(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "console_mp.log")
            with open(path, "w") as f:
                f.write("x" * 100 + "\nold line\n")
            tail = LogTail(path, history=12)
            self.assertEqual(tail.poll(), ["old line"])   # the cut line before it is dropped
            with open(path, "a") as f:
                f.write("new 1\nnew")
            self.assertEqual(tail.poll(), ["new 1"])
            with open(path, "a") as f:
                f.write(" 2\n")
            self.assertEqual(tail.poll(), ["new 2"])
            with open(path, "w") as f:
                f.write("restart\n")
            self.assertEqual(tail.poll(), ["restart"])
            tail.close()

    def test_read_error_retried(self):
        # WSL's /mnt/c gives ENODATA now and then on a read of a file another process is appending to
        class FailOnce:
            def __init__(self, f):
                self.f, self.failed = f, False

            def read(self, *args):
                if not self.failed:
                    self.failed = True
                    raise OSError(errno.ENODATA, "No data available")
                return self.f.read(*args)

            def __getattr__(self, name):
                return getattr(self.f, name)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "console_mp.log")
            with open(path, "w") as f:
                f.write("one\n")
            tail = LogTail(path)
            self.assertEqual(tail.poll(), ["one"])
            with open(path, "a") as f:
                f.write("two\n")
            tail._file = FailOnce(tail._file)
            self.assertEqual(tail.poll(), [])
            self.assertEqual(tail.poll(), ["two"])
            tail.close()


class LauncherTest(unittest.TestCase):
    def test_command_matches_server_script(self):
        with tempfile.TemporaryDirectory() as d:
            for name in (launcher.EXE_NAME, launcher.SCRIPT_NAME):
                open(os.path.join(d, name), "w").close()
            os.mkdir(os.path.join(d, "zone"))
            dist = launcher.find_dist(d)
            self.assertIsNotNone(dist)
            cmd = launcher.server_command(dist, {"map": "zombie_moon", "zinfo": False}, 3080, "pw")
        root = os.path.abspath(d)
        # as server.sh / Server.bat (tools/make_dist.sh), plus the rcon password and no curses console
        self.assertEqual(cmd, [os.path.join(root, launcher.EXE_NAME), "+set", "fs_b", root,
                               "+set", "fs_h", os.path.join(root, "server"), "+set", "bo1_server", "1",
                               "+set", "net_ip", "0.0.0.0", "+set", "net_port", "3080", "+set", "bo1_tui", "0",
                               "+set", "rcon_password", "pw", "+rcon_password", "pw", "+devmap", "zombie_moon"])

    def test_not_a_dist(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(launcher.find_dist(d))

    def test_bo2_weapons(self):
        with tempfile.TemporaryDirectory() as d:
            for name in (launcher.EXE_NAME, launcher.SCRIPT_NAME):
                open(os.path.join(d, name), "w").close()
            for mod in ("zone", "mods/admin", "mods/bo2weapons"):
                os.makedirs(os.path.join(d, mod))
            dist = launcher.find_dist(d)
            self.assertFalse(dist.bo2_weapons())
            open(os.path.join(d, "mods", "bo2weapons", "mod.ff"), "w").close()
            self.assertTrue(dist.bo2_weapons())
            cmd = launcher.server_command(dist, {"map": "zombie_moon", "zinfo": False, "bo2_weapons": 3}, 3080, "pw")
            plain = launcher.server_command(dist, {"map": "zombie_moon"}, 3080, "pw")
        line = " ".join(cmd)
        self.assertIn("+set rcon_password pw +set fs_mods bo2weapons +set bo2weapons_box 2 +rcon_password pw", line)
        self.assertTrue(line.endswith("+devmap zombie_moon"))
        self.assertNotIn("fs_game", line)
        self.assertNotIn("bo2weapons", " ".join(plain))

    def test_dual_wield(self):
        with tempfile.TemporaryDirectory() as d:
            for name in (launcher.EXE_NAME, launcher.SCRIPT_NAME):
                open(os.path.join(d, name), "w").close()
            for mod in ("zone", "mods/dualwield"):
                os.makedirs(os.path.join(d, mod))
            dist = launcher.find_dist(d)
            self.assertFalse(dist.dual_wield())
            open(os.path.join(d, "mods", "dualwield", "mod.ff"), "w").close()
            self.assertTrue(dist.dual_wield())
            game = {"map": "zombie_theater", "zinfo": False, "dual_wield": True}
            both = " ".join(launcher.server_command(dist, dict(game, bo2_weapons=1), 3080, "pw"))
            alone = " ".join(launcher.server_command(dist, game, 3080, "pw"))
        self.assertIn("+set fs_mods bo2weapons dualwield +set bo2weapons_box 0 +rcon_password pw", both)
        self.assertIn("+set rcon_password pw +set fs_mods dualwield +rcon_password pw", alone)

    def test_mapkit_and_mods(self):
        """A native Black Ops II map with mods: the solo line's mod part, then the map's base bsp; its clients load
        what the server's getmodinfo would say (gamemods.client_values)."""
        with tempfile.TemporaryDirectory() as d:
            for name in (launcher.EXE_NAME, launcher.SCRIPT_NAME):
                open(os.path.join(d, name), "w").close()
            for folder in ("zone", "mods/mapkit/layouts", "usermaps/zombie_bo2transit", "usermaps/zombie_bo2fx",
                           "main/maps", "mods/bo2weapons"):
                os.makedirs(os.path.join(d, folder))
            with open(os.path.join(d, "mods", "mapkit", "layouts", "bo2_zm_transit_bsp.json"), "w") as f:
                f.write('{"base": "zombie_pentagon"}')
            dist = launcher.find_dist(d)
            game = {"map": "mapkit:bo2_zm_transit_bsp", "hitmarker": True, "spawn_rate": 2, "bo2_weapons": 1}
            line = " ".join(launcher.server_command(dist, game, 3080, "pw"))
            values = gamemods.client_values(launcher.server_game(game), dist.root)
            missing = gamemods.missing_files(values, dist.root)
        self.assertIn("+set fs_game mods/mapkit +set bo1_mod_mapkit bo2_zm_transit_bsp +set fs_mods mapkit zinfo "
                      "hitmarker spawnrate bo2weapons +set bo1_mod_zones zombie_bo2transit zombie_cosmodrome "
                      "zombie_bo2fx +set bo1_bspworld maps/zombie_bo2transit.d3dbsp", line)
        self.assertIn("+set spawnrate_mult 2", line)
        self.assertNotIn("bo1_mod_quickrestart", line)
        self.assertTrue(line.endswith("+rcon_password pw +devmap zombie_pentagon"))
        self.assertEqual(values, {"fs_game": "mods/mapkit", "bo1_mod_mapkit": "bo2_zm_transit_bsp",
                                  "fs_mods": "mapkit zinfo hitmarker spawnrate bo2weapons",
                                  "bo1_mod_zones": "zombie_bo2transit zombie_cosmodrome zombie_bo2fx",
                                  "bo1_bspworld": "maps/zombie_bo2transit.d3dbsp"})
        # the files a client of that server must have: the two zones, the world, the BO2 weapons' mod.ff
        self.assertEqual(sorted(missing), sorted([os.path.join("mods", "bo2weapons", "mod.ff"),
                                                  os.path.join("usermaps", "zombie_bo2transit", "zombie_bo2transit.ff"),
                                                  os.path.join("usermaps", "zombie_bo2fx", "zombie_bo2fx.ff"),
                                                  os.path.join("main", "maps", "zombie_bo2transit.d3dbsp")]))



class OpenBSDTest(unittest.TestCase):
    """The OpenBSD package: one program per ABI, found as bo1_program.sh finds it, and no /proc to check a PID."""

    def test_flavor(self):
        f = launcher.openbsd_flavor
        self.assertEqual(f(env={"BO1_OPENBSD": "current"}, kern_version="OpenBSD 8.0 (GENERIC.MP) #1: ...\n"),
                         "current")
        self.assertEqual(f(env={}, kern_version="OpenBSD 8.0-current (GENERIC.MP) #12: ...\n    deraadt@\n",
                           release="8.0"), "current")
        self.assertEqual(f(env={}, kern_version="OpenBSD 8.1-beta (GENERIC.MP) #3: ...\n", release="8.1"), "current")
        self.assertEqual(f(env={}, kern_version="OpenBSD 8.0 (GENERIC.MP) #1: ...\n", release="8.0"), "8.0")
        self.assertEqual(f(env={}, kern_version="", release="8.0"), "8.0")

    def test_program_name(self):
        self.assertEqual(launcher.program_name("linux"), "BO1Zombies")
        self.assertEqual(launcher.program_name("win32"), "BO1Zombies.exe")
        self.assertEqual(launcher.program_name("openbsd8", env={}, kern_version="OpenBSD 8.0 (GENERIC.MP)\n",
                                               release="8.0"), "BO1Zombies-8.0")
        self.assertEqual(launcher.program_name("openbsd8", env={"BO1_OPENBSD": "current"}), "BO1Zombies-current")

    def test_dist_with_the_flavor_program(self):
        saved = launcher.EXE_NAME
        launcher.EXE_NAME = "BO1Zombies-8.0"
        try:
            with tempfile.TemporaryDirectory() as d:
                for name in ("BO1Zombies-current", "server.sh"):
                    open(os.path.join(d, name), "w").close()
                os.mkdir(os.path.join(d, "zone"))
                self.assertIsNone(launcher.find_dist(d))       # only the other ABI's program
                open(os.path.join(d, "BO1Zombies-8.0"), "w").close()
                dist = launcher.find_dist(d)
                self.assertEqual(dist.exe, os.path.join(os.path.abspath(d), "BO1Zombies-8.0"))
        finally:
            launcher.EXE_NAME = saved

    @unittest.skipIf(os.name == "nt", "ps and sleep")
    def test_pid_runs_by_command_name(self):
        """A real process through ps -o comm= (Linux's ps answers it too; its names stop at 15 characters)."""
        import shutil
        import subprocess
        saved = launcher.IS_OPENBSD
        launcher.IS_OPENBSD = True
        launcher._COMM_CACHE.clear()
        try:
            with tempfile.TemporaryDirectory() as d:
                exe = os.path.join(d, "BO1Zombies-8.0")
                shutil.copy(shutil.which("sleep"), exe)
                os.chmod(exe, 0o755)
                proc = subprocess.Popen([exe, "30"])
                try:
                    self.assertTrue(launcher.pid_runs(proc.pid, exe))
                    self.assertFalse(launcher.pid_runs(proc.pid, os.path.join(d, "BO1Zombies-current")))
                finally:
                    proc.kill()
                    proc.wait()
                # a dead PID stops counting at once, though ps's cached answer still stands; past its lifetime ps
                # finds no process
                self.assertFalse(launcher.pid_runs(proc.pid, exe))
                self.assertEqual(launcher._pid_comm(proc.pid), "BO1Zombies-8.0")
                self.assertIsNone(launcher._pid_comm(proc.pid, now=time.monotonic() + launcher._COMM_TTL + 1))
        finally:
            launcher.IS_OPENBSD = saved
            launcher._COMM_CACHE.clear()

    def test_hint_only_on_openbsd(self):
        saved = launcher.IS_OPENBSD
        try:
            launcher.IS_OPENBSD = False
            self.assertEqual(launcher.missing_program_hint(), "")
            launcher.IS_OPENBSD = True
            self.assertIn("BO1_OPENBSD", launcher.missing_program_hint())
        finally:
            launcher.IS_OPENBSD = saved

class LaunchDialogTest(unittest.TestCase):
    """ZmAdmin's local server launch, dialog by dialog, on a fake app: map, mods, then the choices that apply."""

    class FakeApp:
        def __init__(self, dist):
            from zmadmin.config import Config
            self.dist = dist
            self.config = Config(os.path.join(dist.root, "cfg"))
            self.locals = {}
            self.modals, self.launched, self.messages = [], [], []

        def profile_names(self):
            return [n for n, _ in self.config.local_profiles(self.dist.root)]

        def profile(self, name):
            return self.config.local_profile(self.dist.root, name)

        def local(self, name):
            return self.locals.setdefault(name, launcher.LocalServer(self.dist, name))

        def open(self, dialog):
            self.modals.append(dialog)

        def msg(self, text, *_):
            self.messages.append(text)

        def launch_local(self, name):
            local = self.profile(name)
            self.launched.append((name, dict(local["game"]), local["port"], local["password"]))

    def test_flow(self):
        from zmadmin.views import ServersView
        from zmadmin.widgets import ChoiceDialog, FormDialog
        with tempfile.TemporaryDirectory() as d:
            for name in (launcher.EXE_NAME, launcher.SCRIPT_NAME):
                open(os.path.join(d, name), "w").close()
            for folder in ("zone", "mods/mapkit/layouts", "mods/bo2weapons", "usermaps/zombie_bo2transit",
                           "usermaps/zombie_bo2fx", "main/maps"):
                os.makedirs(os.path.join(d, folder))
            for f in ("mods/bo2weapons/mod.ff", "usermaps/zombie_bo2transit/zombie_bo2transit.ff",
                      "usermaps/zombie_bo2fx/zombie_bo2fx.ff", "main/maps/zombie_bo2transit.d3dbsp"):
                open(os.path.join(d, f), "w").close()
            with open(os.path.join(d, "mods", "mapkit", "layouts", "bo2_zm_transit_bsp.json"), "w") as f:
                f.write('{"base": "zombie_pentagon"}')
            gamemods.mapkit_layouts.cache_clear()
            app = self.FakeApp(launcher.find_dist(d))
            ServersView(app).configure_dialog("default", launch=True)
            maps = app.modals.pop()
            self.assertIsInstance(maps, ChoiceDialog)
            self.assertIn("mapkit:bo2_zm_transit_bsp", [v for v, _, _ in maps.items])
            maps.on_pick("mapkit:bo2_zm_transit_bsp")
            mods = app.modals.pop()
            self.assertIsInstance(mods, ChecklistDialog)
            mods.on_ok(["zinfo", "hitmarker", "horde"])
            titles = []
            while True:
                dialog = app.modals.pop()
                if isinstance(dialog, FormDialog):
                    break
                titles.append(dialog.title)
                values = [v for v, _, _ in dialog.items]
                # the horde's size 256, the spawn speed 3, BO2's weapons alone in the box
                dialog.on_pick({"Horde : zombies à la fois": 256, "Vitesse d'apparition des zombies": 3,
                                "Armes de Black Ops II": 3}.get(dialog.title, values[0]))
            # no difficulty on a MapKit map, no dual wield without its mod.ff
            self.assertEqual(titles, ["Horde : zombies à la fois", "Vitesse d'apparition des zombies",
                                      "Armes de Black Ops II"])
            self.assertTrue(dialog.submit())
            name, game, port, password = app.launched[0]
            self.assertEqual(name, "default")
            self.assertEqual(port, 3074)
            self.assertEqual((game["map"], game["horde"], game["horde_max"], game["spawn_rate"], game["bo2_weapons"],
                              game["hitmarker"], game["noperks"]),
                             ("mapkit:bo2_zm_transit_bsp", True, 256, 3, 3, True, False))
            # kept for the next launch
            self.assertEqual(app.config.local_settings(d)["game"]["horde_max"], 256)
            line = " ".join(launcher.server_command(app.dist, game, port, password))
        gamemods.mapkit_layouts.cache_clear()
        self.assertIn("+set fs_mods mapkit horde zinfo hitmarker spawnrate bo2weapons", line)
        self.assertIn("+set bo1_mod_mapkit bo2_zm_transit_bsp", line)
        self.assertIn("+set horde_max_zombies 256", line)

    def test_older_settings(self):
        from zmadmin.profiles import local_game, profile_configured
        self.assertFalse(profile_configured({"map": "zombie_moon", "port": 3074}))
        self.assertTrue(profile_configured({"map": "zombie_moon", "bo2_box": 1}))
        self.assertEqual(local_game({"map": "zombie_moon", "bo2_box": 1, "dual_wield": True}),
                         {"map": "zombie_moon", "bo2_weapons": 2, "dual_wield": True})
        self.assertEqual(local_game({"map": "zombie_moon"})["bo2_weapons"], 0)


def make_dist(d):
    for name in (launcher.EXE_NAME, launcher.SCRIPT_NAME):
        open(os.path.join(d, name), "w").close()
    os.makedirs(os.path.join(d, "zone"), exist_ok=True)
    return launcher.find_dist(d)


def free_udp_port():
    """An even port whose port + 1 is free too (a server takes both)."""
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("0.0.0.0", 0))
            port = s.getsockname()[1]
        if port % 2 == 0 and port < 65534 and launcher.port_in_use(port) is None:
            return port
    raise unittest.SkipTest("no free UDP port pair")


class ProfilesTest(unittest.TestCase):
    """Several local servers of one folder: profiles in servers.json, their folders, ports and kept settings."""

    def test_config_profiles(self):
        import json
        from zmadmin.config import Config
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "dist")
            cfg = os.path.join(d, "cfg")
            os.makedirs(cfg)
            # a servers.json of the ZmAdmin before profiles: its local server is the default profile
            key = os.path.normcase(os.path.abspath(root))
            with open(os.path.join(cfg, "servers.json"), "w") as f:
                json.dump({"servers": [], "local": {key: {"password": "old", "port": 3075,
                                                          "map": "zombie_moon", "game": {"map": "zombie_moon"}}}}, f)
            config = Config(cfg)
            self.assertEqual([(n, e["password"]) for n, e in config.local_profiles(root)], [("default", "old")])
            self.assertIs(config.local_settings(root), config.local_profile(root, "default"))
            # 3074 and 3076 touch 3075 (port + 1 is the clients' logs): the next one, by steps of 2, is 3078
            self.assertEqual(config.next_port(root), 3078)
            config.add_profile(root, "kino")
            self.assertEqual(config.local_profile(root, "kino")["port"], 3078)
            self.assertEqual(config.next_port(root), 3080)
            for bad in ("Kino", "default", "a b", "", "x" * 33, "five/hard"):
                self.assertIsNotNone(config.check_profile_name(root, bad), bad)
            self.assertIsNone(config.check_profile_name(root, "five_hard-2"))
            with self.assertRaises(ValueError):
                config.add_profile(root, "KINO")
            with self.assertRaises(ValueError):
                config.remove_profile(root, "default")
            config.local_profile(root, "kino")["settings"] = {"sv_hostname": "Kino"}
            config.save()
            again = Config(cfg)
            self.assertEqual([n for n, _ in again.local_profiles(root)], ["default", "kino"])
            self.assertEqual(again.local_profile(root, "kino")["settings"], {"sv_hostname": "Kino"})
            self.assertNotEqual(again.local_profile(root, "kino")["password"], "old")
            again.remove_profile(root, "kino")
            self.assertIsNone(again.local_profile(root, "kino"))

    def test_server_homes(self):
        with tempfile.TemporaryDirectory() as d:
            dist = make_dist(d)
            root = os.path.abspath(d)
            kino = dist.server_home("kino")
            self.assertEqual(dist.server_home("default").log, dist.log)
            self.assertEqual(kino.log, os.path.join(root, "servers", "kino", "main", "console_mp.log"))
            cmd = launcher.server_command(dist, {"map": "zombie_moon"}, 3080, "pw", kino)
            self.assertEqual(launcher.LocalServer(dist, "kino").home.state_path,
                             os.path.join(root, "servers", "kino", "main", "zmadmin_server.json"))
        self.assertEqual(cmd[cmd.index("fs_h") + 1], os.path.join(root, "servers", "kino"))
        self.assertEqual(cmd[cmd.index("fs_b") + 1], root)

    def test_port_in_use(self):
        port = free_udp_port()
        self.assertIsNone(launcher.port_in_use(port))
        for taken in (port, port + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind(("0.0.0.0", taken))
                why = launcher.port_in_use(port)
            self.assertIn(str(taken), why or "")

    def test_kept_settings_and_server_cfg(self):
        from zmadmin.settings import build_server_cfg, kept_settings
        applied = {"zm_startpoints": "500", "rcon_password": "new", "fs_mods": "hitmarker", "sv_hostname": "Kino"}
        self.assertEqual(kept_settings(applied, local=True), {"zm_startpoints": "500", "sv_hostname": "Kino"})
        self.assertEqual(kept_settings(applied, local=False),
                         {"zm_startpoints": "500", "sv_hostname": "Kino", "fs_mods": "hitmarker"})
        fresh = build_server_cfg(None, {"zm_startpoints": "500", "sv_hostname": "Kino"}, "kino")
        self.assertEqual(fresh.splitlines()[1:], ['set sv_hostname "Kino"', 'set zm_startpoints "500"'])
        self.assertIn("profile kino", fresh.splitlines()[0])
        mine = "// mine\nset g_inactivity 60\nset sv_hostname old\nexec more.cfg\n"
        self.assertEqual(build_server_cfg(mine, {"sv_hostname": "Kino"}, "kino"),
                         '// mine\nset g_inactivity 60\nset sv_hostname "Kino"\nexec more.cfg\n')
        self.assertEqual(build_server_cfg(mine, {}, "kino"), mine)

    def test_new_game_drops_what_its_line_sets(self):
        """server.cfg runs after the command line: choosing the game again drops the kept settings its line sets, or
        an old bo2weapons_box would silently replace the new choice."""
        from zmadmin import profiles
        with tempfile.TemporaryDirectory() as d:
            dist = make_dist(d)
            os.makedirs(os.path.join(d, "mods", "bo2weapons"))
            open(os.path.join(d, "mods", "bo2weapons", "mod.ff"), "w").close()
            home = dist.server_home("kino")
            local = {"settings": {"bo2weapons_box": "0", "sv_hostname": "Kino"}}
            self.assertIsNone(profiles.write_profile_cfg(home, local["settings"], "kino"))
            self.assertIn("bo2weapons_box", profiles.line_settings({"bo2_weapons": 3}, d))
            self.assertNotIn("bo2weapons_box", profiles.line_settings({"bo2_weapons": 0}, d))
            # a game without BO2 weapons sets no box: the kept one stays
            self.assertIsNone(profiles.configure_game(local, {"map": "zombie_moon"}, home, "kino", d))
            self.assertEqual(local["settings"], {"bo2weapons_box": "0", "sv_hostname": "Kino"})
            self.assertEqual(local["game"], {"map": "zombie_moon"})
            self.assertIsNone(profiles.configure_game(local, {"map": "zombie_moon", "bo2_weapons": 3}, home, "kino", d))
            self.assertEqual(local["settings"], {"sv_hostname": "Kino"})
            with open(home.server_cfg) as f:
                cfg = f.read()
        self.assertNotIn("bo2weapons_box", cfg)
        self.assertIn('set sv_hostname "Kino"', cfg)

    def test_start_profile(self):
        from zmadmin import profiles
        from zmadmin.config import Config
        started = []
        real_start, real_running = launcher.LocalServer.start, launcher.LocalServer.running
        launcher.LocalServer.start = lambda self, game, port, pw: started.append((self.profile, game, port, pw))
        try:
            with tempfile.TemporaryDirectory() as d:
                dist = make_dist(d)
                config = Config(os.path.join(d, "cfg"))
                self.assertIn("pas de profil", profiles.start_profile(config, dist, launcher.LocalServer(dist, "x"), "x"))
                kino = config.add_profile(dist.root, "kino")
                kino.update(game={"map": "zombie_theater"}, settings={"sv_hostname": "Kino"})
                self.assertIsNone(profiles.start_profile(config, dist, launcher.LocalServer(dist, "kino"), "kino"))
                with open(dist.server_home("kino").server_cfg) as f:
                    self.assertIn('set sv_hostname "Kino"', f.read())
                self.assertFalse(os.path.exists(dist.server_cfg))       # default's is not touched
                self.assertEqual(started, [("kino", {"map": "zombie_theater"}, kino["port"], kino["password"])])
                # a running neighbour one port away: its port + 1 would be this one's
                config.local_settings(dist.root)["port"] = kino["port"] - 1
                launcher.LocalServer.running = lambda self: self.profile == "default"
                why = profiles.start_profile(config, dist, launcher.LocalServer(dist, "kino"), "kino")
                self.assertIn("default", why)
        finally:
            launcher.LocalServer.start, launcher.LocalServer.running = real_start, real_running

    def test_cli_start_and_list(self):
        import contextlib
        import io
        from zmadmin import cli
        from zmadmin.config import Config
        started = []
        real_start = launcher.LocalServer.start

        def fake_start(self, game, port, pw):
            started.append(self.profile)
            self.pid, self.port, self.map = 4242, port, game["map"]
        launcher.LocalServer.start = fake_start
        try:
            with tempfile.TemporaryDirectory() as d:
                dist = make_dist(d)
                cfg = os.path.join(d, "cfg")
                config = Config(cfg)
                config.add_profile(dist.root, "kino")["game"] = {"map": "zombie_theater"}
                config.add_profile(dist.root, "fresh")
                config.save()
                base = ["--dist", d, "--config", cfg]
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(cli.main(base + ["--start", "nope", "--detach"]), 2)
                    self.assertEqual(cli.main(base + ["--start", "fresh", "--detach"]), 2)
                    self.assertEqual(cli.main(base + ["--start", "kino", "--detach"]), 0)
                    self.assertEqual(cli.main(base + ["--list-profiles"]), 0)
                self.assertEqual(started, ["kino"])
                self.assertIn("no profile 'nope'", err.getvalue())
                self.assertIn("never set up", err.getvalue())
                self.assertIn("kino: started, PID 4242, port 3076", out.getvalue())
                listing = out.getvalue().split(":\n", 1)[1]
                self.assertEqual([line.split()[0] for line in listing.splitlines()], ["default", "fresh", "kino"])
        finally:
            launcher.LocalServer.start = real_start

    def test_new_profile_dialog(self):
        from zmadmin.views import ServersView
        from zmadmin.widgets import ChoiceDialog, InputDialog
        with tempfile.TemporaryDirectory() as d:
            app = LaunchDialogTest.FakeApp(make_dist(d))
            view = ServersView(app)
            view.key("n")
            ask = app.modals.pop()
            self.assertIsInstance(ask, InputDialog)
            ask.edits[0].set("default")
            self.assertFalse(ask.submit())
            ask.edits[0].set("kino")
            self.assertTrue(ask.submit())
            self.assertIsNotNone(app.profile("kino"))
            self.assertEqual(view.entries()[view.sel], ("local", "kino"))
            self.assertIsInstance(app.modals.pop(), ChoiceDialog)       # its map, then the rest of the chain
            view.key("x")
            app.modals.pop().on_yes(False)
            self.assertIsNone(app.profile("kino"))


class KeepSettingsTest(unittest.TestCase):
    """Settings Save applied go to the profile they were sent to, and its server.cfg."""

    def test_keep(self):
        from zmadmin.app import App
        from zmadmin.config import Config

        class Fake:
            keep_settings = App.keep_settings
            write_cfg = App.write_cfg

            def __init__(self, d):
                self.dist = make_dist(d)
                self.config = Config(os.path.join(d, "cfg"))
                self.config.add_profile(self.dist.root, "kino")
                self.messages, self.lines = [], []
                self.console = type("C", (), {"add": lambda _, line, *a: self.lines.append(line)})()

            def profile(self, name):
                return self.config.local_profile(self.dist.root, name)

            def local(self, name):
                return launcher.LocalServer(self.dist, name)

            def msg(self, text, *_):
                self.messages.append(text)

        with tempfile.TemporaryDirectory() as d:
            app = Fake(d)
            app.connected_to = ("local", "kino")
            app.keep_settings({"sv_hostname": "Kino", "rcon_password": "x", "fs_mods": "hitmarker"})
            self.assertEqual(app.profile("kino")["settings"], {"sv_hostname": "Kino"})
            with open(app.dist.server_home("kino").server_cfg) as f:
                self.assertIn('set sv_hostname "Kino"', f.read())
            remote = {"name": "far", "host": "10.0.0.2", "port": 3074, "password": "p"}
            app.connected_to = ("saved", remote)
            app.keep_settings({"fs_mods": "hitmarker"})
            self.assertEqual(remote["settings"], {"fs_mods": "hitmarker"})
            with open(os.path.join(d, "cfg", "servers.json")) as f:
                self.assertIn('"sv_hostname": "Kino"', f.read())
            self.assertEqual(app.messages, [])


class MouseTest(unittest.TestCase):
    def test_kinds(self):
        import curses
        self.assertEqual(mouse_kind(curses.BUTTON1_CLICKED), "click")
        self.assertEqual(mouse_kind(curses.BUTTON1_RELEASED), "click")
        self.assertEqual(mouse_kind(curses.BUTTON1_DOUBLE_CLICKED), "double")
        # a press alone does nothing: its release (or the merged click) acts, so a click never acts twice
        self.assertIsNone(mouse_kind(curses.BUTTON1_PRESSED))
        if getattr(curses, "BUTTON4_PRESSED", 0):
            self.assertEqual(mouse_kind(curses.BUTTON4_PRESSED), "up")

    def test_hitmap(self):
        hits, calls = HitMap(), []
        hits.add(3, 10, 5, lambda: calls.append("a"), lambda: calls.append("A"))
        hits.add(3, 12, 2, lambda: calls.append("b"))
        hits.add(4, 0, 0, lambda: calls.append("empty"))
        self.assertIsNone(hits.dispatch(3, 9, "click"))
        self.assertIsNone(hits.dispatch(3, 15, "click"))
        hits.dispatch(3, 10, "click")
        hits.dispatch(3, 11, "double")
        hits.dispatch(3, 12, "click")      # the zone added last wins
        hits.dispatch(3, 13, "double")     # no double action: its click runs
        hits.dispatch(4, 0, "click")
        self.assertEqual(calls, ["a", "A", "b", "b"])
        hits.clear()
        self.assertIsNone(hits.find(3, 10))

    def test_dialog_zones(self):
        said = []
        d = ConfirmDialog("t", ["?"], said.append, checkbox="box")
        d.origin = (5, 7)
        d.zone(2, 2, 7, d.yes)
        d.zone(1, 2, 7, d.toggle)
        self.assertFalse(d.mouse(6, 9, "click"))   # the checkbox: ticked, dialog stays
        self.assertFalse(d.mouse(0, 0, "click"))   # outside every zone
        self.assertTrue(d.mouse(7, 12, "click"))   # Oui
        self.assertEqual(said, [True])
        c = ChecklistDialog("t", [("x", "X"), ("y", "Y")], [], said.append)
        c.tick(1)
        c.tick(0)
        c.tick(1)
        self.assertTrue(c.submit())
        self.assertEqual(said[-1], ["x"])


if __name__ == "__main__":
    unittest.main()
