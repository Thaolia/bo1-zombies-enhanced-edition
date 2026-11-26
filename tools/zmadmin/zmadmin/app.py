"""The curses application: the tab bar, the status lines, the event loop, connections and the local server."""
import curses
import os
import queue
import socket
import time

from . import help as H
from .config import DEFAULT_PROFILE
from .i18n import tr
from .launcher import LocalServer
from .link import ServerLink
from .logtail import LogTail
from .model import merge_players
from .protocol import strip_colors
from .profiles import start_profile, write_profile_cfg
from .settings import Form, build_server_cfg, kept_settings
from .views import ConsoleView, GameView, LogView, PlayersView, ServersView, SettingsView
from .widgets import (BTAB, CTRL_C, C_ERR, C_INFO, C_OK, C_TITLE, C_WARN, ESC, MOUSE_MASK, TAB, ChecklistDialog,
                      ConfirmDialog, HitMap, InputDialog, MessageDialog, color, cursor, fill, init_colors,
                      normalize_key, put, read_mouse)

STOP_TIMEOUT = 15.0
MIN_H, MIN_W = 24, 80
MOUSE_BUTTONS_W = 21    # "[ Aide ] [ Quitter ]" at the right of the message line


class App:
    def __init__(self, scr, config, dist, initial=None, admin_every=5.0, mouse=True):
        self.scr = scr
        self.mouse = mouse
        self.hits = HitMap()
        self.config = config
        self.dist = dist
        self.locals = {}            # profile -> LocalServer, made on first use
        self.admin_every = admin_every
        self.history = config.load_history()
        self.link = None
        self.connected_to = None    # ("local", None) or ("saved", entry) or ("cli", entry)
        self.status = None
        self.report = None
        self.rows = []
        self.form = Form()
        self.modals = []
        self.message = ("", 0, 0.0)
        self.running = True
        self.stopping = {}          # profile -> deadline of its stop
        self.quit_after_stop = False
        self.log_profile = None     # the profile whose console_mp.log the Log view follows
        self.logtail = None
        self.next_log_poll = 0.0
        self.views = [ServersView(self), PlayersView(self), GameView(self), SettingsView(self), ConsoleView(self),
                      LogView(self)]
        self.current = 0
        if dist:
            self.follow_log(DEFAULT_PROFILE)
        if initial:
            self.connect(*initial)
            self.show(1)
        else:
            running = [n for n in self.profile_names() if self.local(n).running()]
            if running:
                self.connect_local(running[0])

    # ----------------------------------------------------------------------------------------------- helpers
    @property
    def view(self):
        return self.views[self.current]

    @property
    def console(self):
        return self.views[4]

    @property
    def settings_view(self):
        return self.views[3]

    def msg(self, text, pair=C_INFO):
        self.message = (text, pair, time.monotonic())

    def open(self, dialog):
        self.modals.append(dialog)

    def show_help(self):
        self.open(MessageDialog(f"Aide : {self.view.title}", H.VIEW_HELP[self.view.name] + [""] + H.GLOBAL_HELP))

    def show(self, index):
        self.current = index % len(self.views)
        if self.link:
            self.link.admin_wanted = self.view.uses_admin
            if self.view.uses_admin:
                self.link.refresh_admin()
        self.view.on_show()

    def require_link(self):
        if not self.link:
            self.msg("Pas connecté : choisir un serveur dans la vue Serveurs (F1).", C_WARN)
            return False
        return True

    def send(self, command, tag="console"):
        self.link.send(command, tag)
        if tag in ("console", "action"):
            self.console.add(f"> {command}", C_INFO)

    def remember(self, command):
        if not self.history or self.history[-1] != command:
            self.history.append(command)
            del self.history[:-100]
        try:
            self.config.save_history(self.history)
        except OSError:
            pass

    def is_local_link(self):
        return bool(self.link and self.connected_to and self.connected_to[0] == "local")

    # ------------------------------------------------------------------------------------------------ profiles
    def profile_names(self):
        return [n for n, _ in self.config.local_profiles(self.dist.root)] if self.dist else []

    def local(self, name):
        server = self.locals.get(name)
        if server is None:
            server = self.locals[name] = LocalServer(self.dist, name)
        return server

    def profile(self, name):
        return self.config.local_profile(self.dist.root, name)

    @property
    def local_profile_name(self):
        """The profile of the local server the link talks to, or None."""
        return self.connected_to[1] if self.is_local_link() else None

    def running_locals(self):
        return [n for n in self.profile_names() if self.local(n).running()]

    def follow_log(self, name):
        if self.log_profile == name:
            return
        if self.logtail:
            self.logtail.close()
        self.log_profile = name
        self.logtail = LogTail(self.local(name).home.log)
        self.views[5].reset()

    # ------------------------------------------------------------------------------------------- connections
    def connect(self, host, port, password, target):
        self.disconnect()
        try:
            self.link = ServerLink(host, port, password, admin_every=self.admin_every)
        except (OSError, socket.gaierror) as e:
            self.msg(f"Adresse {host} introuvable : {e}", C_ERR)
            return
        self.connected_to = target
        self.link.admin_wanted = self.view.uses_admin
        self.form = Form()
        self.settings_view.loaded = False
        self.settings_view.saving = None
        self.console.add(f"--- connexion à {host}:{port} ---", C_INFO)
        self.msg(f"Connexion à {host}:{port}…", C_INFO)
        if self.view is self.settings_view:
            self.settings_view.on_show()

    def disconnect(self):
        if self.link:
            self.link.close()
        self.link = None
        self.connected_to = None
        self.status = self.report = None
        self.rows = []

    def connect_saved(self, entry):
        if not entry.get("password"):
            self.msg("Ce serveur n'a pas de mot de passe rcon : « e » pour l'ajouter. Statut seulement.", C_WARN)
        self.connect(entry["host"], int(entry.get("port", 3074)), entry.get("password", ""), ("saved", entry))
        self.show(1)

    def connect_local(self, name):
        local = self.profile(name)
        port = self.local(name).port or local["port"]
        self.follow_log(name)
        self.connect("127.0.0.1", int(port), local["password"], ("local", name))
        self.show(1)

    def password_changed(self, password):
        """rcon_password changed by Save: use it from now on, and remember it where it came from."""
        self.link.set_password(password)
        kind, entry = self.connected_to
        if kind == "local":
            self.profile(entry)["password"] = password
        elif kind == "saved":
            entry["password"] = password
        try:
            self.config.save()
        except OSError as e:
            self.msg(f"Mot de passe changé, mais servers.json n'a pas pu être écrit : {e}", C_ERR)

    # ------------------------------------------------------------------------------------------- local servers
    def launch_local(self, name):
        """Starts profile `name` with its saved game, port and password; None or why not."""
        why = start_profile(self.config, self.dist, self.local(name), name)
        if why:
            return why
        server = self.local(name)
        label = H.map_label(server.map)
        self.console.add(f"--- serveur local « {name} » lancé : {label}, port {server.port}, PID {server.pid} ---", C_OK)
        self.msg(f"« {name} » lancé (PID {server.pid}) : chargement de {label}…", C_OK)
        self.connect_local(name)
        return None

    def stop_local(self, name):
        server = self.local(name)
        if not server.running():
            self.msg(f"« {name} » ne tourne pas.", C_INFO)
            return

        def go(_):
            self.request_stop(name)
            self.msg(f"Arrêt de « {name} »…", C_WARN)
        self.open(ConfirmDialog("Arrêter un serveur local", [f"Arrêter le serveur local « {name} » ?",
                                                             "Ses joueurs sont déconnectés et sa partie est perdue."],
                                go))

    def request_stop(self, name):
        """quit over rcon when connected to it, else kill; check_local forces it after STOP_TIMEOUT."""
        if self.local_profile_name == name and self.link.online:
            self.send("quit", tag="quit")
        else:
            self.local(name).kill()
        self.stopping[name] = time.monotonic() + STOP_TIMEOUT

    def check_local(self, now):
        connected = self.local_profile_name
        if connected and connected not in self.stopping:
            server = self.local(connected)
            if not server.running() and server.pid:
                tail = server.exit_text()
                self.console.add(f"--- le serveur local « {connected} » s'est arrêté ---", C_ERR)
                for line in tail:
                    self.console.add(line, C_ERR)
                self.msg(f"« {connected} » s'est arrêté (dernières lignes dans la Console).", C_ERR)
                server.pid = None
                self.disconnect()
        for name, deadline in list(self.stopping.items()):
            server = self.local(name)
            if not server.running():
                del self.stopping[name]
                server.pid = None
                if self.local_profile_name == name:
                    self.disconnect()
                self.msg(f"« {name} » arrêté.", C_OK)
            elif now > deadline:
                server.kill()
                self.msg(f"« {name} » ne s'arrêtait pas : arrêt forcé.", C_WARN)
                self.stopping[name] = now + 5
        if self.quit_after_stop and not self.stopping:
            self.running = False

    def keep_settings(self, applied):
        """Settings Save applied, kept in the profile (or the saved server's entry) they were sent to, so its
        server.cfg can be rebuilt; a local profile's server.cfg is rewritten now."""
        kind, entry = self.connected_to
        if kind == "local":
            target, name = self.profile(entry), entry
        elif kind == "saved":
            target, name = entry, None
        else:
            return
        kept = kept_settings(applied, local=kind == "local")
        if not kept:
            return
        target.setdefault("settings", {}).update(kept)
        try:
            self.config.save()
        except OSError as e:
            self.msg(f"Réglages appliqués, mais servers.json n'a pas pu être écrit : {e}", C_ERR)
            return
        if name:
            self.write_cfg(name)

    def write_cfg(self, name):
        server = self.local(name)
        settings = self.profile(name).get("settings") or {}
        why = write_profile_cfg(server.home, settings, name)
        if why:
            self.msg(why, C_ERR)
            return False
        self.console.add(f"--- server.cfg de « {name} » : {len(settings)} réglage(s) gardé(s), "
                         f"{server.home.server_cfg} ---", C_OK)
        return True

    def export_cfg(self, entry):
        """A saved remote server's kept settings as a server.cfg in ZmAdmin's folder; returns its path or None."""
        label = entry.get("name") or entry["host"]
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        path = os.path.join(self.config.dir, f"{safe}_server.cfg")
        try:
            os.makedirs(self.config.dir, exist_ok=True)
            with open(path, "w", encoding="latin-1", newline="\n") as f:
                f.write(build_server_cfg(None, entry.get("settings") or {}, label))
        except OSError as e:
            self.msg(f"server.cfg non écrit : {e}", C_ERR)
            return None
        return path

    def edit_mods(self, current, on_done):
        mods = self.dist.mods() if self.dist and self.is_local_link() else []
        intro = ["mods/admin est toujours chargé par le serveur."]
        if mods:
            self.open(ChecklistDialog("Mods chargés", [(m, m) for m in mods], current,
                                      lambda ticked: on_done(" ".join(ticked)), intro=intro))
        else:
            def ok(v):
                if '"' in v or ";" in v:
                    return "pas de guillemet ni de point-virgule"
                on_done(" ".join(v.split()))
                return None
            self.open(InputDialog("Mods chargés", "fs_mods", " ".join(current),
                                  "noms des dossiers de mods/ du serveur, séparés par des espaces", ok,
                                  intro=intro + ["Serveur distant : ZmAdmin ne voit pas ses dossiers, tapez les noms."]))

    # ------------------------------------------------------------------------------------------------- events
    def pump(self):
        if not self.link:
            return
        while True:
            try:
                event = self.link.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "status":
                _, status, error = event
                was = self.status is not None
                self.status = status
                if status is None and was:
                    self.msg(f"Le serveur ne répond plus ({error}) : nouvel essai chaque seconde.", C_ERR)
                elif status is not None and not was:
                    self.msg(f"Connecté : {status.get('sv_hostname')} sur {H.map_label(status.get('mapname'))}.",
                             C_OK)
                    if self.view is self.settings_view:
                        self.settings_view.on_show()
            elif kind == "admin":
                self.report = event[1]
            elif kind == "auth":
                self.msg(f"rcon : {event[1]}. Vue Serveurs (F1), « e » pour corriger le mot de passe.", C_ERR)
            elif kind == "reply":
                _, tag, command, text, error = event
                if tag in ("console", "action"):
                    if text is None:
                        self.console.add(f"! {error}", C_ERR)
                    else:
                        self.console.add(strip_colors(text).rstrip("\n") or "(pas de sortie)")
                if tag == "action":
                    first = strip_colors(text or "").strip().splitlines()
                    self.msg(error if text is None else (first[0] if first else f"{command} : envoyé"),
                             C_ERR if text is None else C_OK)
                elif tag.startswith(("settings-", "save-")):
                    self.settings_view.on_reply(tag, text, error)
            self.rows = merge_players(self.status, self.report)

    def poll_log(self, now):
        if not self.logtail or now < self.next_log_poll:
            return
        self.next_log_poll = now + 0.25
        lines = self.logtail.poll()
        if not lines:
            return
        self.views[5].add(lines)
        if self.is_local_link():
            for line in lines:
                # the server also logs every rcon command it gets: ZmAdmin's own polling would flood the Console
                if line.startswith(("Rcon from", "zm_admin", "  ")) or not line.strip():
                    continue
                if "admin:" in line:
                    self.console.add(line)

    # --------------------------------------------------------------------------------------------------- draw
    def draw(self):
        scr = self.scr
        scr.erase()
        self.hits.clear()
        h, w = scr.getmaxyx()
        if h < MIN_H or w < MIN_W:
            put(scr, 0, 0, f"Fenêtre trop petite ({w}x{h}) : il faut au moins {MIN_W}x{MIN_H}.")
            scr.refresh()
            return
        fill(scr, 0, color(C_TITLE))
        x = 1
        for i, v in enumerate(self.views):
            label = f" F{i + 1} {v.title} "
            put(scr, 0, x, label, (curses.A_REVERSE | curses.A_BOLD) if i == self.current else color(C_TITLE))
            self.hits.add(0, x, len(label), lambda i=i: self.show(i))
            x += len(label) + 1
        put(scr, 0, x + 1, "ZmAdmin", color(C_TITLE) | curses.A_BOLD)
        self.draw_status_line(scr, w)
        text, pair, at = self.message
        buttons = MOUSE_BUTTONS_W if self.mouse else 0
        if text and time.monotonic() - at < 12:
            put(scr, h - 2, 1, text, color(pair), width=w - 2 - buttons)
        if self.mouse:
            x = w - buttons
            for label, action in (("[ Aide ]", self.show_help), ("[ Quitter ]", self.ask_quit)):
                put(scr, h - 2, x, label, curses.A_BOLD)
                self.hits.add(h - 2, x, len(label), action)
                x += len(label) + 1
        fill(scr, h - 1, color(C_TITLE))
        put(scr, h - 1, 1, tr(self.view.hints), color(C_TITLE), width=w - 2)
        cursor(False)
        # the view draws last: a view with a command line leaves the cursor on it
        try:
            self.view.draw(scr, 2, h - 4, w)
        except curses.error:
            pass
        if self.view.captures_text and not self.modals:
            cursor(True)
        for d in self.modals[-1:]:
            d.draw(scr)
            if d.cursor:
                cursor(True)
        scr.refresh()

    def draw_status_line(self, scr, w):
        if not self.link:
            put(scr, 1, 1, "Pas connecté. F1 : choisir ou lancer un serveur.", color(C_WARN))
            return
        parts = []
        if self.link.online is None:
            parts.append(("● connexion…", C_WARN))
        elif not self.link.online:
            starting = self.is_local_link() and self.local(self.local_profile_name).running()
            parts.append(("● démarrage du serveur…" if starting else "● hors ligne", C_WARN if starting else C_ERR))
        else:
            parts.append(("● en ligne", C_OK))
        where = f"local « {self.local_profile_name} » " if self.is_local_link() else ""
        parts.append((f"{where}{self.link.host}:{self.link.port}", 0))
        if self.status:
            parts.append((self.status.get("sv_hostname"), 0))
            parts.append((H.MAP_NAMES.get(self.status.get("mapname"), self.status.get("mapname")), 0))
            parts.append((f"{len(self.status.players)}/{self.status.max_clients} joueurs", 0))
        if self.link.auth_ok is False:
            parts.append(("rcon refusé", C_ERR))
        if self.link.queued:
            parts.append((f"{self.link.queued} commande(s) en file", C_WARN))
        x = 1
        for i, (text, pair) in enumerate(parts):
            if i:
                put(scr, 1, x, " | ", color(C_INFO))
                x += 3
            put(scr, 1, x, text, color(pair) if pair else 0)
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
            # a dialog may open the next one before it closes: remove this one, not the top
            if dialog.key(k):
                self.modals.remove(dialog)
            return
        for i in range(6):
            if k == curses.KEY_F1 + i:
                self.show(i)
                return
        if k == TAB:
            self.show(self.current + 1)
            return
        if k == BTAB:
            self.show(self.current - 1)
            return
        if k == curses.KEY_F9 or (k == "?" and not self.view.captures_text):
            self.show_help()
            return
        if k == curses.KEY_F10 or (k == "q" and not self.view.captures_text):
            self.ask_quit()
            return
        if self.view.key(k):
            return
        if k == ESC and self.view.captures_text:
            self.console.edit.set("")

    def ask_quit(self):
        running = self.running_locals()
        if running:
            def go(stop):
                if stop:
                    self.quit_after_stop = True
                    for name in running:
                        self.request_stop(name)
                    self.msg("Arrêt des serveurs locaux avant de quitter…", C_WARN)
                else:
                    self.running = False
            names = ", ".join(f"« {n} »" for n in running)
            self.open(ConfirmDialog("Quitter ZmAdmin", ["Quitter ZmAdmin ?",
                                                        f"En marche : {names}.",
                                                        "Ils continuent de tourner, sauf si la case ci-dessous",
                                                        "est cochée. Un prochain ZmAdmin les retrouve."],
                                    go, checkbox="Arrêter aussi les serveurs locaux"))
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
        while self.running:
            now = time.monotonic()
            self.pump()
            self.poll_log(now)
            if self.dist:
                self.check_local(now)
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
        self.disconnect()
        if self.logtail:
            self.logtail.close()
