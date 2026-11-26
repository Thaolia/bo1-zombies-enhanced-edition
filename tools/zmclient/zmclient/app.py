"""The curses application: the tab bar, the status line, the event loop, launching the game and the local server."""
import curses
import os
import threading
import time

from zmadmin.config import DEFAULT_PROFILE
from zmadmin.config import Config as AdminConfig
from zmadmin.i18n import set_language, tr
from zmadmin.launcher import LocalServer
from zmadmin.logtail import LogTail
from zmadmin.profiles import write_profile_cfg
from zmadmin.protocol import ProtocolError, RconClient, RconTimeout, query_modinfo
from zmadmin.widgets import (BTAB, CTRL_C, C_ERR, C_INFO, C_OK, C_TITLE, C_WARN, MOUSE_MASK, TAB, ConfirmDialog,
                             FormDialog, HitMap, MessageDialog, color, cursor, fill, init_colors, normalize_key, put,
                             read_mouse)

from . import gamesetup
from . import help as H
from .browser import Browser
from .client import Client
from .gamecfg import GameConfig
from .profile import (DEFAULT_PORT, build_command, fs_game, launch_env, map_label, solo_mod_flags, split_on, valid_host,
                      valid_password)
from .views import ConfigView, ExtraView, LaunchView, LogView, PlayView, ServersView, SetupView, SoloView

STOP_TIMEOUT = 15.0
MIN_H, MIN_W = 24, 80


class App:
    def __init__(self, scr, profile, dist, mouse=True, admin_config_dir=None):
        self.scr = scr
        self.mouse = mouse
        self.hits = HitMap()
        self.profile = profile
        set_language(profile["language"])
        self.dist = dist
        self.root = dist.root if dist else None
        self.client = Client(dist) if dist else None
        self.client2 = Client(dist, 2) if dist else None     # a split screen's second window
        self.local = LocalServer(dist) if dist else None
        # the last getmodinfo answer and the (host, port, password) it is for: a line for another server ignores it
        self._server_mods = None
        self._server_mods_for = None
        self.detect_note = ""
        # the local server's rcon password lives in ZmAdmin's servers.json, so ZmAdmin administers what ZmClient starts
        self.admin_config = AdminConfig(admin_config_dir)
        self.gamecfg = GameConfig(self.root) if dist else None
        self.browser = Browser(lambda: [(f["host"], int(f.get("port", DEFAULT_PORT)))
                                        for f in self.profile["favorites"]])
        self.browser.start()
        self.setup_job = None
        self.modals = []
        self.message = ("", 0, 0.0)
        self.running = True
        self.stopping = None        # deadline of a local server stop
        self.quit_after_stop = False
        self.client_was_running = bool(self.client and self.client.running())
        self.client2_was_running = bool(self.client2 and self.client2.running())
        self.server_was_running = bool(self.local and self.local.running())
        self.logtail = None
        self.log_path = None
        self.next_log_poll = 0.0
        self.next_log_pick = 0.0
        self.missing_cache = (0.0, None)
        self.views = [PlayView(self), ServersView(self), SoloView(self), LaunchView(self), ConfigView(self),
                      ExtraView(self), SetupView(self), LogView(self)]
        self.current = 0
        if self.dist and self.setup_missing():
            self.show(6)
            self.msg(tr('The game files are missing: choose your Black Ops install, then "Install".'), C_WARN)

    # ----------------------------------------------------------------------------------------------- helpers
    @property
    def view(self):
        return self.views[self.current]

    def msg(self, text, pair=C_INFO):
        self.message = (text, pair, time.monotonic())

    def open(self, dialog):
        self.modals.append(dialog)

    def show_help(self):
        self.open(MessageDialog(tr("Help: {title}").format(title=tr(self.view.title)),
                                H.VIEW_HELP[self.view.name] + [""] + H.global_help()))

    def show(self, index):
        self.current = index % len(self.views)
        self.view.on_show()

    def save_profile(self):
        try:
            self.profile.save()
        except OSError as e:
            self.msg(tr("profile.json not written: {error}").format(error=e), C_ERR)

    def setup_missing(self):
        """What the folder lacks to start the game (cached 2 s: it reads the folder), or None."""
        at, value = self.missing_cache
        if time.monotonic() - at > 2:
            value = gamesetup.ready(self.root) if self.dist else tr("no game folder")
            self.missing_cache = (time.monotonic(), value)
        return value

    def launch_cfg_text(self):
        try:
            with open(os.path.join(self.root, "launch.cfg"), encoding="latin-1") as f:
                return f.read().strip()
        except OSError:
            return ""

    def local_password(self):
        return self.admin_config.local_settings(self.root)["password"] if self.dist else ""

    def set_local_password(self, password):
        self.admin_config.local_settings(self.root)["password"] = password
        try:
            self.admin_config.save()
        except OSError as e:
            self.msg(tr("ZmAdmin's servers.json not written: {error}").format(error=e), C_ERR)

    def detect_server_mods(self):
        """Asks the server to join what its clients load (getmodinfo, with the player password): the answer, kept for
        that server, or None (detection off, no answer: an older server, or none there). self.detect_note says what
        it found, for the launch message."""
        p = self.profile
        self._server_mods, self._server_mods_for, self.detect_note = None, None, ""
        if p["mode"] != "join" or not p["join_detect_mods"]:
            return None
        target = (p["join_host"], int(p["join_port"]))
        try:
            mods = query_modinfo(target, p["join_password"], timeout=1.5)
        except RconTimeout:
            self.detect_note = tr("server mods: no answer (an older version?), manual choices")
            return None
        except OSError as e:
            self.detect_note = tr("server mods: {error}, manual choices").format(error=e)
            return None
        if mods.refused:
            self.detect_note = tr("server mods: password refused, manual choices")
            return None
        self._server_mods, self._server_mods_for = mods, self._join_key()
        world = mods.get("bo1_mod_mapkit")
        listed = mods.get("fs_mods") or tr("none")
        self.detect_note = (tr("server mods: {mods}, map {world}").format(mods=listed, world=world) if world
                            else tr("server mods: {mods}").format(mods=listed))
        return mods

    def _join_key(self):
        p = self.profile
        return p["join_host"], int(p["join_port"]), p["join_password"]

    @property
    def server_mods(self):
        """The detected settings of the server the profile joins, or None."""
        return self._server_mods if self._server_mods_for == self._join_key() else None

    def solo_flags(self):
        return solo_mod_flags(self.profile, self.root)

    def solo_summary(self):
        p = self.profile
        parts = []
        if p["horde"]:
            parts.append(tr("horde {max}, round {round}").format(max=p["horde_max"], round=p["horde_round"])
                         if p["horde_round"] > 1 else f"horde {p['horde_max']}")
        if p["difficulty"]:
            parts.append(H.DIFFICULTY_LABELS[p["difficulty"]])
        for key, label in (("god", "god"), ("zinfo", "zinfo"), ("noperks", "noperks"), ("quickrestart", "R restart")):
            if p[key]:
                parts.append(tr(label))
        if p["start_points"]:
            parts.append(f"{p['start_points']} points")
        if p["start_perks"]:
            n = len(p["start_perks"])
            parts.append((tr("{n} perks") if n > 1 else tr("{n} perk")).format(n=n))
        if p["start_power"]:
            parts.append(tr("power"))
        if p["start_pap"]:
            parts.append("Pack-a-Punch")
        if p["far_respawn"]:
            parts.append(tr("far zombies brought back > {distance}").format(distance=p["far_respawn"]))
        if p["bo2_weapons"]:
            parts.append(tr("BO2 weapons") if p["bo2_weapons"] == 1 else tr("BO2 weapons only"))
        if p["dual_wield"]:
            parts.append(tr("dual wield"))
        return ", ".join(parts) or tr("none")

    def command(self, player=1):
        """(argv, None) or (None, why the line cannot be built). player 2: a split screen's second window. A join
        uses the server's mods from the last detection (detect_server_mods)."""
        if not self.dist:
            return None, tr("no game folder")
        p = self.profile
        if p["mode"] == "host" and self.local.running() and self.local.port:
            # the running server's port wins: that is where it listens
            saved = p["host_port"]
            p["host_port"] = int(self.local.port)
            try:
                return build_command(p, self.dist.exe, self.root, self.launch_cfg_text(), player), None
            except ValueError as e:
                return None, str(e)
            finally:
                p["host_port"] = saved
        try:
            return build_command(p, self.dist.exe, self.root, self.launch_cfg_text(), player, self.server_mods), None
        except ValueError as e:
            return None, str(e)

    def clients_running(self):
        return self.client.running() or self.client2.running()

    # -------------------------------------------------------------------------------------------- the game
    def launch(self):
        if not self.dist:
            self.msg(tr("No game folder: put ZmClient next to BO1Zombies."), C_ERR)
            return
        missing = self.setup_missing()
        if missing:
            self.msg(tr("Cannot launch: {missing}. Setup view (F7).").format(missing=missing), C_ERR)
            self.show(6)
            return
        for c in (self.client, self.client2):
            if c.running():
                self.msg(tr("The game is already running (PID {pid}).").format(pid=c.pid), C_WARN)
                return
        p = self.profile
        split = split_on(p)
        self.detect_server_mods()
        # checked before a local server starts: a line that cannot run must not leave a server behind
        argv, err = self.command()
        argv2, err2 = self.command(2) if split else (None, None)
        if err or err2:
            text = (tr("Cannot launch: {error} ({note})") if self.detect_note else tr("Cannot launch: {error}"))
            self.msg(text.format(error=err or err2, note=self.detect_note), C_ERR)
            return
        if p["mode"] == "host" and not self.local.running():
            try:
                password = self.local_password()
                # a password local_settings just generated must reach servers.json, or ZmAdmin cannot use rcon
                self.admin_config.save()
                # the settings ZmAdmin keeps for the default profile come back at each start, as from ZmAdmin
                why = write_profile_cfg(self.local.home, self.admin_config.local_settings(self.root).get("settings")
                                        or {}, DEFAULT_PROFILE)
                if why:
                    raise RuntimeError(why)
                self.local.start(p.data, int(p["host_port"]), password)
            except (OSError, RuntimeError) as e:
                self.msg(tr("Local server not started: {error}").format(error=e), C_ERR)
                return
            self.server_was_running = True
            self.msg(tr("Local server started (PID {pid}) on port {port}.").format(pid=self.local.pid,
                                                                                     port=p["host_port"]), C_OK)
        game = fs_game(p, self.root, self.server_mods)
        if split:
            # player 2 first: the window started last takes the focus, which the keyboard and mouse player needs
            try:
                self.client2.start(argv2, game, launch_env(p))
            except (OSError, RuntimeError) as e:
                self.msg(tr("Player 2's window does not start: {error}").format(error=e), C_ERR)
                return
            self.client2_was_running = True
        try:
            self.client.start(argv, game, launch_env(p))
        except (OSError, RuntimeError) as e:
            if split:
                self.client2.kill()     # half a split screen is no use
            self.msg(tr("The game does not start: {error}").format(error=e), C_ERR)
            return
        self.client_was_running = True
        self.follow_log(self.client.log_path(game))
        if p["mode"] == "solo":
            what = map_label(p["map"], self.root)
        elif p["mode"] == "join":
            what = (tr("joins {host}:{port}; {note}") if self.detect_note else tr("joins {host}:{port}")).format(
                host=p["join_host"], port=p["join_port"], note=self.detect_note)
        else:
            what = tr("joins the local server ({map})").format(map=map_label(p["map"], self.root))
        if split:
            self.msg(tr("Split screen started (PID {pid} and {pid2}): {what}.").format(
                pid=self.client.pid, pid2=self.client2.pid, what=what), C_OK)
        else:
            self.msg(tr("Game started (PID {pid}): {what}.").format(pid=self.client.pid, what=what), C_OK)

    def join(self, host, port, password):
        p = self.profile
        p["mode"], p["join_host"], p["join_port"], p["join_password"] = "join", host, int(port), password
        self.save_profile()
        self.show(0)
        self.launch()

    def edit_join_target(self):
        p = self.profile

        def ok(v):
            host = v["host"].strip()
            if not valid_host(host):
                return tr("address: an IP or a host name")
            try:
                port = int(v["port"])
            except ValueError:
                return tr("port: a number")
            if not 1 <= port <= 65535:
                return tr("port: between 1 and 65535")
            if v["password"] and not valid_password(v["password"]):
                return tr('password: no blank, quote, ";" or "+"')
            p["join_host"], p["join_port"], p["join_password"] = host, port, v["password"]
            self.save_profile()
            return None
        self.open(FormDialog(tr("Server to join"), [
            ("host", tr("Address"), p["join_host"], tr("IP or host name"), False),
            ("port", "Port", p["join_port"], tr("3074 by default"), False),
            ("password", tr("Password"), p["join_password"], tr("the players' one (g_password), empty if none"),
             True)], ok))

    def stop_client(self):
        if not self.client or not self.clients_running():
            self.msg(tr("The game is not running."), C_INFO)
            return

        def kill(_):
            self.client.kill()
            self.client2.kill()
        question = (tr("Force-close both game windows?") if self.client.running() and self.client2.running()
                    else tr("Force-close the game?"))
        self.open(ConfirmDialog(tr("Stop the game"), [question,
                                                      tr("A game in progress is lost; config.cfg is not rewritten.")],
                                kill))

    def follow_log(self, path):
        if path == self.log_path:
            return
        if self.logtail:
            self.logtail.close()
        self.log_path = path
        self.logtail = LogTail(path)

    def poll_log(self, now):
        if not self.dist:
            return
        if now >= self.next_log_pick:
            # the newest of the possible log files: another fs_game, or a Linux build that writes at fs_h's root
            self.next_log_pick = now + 2.0
            self.follow_log(self.client.log_path())
        if now < self.next_log_poll:
            return
        self.next_log_poll = now + 0.25
        lines = self.logtail.poll()
        if lines:
            self.views[7].add(lines)

    # ------------------------------------------------------------------------------------------ local server
    def stop_local(self, then_quit=False):
        if not self.local or not self.local.running():
            self.msg(tr("The local server is not running."), C_INFO)
            return

        def go(_):
            self.request_local_stop(then_quit)
        self.open(ConfirmDialog(tr("Stop the local server"), [tr("Stop the local server?"),
                                                              tr("Players are disconnected and the game is lost.")],
                                go))

    def request_local_stop(self, then_quit=False):
        # quit over rcon lets the server close cleanly; check_processes kills it after STOP_TIMEOUT if it does not.
        # In a thread: the server closes before it answers, so the command waits for its timeout.
        addr, password = ("127.0.0.1", int(self.local.port or DEFAULT_PORT)), self.local_password()

        def send():
            client = RconClient(addr, password, timeout=1.0)
            try:
                client.command("quit")
            except (ProtocolError, OSError):
                pass
            finally:
                client.close()
        threading.Thread(target=send, daemon=True).start()
        self.quit_after_stop = then_quit
        self.stopping = time.monotonic() + STOP_TIMEOUT
        self.msg(tr("Stopping the local server…"), C_WARN)

    def check_processes(self, now):
        if not self.dist:
            return
        if self.client_was_running and not self.client.running():
            self.client_was_running = False
            self.msg(tr("The game has closed."), C_INFO)
            self.missing_cache = (0.0, None)
            config_view = self.views[4]
            # the game rewrote config.cfg as it quit: show its values, unless edits are pending
            if config_view.loaded and not config_view.edits and not config_view.bind_edits:
                self.gamecfg.load()
        if self.client2_was_running and not self.client2.running():
            self.client2_was_running = False
            self.msg(tr("Player 2's window has closed."), C_INFO)
        if self.stopping is not None:
            if not self.local.running():
                self.stopping = None
                self.server_was_running = False
                self.msg(tr("Local server stopped."), C_OK)
                if self.quit_after_stop:
                    self.running = False
            elif now > self.stopping:
                self.local.kill()
                self.msg(tr("The server would not stop: forced stop."), C_WARN)
                self.stopping = now + 5
        elif self.server_was_running and not self.local.running():
            self.server_was_running = False
            tail = self.local.exit_text()
            self.msg(tr("The local server has stopped: {line}").format(line=tail[-1]) if tail
                     else tr("The local server has stopped."), C_ERR)

    # ------------------------------------------------------------------------------------------------- setup
    def start_setup(self):
        p = self.profile
        if self.clients_running() or self.local.running():
            self.msg(tr("Close the game and the local server before installing: they read these files."), C_ERR)
            return
        if not gamesetup.is_install(p["steam_install"]):
            self.msg(tr('First choose your Black Ops install ("c").'), C_ERR)
            return
        self.setup_job = gamesetup.Setup(self.root, p["steam_install"], video=p["setup_video"],
                                         convert=p["setup_convert"], spirv=p["setup_spirv"])
        self.setup_job.start()
        self.msg(tr("Setup started."), C_INFO)

    def check_setup(self):
        job = self.setup_job
        if job and job.finished and not getattr(job, "reported", False):
            job.reported = True
            self.missing_cache = (0.0, None)
            if job.error:
                self.msg(tr("Setup: {error}").format(error=job.error), C_ERR)
            elif job.warning:
                self.msg(tr("Setup done, except Vulkan: {warning}").format(warning=job.warning), C_WARN)
            else:
                self.msg(tr("Setup done: the game can start (F1)."), C_OK)

    # --------------------------------------------------------------------------------------------------- draw
    def draw(self):
        scr = self.scr
        # cheap, and the Launch view's language row takes effect at once
        set_language(self.profile["language"])
        scr.erase()
        self.hits.clear()
        h, w = scr.getmaxyx()
        if h < MIN_H or w < MIN_W:
            put(scr, 0, 0, tr("Window too small ({w}x{h}): at least {min_w}x{min_h} needed.").format(
                w=w, h=h, min_w=MIN_W, min_h=MIN_H))
            scr.refresh()
            return
        fill(scr, 0, color(C_TITLE))
        x = 1
        for i, v in enumerate(self.views):
            label = f" F{i + 1} {tr(v.title)} "
            put(scr, 0, x, label, (curses.A_REVERSE | curses.A_BOLD) if i == self.current else color(C_TITLE))
            self.hits.add(0, x, len(label), lambda i=i: self.show(i))
            x += len(label)
        if x + 9 < w:
            put(scr, 0, w - 9, "ZmClient", color(C_TITLE) | curses.A_BOLD)
        self.draw_status_line(scr, w)
        text, pair, at = self.message
        labels = ((tr("[ Help ]"), self.show_help), (tr("[ Quit ]"), self.ask_quit)) if self.mouse else ()
        buttons = sum(len(label) + 1 for label, _ in labels)
        if text and time.monotonic() - at < 12:
            put(scr, h - 2, 1, text, color(pair), width=w - 2 - buttons)
        if self.mouse:
            x = w - buttons
            for label, action in labels:
                put(scr, h - 2, x, label, curses.A_BOLD)
                self.hits.add(h - 2, x, len(label), action)
                x += len(label) + 1
        fill(scr, h - 1, color(C_TITLE))
        put(scr, h - 1, 1, tr(self.view.hints), color(C_TITLE), width=w - 2)
        cursor(False)
        try:
            self.view.draw(scr, 2, h - 4, w)
        except curses.error:
            pass
        for d in self.modals[-1:]:
            d.draw(scr)
            if d.cursor:
                cursor(True)
        scr.refresh()

    def draw_status_line(self, scr, w):
        p = self.profile
        parts = [(H.MODE_LABELS[p["mode"]], curses.A_BOLD)]
        if p["mode"] == "solo":
            parts.append((map_label(p["map"], self.root), 0))
        elif p["mode"] == "join":
            parts.append((f"{p['join_host']}:{p['join_port']}" if p["join_host"] else tr("no server chosen"), 0))
        else:
            parts.append((f"127.0.0.1:{p['host_port']}, {map_label(p['map'], self.root)}", 0))
        if self.dist:
            if self.client.running():
                parts.append((tr("● game running (PID {pid})").format(pid=self.client.pid), color(C_OK)))
            if self.client2.running():
                parts.append((tr("● player 2 (PID {pid})").format(pid=self.client2.pid), color(C_OK)))
            if self.local.running():
                parts.append((tr("● local server, port {port}").format(port=self.local.port), color(C_OK)))
            if self.setup_job and not self.setup_job.finished:
                parts.append((tr("setup: {phase}…").format(phase=tr(self.setup_job.phase)), color(C_WARN)))
        else:
            parts.append((tr("no game folder"), color(C_ERR)))
        x = 1
        for i, (text, attr) in enumerate(parts):
            if i:
                put(scr, 1, x, " | ", color(C_INFO))
                x += 3
            put(scr, 1, x, text, attr)
            x += len(text)

    # ---------------------------------------------------------------------------------------------------- keys
    def handle_mouse(self):
        event = read_mouse()
        if event is None:
            return
        y, x, kind = event
        if self.modals:
            dialog = self.modals[-1]
            if dialog.mouse(y, x, kind):
                self.modals.remove(dialog)
        elif kind in ("up", "down"):
            self.view.wheel(-1 if kind == "up" else 1)
        else:
            self.hits.dispatch(y, x, kind)

    def handle(self, k):
        if k == curses.KEY_MOUSE:
            self.handle_mouse()
            return
        if k == curses.KEY_RESIZE:
            try:
                curses.resize_term(0, 0)
            except curses.error:
                pass
            return
        if self.modals:
            dialog = self.modals[-1]
            if dialog.key(k):
                self.modals.remove(dialog)
            return
        for i in range(len(self.views)):
            if k == curses.KEY_F1 + i:
                self.show(i)
                return
        if k == TAB:
            self.show(self.current + 1)
            return
        if k == BTAB:
            self.show(self.current - 1)
            return
        if k in (curses.KEY_F9, "?"):
            self.show_help()
            return
        if k in (curses.KEY_F10, "q"):
            self.ask_quit()
            return
        self.view.key(k)

    def ask_quit(self):
        if self.setup_job and not self.setup_job.finished:
            def stop_setup(_):
                self.setup_job.cancel()
                self.running = False
            self.open(ConfirmDialog(tr("Quit ZmClient"), [tr("A setup is in progress."),
                                                          tr("Quitting cancels it (the files already copied stay).")],
                                    stop_setup))
            return
        if self.local and self.local.running():
            def go(stop):
                if stop:
                    self.request_local_stop(then_quit=True)
                else:
                    self.running = False
            self.open(ConfirmDialog(tr("Quit ZmClient"), [
                tr("Quit ZmClient? The game keeps running."),
                tr("So does the local server, unless the box below is ticked. ZmClient and ZmAdmin find it again "
                   "later.")], go, checkbox=tr("Also stop the local server")))
        else:
            self.running = False

    # ---------------------------------------------------------------------------------------------------- loop
    def run(self):
        init_colors()
        # raw: Ctrl+S (Save) would be the terminal's XOFF in cbreak mode; Ctrl+C then comes as a key
        curses.raw()
        self.scr.timeout(100)
        self.scr.keypad(True)
        if self.mouse:
            curses.mousemask(MOUSE_MASK)
        cursor(False)
        try:
            while self.running:
                now = time.monotonic()
                self.poll_log(now)
                self.check_processes(now)
                self.check_setup()
                self.draw()
                try:
                    k = self.scr.get_wch()
                except curses.error:
                    continue
                except KeyboardInterrupt:
                    self.ask_quit()
                    continue
                k = normalize_key(k)
                if k == CTRL_C and self.modals:
                    self.modals.pop()
                elif k == CTRL_C:
                    self.ask_quit()
                elif k is not None:
                    self.handle(k)
        finally:
            self.browser.stop()
            if self.logtail:
                self.logtail.close()
            if self.setup_job and not self.setup_job.finished:
                self.setup_job.cancel()
                self.setup_job.join(timeout=10)
