"""The eight views. Each draws itself in the body area and handles the keys the app does not take."""
import curses
import os
import time

from zmadmin.i18n import tr
from zmadmin.views import LogView as AdminLogView
from zmadmin.views import View
from zmadmin.widgets import (BAD_MARK, C_DIM, C_ERR, C_INFO, C_OK, C_WARN, CTRL_S, ENTER, ESC, OK_MARK, ChoiceDialog,
                             ConfirmDialog, FormDialog, InputDialog, color, put, wrap)

from . import gamesetup
from . import help as H
from .dirbrowser import FolderDialog, start_folder
from .dvarhelp import KNOWN, describe
from .gamecfg import BY_NAME, SETTINGS, valid_bind_key, validate
from .profile import (BO2_WEAPON_CHOICES, DEFAULT_NAME2, DEFAULT_PORT, MAP_LABELS, SSAA_MODES, START_PERKS,
                      bo2_weapons_available, bo2_weapons_installed, dual_wield_installed, FAR_RESPAWN_CHOICES,
                      SPAWN_RATE_CHOICES, START_POINT_CHOICES, check_extra, unlimited_pap_installed, map_installed,
                      map_label, nightmare_available, parse_size, quote_command, resolve_map, solo_maps,
                      specials_available, split_on, valid_host, valid_name, valid_password)

# shown as is in both languages: each language under its own name
LANGUAGE_NAMES = {"en": "English", "fr": "Français"}


class Row:
    def __init__(self, key, label, value="", action=None, disabled=None, help_text=None, section=False):
        self.key = key
        self.label = label
        self.value = value
        self.action = action
        self.disabled = disabled        # why the row does not apply, or None
        self.help = help_text if help_text is not None else H.ROW_HELP.get(key, "")
        self.section = section


def section(label):
    return Row(None, label, section=True)


def _int(text, lo, hi):
    text = text.strip()
    if not text.lstrip("-").isdigit():
        raise ValueError(tr("a whole number"))
    n = int(text)
    if not lo <= n <= hi:
        raise ValueError(tr("between {lo} and {hi}").format(lo=lo, hi=hi))
    return n


class RowsView(View):
    """A list of settings: one row each, its value, its help below. Rows a mode or a map does not use are greyed
    with the reason."""

    label_w = 34

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0
        self.top = 0

    @property
    def p(self):
        return self.app.profile

    def rows(self):
        raise NotImplementedError

    def draw_header(self, scr, top, width):
        return top

    def buttons(self):
        """(label, key) of the buttons under the list."""
        return []

    def draw_footer(self, scr, y, bottom, width):
        pass

    def list_height(self, height):
        return max(4, height - 9)

    def _fix_sel(self, rows, step=1):
        self.sel = max(0, min(self.sel, len(rows) - 1))
        n = 0
        while rows and rows[self.sel].section and n < len(rows):
            self.sel = (self.sel + step) % len(rows)
            n += 1

    def draw(self, scr, top, height, width):
        rows = self.rows()
        self._fix_sel(rows)
        y = self.draw_header(scr, top, width)
        bottom = top + height
        room = min(self.list_height(height), bottom - y - 5)
        self.top = max(0, min(self.top, self.sel), self.sel - room + 1)
        for i, row in enumerate(rows[self.top:self.top + room]):
            n = self.top + i
            if row.section:
                put(scr, y, 1, f" {row.label} ", curses.A_BOLD | curses.A_UNDERLINE)
            else:
                attr = curses.A_REVERSE if n == self.sel else 0
                dim = color(C_DIM) if row.disabled else 0
                put(scr, y, 1, f"  {row.label:<{self.label_w}}".ljust(width - 2), attr | dim)
                put(scr, y, 3 + self.label_w, str(row.value), attr | (dim or curses.A_BOLD), width=width - 5 - self.label_w)
                self.zone(y, 1, width - 2, lambda n=n: self.select(n), lambda n=n: self.select(n, ENTER))
            y += 1
        if len(rows) > room:
            put(scr, y, 3, tr("({first}-{last} of {total}: Up/Down, wheel)").format(
                first=self.top + 1, last=min(len(rows), self.top + room), total=len(rows)), color(C_DIM))
        y += 1
        x = 3
        for label, k in self.buttons():
            x = self.button(scr, y, x, f"[ {label} ]", curses.A_BOLD, lambda k=k: self.key(k))
        if self.buttons():
            y += 2
        if rows and not rows[self.sel].section:
            row = rows[self.sel]
            lines = []
            if row.disabled:
                lines.append((tr("No effect here: {why}").format(why=row.disabled), C_WARN))
            lines += [(l, C_DIM) for l in wrap(row.help, width - 6)] if row.help else []
            for text, pair in lines[:max(0, bottom - y - 1)]:
                put(scr, y, 3, text, color(pair), width=width - 4)
                y += 1
        self.draw_footer(scr, y + 1, bottom, width)

    def select(self, n, then=None):
        self.sel = n
        if then:
            self.key(then)

    def key(self, k):
        rows = self.rows()
        if k == curses.KEY_UP:
            self.sel = (self.sel - 1) % max(1, len(rows))
            self._fix_sel(rows, -1)
        elif k == curses.KEY_DOWN:
            self.sel = (self.sel + 1) % max(1, len(rows))
            self._fix_sel(rows, 1)
        elif k in (ENTER, " ") and rows:
            row = rows[self.sel]
            if row.section or not row.action:
                return True
            if row.disabled:
                self.app.msg(tr("{label}: no effect here ({why}).").format(label=row.label, why=row.disabled), C_WARN)
                return True
            row.action()
        else:
            return False
        return True

    # ---- the profile's setting editors
    def toggle(self, key):
        def go():
            self.p[key] = not self.p[key]
            self.app.save_profile()
        return go

    def choose(self, key, title, items, convert=None):
        """items: (value, label, description), already translated; title is translated when the dialog opens."""
        def go():
            def picked(v):
                self.p[key] = convert(v) if convert else v
                self.app.save_profile()
            self.app.open(ChoiceDialog(tr(title), items, picked, current=self.p[key]))
        return go

    def toggle_perk(self, name):
        def go():
            perks = self.p["start_perks"]
            self.p["start_perks"] = [p for p in perks if p != name] if name in perks else perks + [name]
            self.app.save_profile()
        return go

    def ask(self, key, title, label, help_text, parse, mask=False):
        """parse(text) returns the value to keep, or raises ValueError with why not. The texts are translated when
        the dialog opens."""
        def go():
            def ok(v):
                try:
                    self.p[key] = parse(v)
                except ValueError as e:
                    return str(e)
                self.app.save_profile()
                return None
            self.app.open(InputDialog(tr(title), tr(label), self.p[key], tr(help_text), ok, mask=mask))
        return go


def _yes(b):
    return tr("yes") if b else tr("no")


def size_value(text):
    if not parse_size(text):
        raise ValueError(tr("WIDTHxHEIGHT, e.g. 1280x720"))
    return text.strip()


def _points(n):
    return f"{n:,}".replace(",", " ") if n else tr("game default (500)")


def _far(n):
    return tr("beyond {n}").format(n=f"{n:,}".replace(",", " ")) if n else tr("no")


def _spawn_rate(n):
    return tr("{n} times faster").format(n=n) if n else tr("game default")


def _name(text):
    text = text.strip()
    if text and not valid_name(text):
        raise ValueError(tr('1 to 15 letters, digits, "_", "-" or "."'))
    return text


# -------------------------------------------------------------------------------------------------------------- Play
class PlayView(RowsView):
    name, title = "play", "Play"
    hints = "Enter edit  L launch  S stop game  K stop local server  ? help  q quit"

    def list_height(self, height):
        return 6

    def rows(self):
        p, app = self.p, self.app
        mode = p["mode"]
        rows = [Row("mode", "Mode", H.MODE_LABELS[mode], self.choose(
            "mode", "Mode", [(m, H.MODE_LABELS[m], H.MODE_HELP[m]) for m in H.MODE_LABELS]),
            help_text=H.MODE_HELP[mode])]
        if mode == "solo":
            rows.append(Row("map", "Map", map_label(p["map"], app.root), lambda: self.app.show(2),
                            help_text=tr("Map and mods are chosen in the Solo view (F3): Enter goes there.")))
            rows.append(Row("mods", "Mods", app.solo_summary(), lambda: self.app.show(2),
                            help_text=tr("Solo view (F3).")))
        elif mode == "join":
            target = f"{p['join_host']}:{p['join_port']}" if p["join_host"] else tr("(none: Servers view, F2)")
            rows.append(Row("server", tr("Server"), target, self.app.edit_join_target))
            rows.append(Row("join_detect_mods", tr("Detect the server's mods"), _yes(p["join_detect_mods"]),
                            self.toggle("join_detect_mods"), help_text=H.ROW_HELP["join_detect_mods"]))
            manual = (" " + tr("Only when the server does not answer: the server tells what it loads itself "
                               "(Detect the server's mods).")) if p["join_detect_mods"] else ""
            rows.append(Row("join_bo2_weapons", tr("Black Ops II weapons"), _yes(p["join_bo2_weapons"]),
                            self.toggle("join_bo2_weapons"),
                            disabled=None if bo2_weapons_installed(app.root) else
                            tr("no mods/bo2weapons/mod.ff: build it from your Black Ops II"),
                            help_text=H.ROW_HELP["join_bo2_weapons"] + manual))
            rows.append(dual_row(self, "join_dual_wield", app.root))
        else:
            rows.append(Row("map", tr("Local server map"), map_label(p["map"], app.root), lambda: self.app.show(2),
                            help_text=H.ROW_HELP["host_game"]))
            rows.append(Row("mods", tr("Local server mods"), app.solo_summary(), lambda: self.app.show(2),
                            help_text=H.ROW_HELP["host_game"]))
            rows.append(Row("host_port", tr("Local server port"), str(p["host_port"]),
                            self.ask("host_port", "Local server port", "Port", "3074 by default",
                                     lambda t: _int(t, 1, 65535))))
        rows.append(name_row(self))
        rows.append(split_row(self))
        return rows

    def buttons(self):
        out = [(tr("Launch game"), "L")]
        if self.app.client and self.app.clients_running():
            out.append((tr("Stop game"), "S"))
        if self.app.local and self.app.local.running():
            out.append((tr("Stop local server"), "K"))
        return out

    def draw_footer(self, scr, y, bottom, width):
        app = self.app
        lines = []
        if not app.dist:
            lines.append((f"{BAD_MARK} " + tr("No game folder: ZmClient must sit next to BO1Zombies (a make_dist.sh "
                                              "folder), or be started with --dist."), C_ERR))
        else:
            missing = app.setup_missing()
            lines.append((f"{OK_MARK} " + tr("Game files installed") if not missing
                          else f"{BAD_MARK} " + tr("Game files: {missing} (Setup view, F7)").format(missing=missing),
                          C_OK if not missing else C_ERR))
            if app.client.running():
                lines.append((tr("● Game running (PID {pid})").format(pid=app.client.pid), C_OK))
            else:
                lines.append((tr("○ Game stopped"), 0))
            if app.client2.running():
                lines.append((tr("● Player 2 window running (PID {pid})").format(pid=app.client2.pid), C_OK))
            if app.local.running():
                lines.append((tr("● Local server running: PID {pid}, port {port}, {map}").format(
                    pid=app.local.pid, port=app.local.port, map=map_label(app.local.map or '', app.root)), C_OK))
            if app.launch_cfg_text():
                lines.append((tr("! {path} exists: the game adds its content before this command line.").format(
                    path=os.path.join(app.root, 'launch.cfg')), C_WARN))
        for text, pair in lines:
            if y >= bottom:
                return
            put(scr, y, 3, text, color(pair) if pair else 0, width=width - 4)
            y += 1
        if y + 2 >= bottom:
            return
        players = (1, 2) if split_on(self.p) else (1,)
        y += 1
        for player in players:
            if y + 1 >= bottom:
                return
            put(scr, y, 3, tr("Command line:") if len(players) == 1 else
                tr("Player {player} command line:").format(player=player), curses.A_BOLD)
            y += 1
            argv, err = app.command(player)
            text = err or quote_command([os.path.basename(argv[0])] + argv[1:])
            for line in wrap(text, width - 6):
                if y >= bottom:
                    return
                put(scr, y, 3, line, color(C_ERR if err else C_DIM), width=width - 4)
                y += 1

    def key(self, k):
        if k in ("L", "l"):
            self.app.launch()
        elif k in ("S", "s"):
            self.app.stop_client()
        elif k in ("K", "k"):
            self.app.stop_local()
        else:
            return super().key(k)
        return True


# ----------------------------------------------------------------------------------------------------------- Servers
class ServersView(View):
    name, title = "servers", "Servers"
    hints = "Enter join  a add  e edit  x remove  f favorite  r refresh  ? help"

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def entries(self):
        """(kind, favorite or None, (ip, port) or None, Entry or None, error text)."""
        app = self.app
        found, resolved = app.browser.snapshot() if app.browser else ({}, {})
        out, fav_addrs = [], set()
        for f in app.profile["favorites"]:
            res = resolved.get((f["host"], int(f.get("port", DEFAULT_PORT))))
            addr = res if isinstance(res, tuple) else None
            if addr:
                fav_addrs.add(addr)
            out.append(("fav", f, addr, found.get(addr) if addr else None, res if isinstance(res, str) else ""))
        for addr, e in sorted(found.items()):
            if e.lan and addr not in fav_addrs:
                out.append(("lan", None, addr, e, ""))
        return out

    def draw(self, scr, top, height, width):
        entries = self.entries()
        self.sel = max(0, min(self.sel, len(entries) - 1))
        put(scr, top, 1, f"  {tr('Name'):<24}{tr('Address'):<22}{'Map':<20}{tr('Players'):<9}{'Ping':<6}",
            curses.A_BOLD)
        y = top + 1
        if not entries:
            put(scr, y + 1, 3, tr('No server: "a" adds a favorite. Servers on the local network show up by '
                                  'themselves.'), color(C_INFO))
            y += 2
        rows = max(3, height - 10)
        start = max(0, self.sel - rows + 1)
        for i, (kind, f, addr, e, err) in enumerate(entries[start:start + rows]):
            n = start + i
            st = e.status if e else None
            if kind == "fav":
                name = "★ " + (f.get("name") or (st.get("sv_hostname") if st else "") or f["host"])
                where = f"{f['host']}:{f.get('port', DEFAULT_PORT)}"
            else:
                name = "  " + (st.get("sv_hostname") if st else "?")
                where = f"{addr[0]}:{addr[1]}"
            if st:
                mapn = MAP_LABELS.get(st.get("mapname"), st.get("mapname"))
                players = f"{len(st.players)}/{st.max_clients}"
                ping = f"{e.ping}"
                pair = 0
            else:
                mapn, players, ping = (err or (e.error if e else "") or tr("searching…")), "", ""
                pair = C_DIM
            attr = curses.A_REVERSE if n == self.sel else (color(pair) if pair else 0)
            put(scr, y, 1, f"{name[:23]:<24}{where[:21]:<22}{mapn[:19]:<20}{players:<9}{ping:<6}".ljust(width - 2),
                attr)
            self.zone(y, 1, width - 2, lambda n=n: self.select(n), lambda n=n: self.select(n, ENTER))
            y += 1
        y += 1
        x = 3
        for label, k in (("Join", ENTER), ("Add", "a"), ("Edit", "e"), ("Remove", "x"),
                         ("Favorite", "f"), ("Refresh", "r")):
            x = self.button(scr, y, x, f"[ {tr(label)} ]", curses.A_BOLD, lambda k=k: self.key(k))
        y += 2
        if entries:
            kind, f, addr, e, _ = entries[self.sel]
            st = e.status if e else None
            if st and st.players:
                names = ", ".join(f"{p.name} ({p.score})" for p in st.players)
                put(scr, y, 3, tr("Players: {list}").format(list=names),
                    color(C_INFO), width=width - 4)
                y += 1
        info = tr("Local network: getstatus broadcast on ports 3074 to 3083, every 3 seconds. An internet server is "
                  "added by hand; the client joins it with cl_allowWanConnect 1.")
        for line in wrap(info, width - 6):
            if y >= top + height:
                break
            put(scr, y, 3, line, color(C_DIM))
            y += 1

    def select(self, n, then=None):
        self.sel = n
        if then:
            self.key(then)

    def key(self, k):
        entries = self.entries()
        cur = entries[self.sel] if entries else None
        favs = self.app.profile["favorites"]
        if k == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif k == curses.KEY_DOWN:
            self.sel = min(len(entries) - 1, self.sel + 1)
        elif k == ENTER and cur:
            kind, f, addr, _, _ = cur
            if kind == "fav":
                self.app.join(f["host"], int(f.get("port", DEFAULT_PORT)), f.get("password", ""))
            else:
                self.app.join(addr[0], addr[1], "")
        elif k == "a":
            self.edit_dialog(None)
        elif k == "e" and cur and cur[0] == "fav":
            self.edit_dialog(cur[1])
        elif k == "f" and cur and cur[0] == "lan":
            st = cur[3].status if cur[3] else None
            favs.append({"name": st.get("sv_hostname") if st else "", "host": cur[2][0], "port": cur[2][1],
                         "password": ""})
            self.app.save_profile()
            self.app.browser.refresh()
            self.app.msg(tr("Added to favorites."), C_OK)
        elif k in ("x", curses.KEY_DC) and cur and cur[0] == "fav":
            f = cur[1]

            def remove(_):
                favs.remove(f)
                self.app.save_profile()
            self.app.open(ConfirmDialog(tr("Remove"), [tr("Remove {name} from favorites?").format(
                name=f.get('name') or f['host'])], remove))
        elif k == "r":
            self.app.browser.refresh()
            self.app.msg(tr("Querying servers…"), C_INFO)
        else:
            return False
        return True

    def edit_dialog(self, fav):
        f = fav or {}

        def ok(v):
            host = v["host"].strip()
            if not valid_host(host):
                return tr('address: an IP or a host name (letters, digits, ".", "-")')
            try:
                port = _int(v["port"], 1, 65535)
            except ValueError as e:
                return tr("port: {why}").format(why=e)
            if v["password"] and not valid_password(v["password"]):
                return tr('password: no space, no quote, no ";", no "+"')
            new = {"name": v["name"].strip(), "host": host, "port": port, "password": v["password"]}
            if fav is None:
                self.app.profile["favorites"].append(new)
            else:
                fav.update(new)
            self.app.save_profile()
            self.app.browser.refresh()
            return None
        self.app.open(FormDialog(tr("Add a favorite") if fav is None else tr("Edit the favorite"), [
            ("name", tr("Name"), f.get("name", ""), tr("to find it again (empty: the name the server gives)"), False),
            ("host", tr("Address"), f.get("host", ""), tr("IP or host name, e.g. 192.168.1.20"), False),
            ("port", "Port", f.get("port", DEFAULT_PORT), tr("the server's net_port (3074 by default)"), False),
            ("password", tr("Password"), f.get("password", ""), tr("the players' one (g_password); empty if there is "
                                                                   "none"), True),
        ], ok, intro=[tr("Saved in profile.json (ZmClient's config folder, readable by you only).")]))


# -------------------------------------------------------------------------------------------------------------- Solo
class SoloView(RowsView):
    name, title = "solo", "Solo"
    hints = "Enter/Space edit  ? help  q quit"

    def rows(self):
        p, root = self.p, self.app.root
        bsp, layout = resolve_map(p["map"], root)

        def not_installed(label):
            return tr("{map}  (not installed)").format(map=label)
        maps = [(v, tr(label) if map_installed(bsp_, root) else not_installed(tr(label)),
                 (f"{bsp_} — {lay}" if lay else bsp_) if map_installed(bsp_, root) else
                 tr("{zone}: no zone in zone/, your Black Ops does not have this DLC").format(
                     zone=f"{bsp_} — {lay}" if lay else bsp_))
                for v, label, bsp_, lay in solo_maps(root)]
        no_horde = None if p["horde"] else tr("horde mode is off")
        specials = None
        if p["horde"]:
            if layout:
                specials = tr("not on a Mapkit map (Kino and Five only)")
            elif bsp == "zombie_temple":
                specials = tr("Shangri-La has them already")
            elif not specials_available(bsp, layout):
                specials = tr("Kino and Five only")
        else:
            specials = no_horde
        nightmare = None if nightmare_available(bsp, layout) else tr("Kino and Five only")
        if self.p["mode"] != "solo":
            mode_note = tr("the mode (F1) is not Solo: these settings are for the next solo game")
        else:
            mode_note = None
        shown_map = map_label(p["map"], root)
        rows = [
            Row("map", "Map", shown_map if map_installed(bsp, root) else not_installed(shown_map),
                self.choose("map", "Map", maps), disabled=mode_note),
            Row("god", "Invincible (god mode)", _yes(p["god"]), self.toggle("god")),
            Row("zinfo", tr("Zombie counter (Tab)"), _yes(p["zinfo"]), self.toggle("zinfo")),
            Row("noperks", tr("No perk machines"), _yes(p["noperks"]), self.toggle("noperks")),
            Row("quickrestart", tr("R restarts after game over"), _yes(p["quickrestart"]), self.toggle("quickrestart")),
            bo2_row(self, "bo2_weapons", root, bsp=bsp),
            dual_row(self, "dual_wield", root, bsp=bsp),
            Row("hitmarker", "Hit marker", _yes(p["hitmarker"]), self.toggle("hitmarker")),
            Row("unlimited_pap", tr("Unlimited Pack-a-Punch"), _yes(p["unlimited_pap"]), self.toggle("unlimited_pap"),
                disabled=None if unlimited_pap_installed(root) else
                tr("no mods/unlimitedpap/maps/_zombiemode_perks.gsc: write it from your zones "
                   "(tools/unlimitedpap/make_perks.py)")),
            Row("spawn_rate", tr("Zombie spawning"), _spawn_rate(p["spawn_rate"]),
                self.choose("spawn_rate", "Zombie spawning",
                            [(n, _spawn_rate(n), H.SPAWN_RATE_HELP[n]) for n in SPAWN_RATE_CHOICES])),
            Row("spawn_rush", tr("Sprint to the barricades"), _yes(p["spawn_rush"]), self.toggle("spawn_rush"),
                disabled=None if p["spawn_rate"] else tr("zombie spawning: game default")),
            section(tr("Game start")),
            Row("start_points", tr("Starting points"), _points(p["start_points"]),
                self.choose("start_points", "Starting points",
                            [(n, _points(n), H.ROW_HELP["start_points"]) for n in START_POINT_CHOICES])),
        ]
        rows += [Row("start_power", tr("Power on from the start"), _yes(p["start_power"]), self.toggle("start_power")),
                 Row("start_pap", tr("Pack-a-Punch from the start"), _yes(p["start_pap"]), self.toggle("start_pap")),
                 Row("far_respawn", tr("Bring far zombies closer"), _far(p["far_respawn"]),
                     self.choose("far_respawn", "Bring far zombies closer",
                                 [(n, _far(n), H.ROW_HELP["far_respawn"]) for n in FAR_RESPAWN_CHOICES]))]
        no_machines = tr("no perk machines (noperks): nothing to give") if p["noperks"] else None
        rows += [Row("start_perk", tr("Perk: {name}").format(name=label), _yes(key in p["start_perks"]),
                     self.toggle_perk(key), disabled=no_machines) for key, label in START_PERKS]
        rows += [
            section("Horde"),
            Row("horde", tr("Horde mode"), _yes(p["horde"]), self.toggle("horde")),
            Row("horde_max", tr("Zombies at once"), str(p["horde_max"]),
                self.ask("horde_max", "Zombies at once", "Number", "24 to 1024; above 300 it gets heavy",
                         lambda t: _int(t, 24, 1024)), disabled=no_horde),
            Row("horde_round", tr("Starting round"), str(p["horde_round"]),
                self.ask("horde_round", "Starting round", "Round", "1 to 255", lambda t: _int(t, 1, 255)),
                disabled=no_horde),
            Row("horde_napalm", tr("Napalm zombies"), _yes(p["horde_napalm"]), self.toggle("horde_napalm"),
                disabled=specials),
            Row("horde_sonic", tr("Shrieker zombies"), _yes(p["horde_sonic"]), self.toggle("horde_sonic"),
                disabled=specials),
            Row("horde_spawn_all", tr("Spawn from every window"), _yes(p["horde_spawn_all"]),
                self.toggle("horde_spawn_all"), disabled=no_horde),
            Row("horde_unjam", tr("Unstick the zombies"), _yes(p["horde_unjam"]), self.toggle("horde_unjam"),
                disabled=no_horde),
            Row("horde_clear_round", tr("Next round: all dead"), _yes(p["horde_clear_round"]),
                self.toggle("horde_clear_round"), disabled=no_horde),
            section(tr("Difficulty")),
            Row("difficulty", tr("Difficulty"), H.DIFFICULTY_LABELS[p["difficulty"]],
                self.choose("difficulty", "Difficulty", [
                    (0, "Normal", tr("the original game")),
                    (1, "Nightmare", tr("special enemies from several maps from round 1")),
                    (2, "Hell", tr("several of each at once"))]), disabled=nightmare),
        ]
        return rows

    def draw_footer(self, scr, y, bottom, width):
        if y + 1 >= bottom:
            return
        flags = " ".join(self.app.solo_flags())
        put(scr, y, 3, tr("Mod flags:"), curses.A_BOLD)
        for i, line in enumerate(wrap(flags or tr("(no flag)"), width - 6)):
            if y + 1 + i >= bottom:
                break
            put(scr, y + 1 + i, 3, line, color(C_DIM), width=width - 4)


def bo2_row(view, key, root, bsp=None, local_running=False):
    """The BO2 weapons row (the Solo view's, which the local server takes too), greyed without
    mods/bo2weapons/mod.ff, on Dead Ops Arcade, or while the local server runs (it took its mods when it started)."""
    labels = dict(BO2_WEAPON_CHOICES)
    if not bo2_weapons_installed(root):
        why = tr("no mods/bo2weapons/mod.ff: build it from your Black Ops II (docs/BO2_WEAPONS.md)")
    elif bsp is not None and not bo2_weapons_available(bsp):
        why = tr("Dead Ops Arcade has no box")
    elif local_running:
        why = tr("the local server is already running: it took its mods when it started")
    else:
        why = None
    return Row(key, tr("Black Ops II weapons"), tr(labels[view.p[key]]),
               view.choose(key, "Black Ops II weapons", [(v, tr(label), H.BO2_WEAPON_HELP[v])
                                                         for v, label in BO2_WEAPON_CHOICES]),
               disabled=why, help_text=H.ROW_HELP["bo2_weapons"])


def dual_row(view, key, root, bsp=None, local_running=False):
    """The dual-wield weapons row (solo and the local server: dual_wield, join: join_dual_wield), greyed without
    mods/dualwield/mod.ff, on Dead Ops Arcade, or while the local server runs."""
    if not dual_wield_installed(root):
        why = tr('no mods/dualwield/mod.ff: build it from the "Relaxing Dual Wield" mod (mods/dualwield)')
    elif bsp is not None and not bo2_weapons_available(bsp):
        why = tr("Dead Ops Arcade has no box")
    elif local_running:
        why = tr("the local server is already running: it took its mods when it started")
    else:
        why = None
    return Row(key, tr("Dual-wield weapons (Pack-a-Punch)"), _yes(view.p[key]), view.toggle(key), disabled=why,
               help_text=H.ROW_HELP["join_dual_wield" if key == "join_dual_wield" else "dual_wield"])


def split_row(view):
    p = view.p
    return Row("split", tr("Split screen (2 players)"), H.SPLIT_LABELS[p["split"]],
               view.choose("split", "Split screen", [(k, v, H.SPLIT_HELP[k]) for k, v in H.SPLIT_LABELS.items()]),
               disabled=tr("not in Solo: choose the Local server mode (Play view, F1)") if p["mode"] == "solo"
               else None)


def name_row(view):
    """The player name row, the same in the Play and Launch views."""
    return Row("name", tr("Player name"), view.p["name"] or tr("(from config.cfg)"),
               view.ask("name", "Player name", "Name", "empty: the one in config.cfg", _name))


# ------------------------------------------------------------------------------------------------------------ Launch
class LaunchView(RowsView):
    name, title = "launch", "Launch"
    hints = "Enter/Space edit  ? help  q quit"

    def tristate(self, key, title):
        return self.choose(key, title, [("", tr("game setting"), tr("nothing is added to the command line")),
                                        ("1", tr("yes"), ""), ("0", tr("no"), "")])

    @staticmethod
    def upscale_disabled(p):
        """Why the upscaler and sharpness rows are greyed, or None: supersampling only averages down."""
        if p["gfx_api"] != "vulkan" or p["fsr"] == "off":
            return tr("upscaling off")
        if p["fsr"] in SSAA_MODES:
            return tr("supersampling does not need it")
        return None

    def rows(self):
        p, app = self.p, self.app
        aim_off = tr("aim assist is off") if p["aim_assist"] == "0" else None
        split_off = tr("split screen places both windows itself") if split_on(p) else None
        no_split = None if split_on(p) else (tr("not in Solo") if p["mode"] == "solo" and p["split"] != "off"
                                             else tr("split screen off"))
        password = app.local_password()
        language_help = tr("Language of ZmClient. The game itself is not affected.")
        rows = [
            Row("language", tr("Language"), LANGUAGE_NAMES.get(p["language"], p["language"]),
                self.choose("language", "Language", [(k, v, language_help) for k, v in LANGUAGE_NAMES.items()]),
                help_text=language_help),
            name_row(self),
            Row("window", tr("Display"), H.WINDOW_LABELS[p["window"]],
                self.choose("window", "Display", [(k, v, H.ROW_HELP["window"]) for k, v in H.WINDOW_LABELS.items()]),
                disabled=split_off),
            Row("window_size", tr("Resolution"), p["window_size"],
                self.ask("window_size", "Resolution", "Size", "WIDTHxHEIGHT, e.g. 1920x1080", size_value),
                disabled=split_off or (None if p["window"] != "borderless" else
                                       tr("Borderless takes the screen's size"))),
            Row("fps_counter", tr("Port's FPS counter"), _yes(p["fps_counter"]), self.toggle("fps_counter")),
            Row("shader_warming", tr("Shader warming"), _yes(p["shader_warming"]), self.toggle("shader_warming")),
            Row("run_info", tr("Speedrun info"), H.RUN_INFO_LABELS[p["run_info"]],
                self.choose("run_info", "Speedrun info",
                            [(k, v, H.ROW_HELP["run_info"]) for k, v in H.RUN_INFO_LABELS.items()])),
            Row("gfx_api", tr("Graphics API"), H.GFX_API_LABELS[p["gfx_api"]],
                self.choose("gfx_api", "Graphics API",
                            [(k, v, H.GFX_API_HELP[k]) for k, v in H.GFX_API_LABELS.items()])),
            Row("fsr", tr("Upscaling"), H.FSR_LABELS[p["fsr"]],
                self.choose("fsr", "Upscaling", [(k, v, H.FSR_HELP[k]) for k, v in H.FSR_LABELS.items()]),
                disabled=None if p["gfx_api"] == "vulkan" else tr("with the Vulkan graphics API only")),
            Row("upscaler", tr("Upscaling method"), H.UPSCALER_LABELS[p["upscaler"]],
                self.choose("upscaler", "Upscaling method",
                            [(k, v, H.UPSCALER_HELP[k]) for k, v in H.UPSCALER_LABELS.items()]),
                disabled=self.upscale_disabled(p)),
            Row("fsr_sharpness", tr("Sharpness"), H.FSR_SHARPNESS_LABELS[p["fsr_sharpness"]],
                self.choose("fsr_sharpness", "Sharpness",
                            [(k, v, H.ROW_HELP["fsr_sharpness"]) for k, v in H.FSR_SHARPNESS_LABELS.items()]),
                disabled=self.upscale_disabled(p)),
            Row("scene_models", tr("Models drawn per frame"), str(p["scene_models"]),
                self.choose("scene_models", "Models drawn per frame", [
                    (1024, "1024", tr("the original game")),
                    (2048, "2048", tr("imported maps (Nuketown): more scenery in the distance")),
                    (4096, "4096", tr("imported maps: all the scenery; a little heavier"))])),
            section(tr("Split screen: 2 players on this PC")),
            split_row(self),
            Row("split_layout", tr("Layout"), H.SPLIT_LAYOUT_LABELS[p["split_layout"]],
                self.choose("split_layout", "Layout of the two windows",
                            [(k, v, H.SPLIT_LAYOUT_HELP[k]) for k, v in H.SPLIT_LAYOUT_LABELS.items()]),
                disabled=no_split),
            Row("name2", tr("Player 2 name"), p["name2"] or f"({DEFAULT_NAME2})",
                self.ask("name2", "Player 2 name", "Name", tr("empty: {name}").format(name=DEFAULT_NAME2), _name),
                disabled=no_split),
            Row("split_sound2", tr("Player 2 sound"), _yes(p["split_sound2"]), self.toggle("split_sound2"),
                disabled=no_split),
            section(tr("Controller: aim assist")),
            Row("aim_assist", tr("Aim assist"), H.TRISTATE_LABELS[p["aim_assist"]],
                self.tristate("aim_assist", "Aim assist")),
            Row("aim_slowdown", tr("Slow down on a zombie"), H.TRISTATE_LABELS[p["aim_slowdown"]],
                self.tristate("aim_slowdown", "Slow down on a zombie"), disabled=aim_off),
            Row("aim_lockon", tr("Follow a zombie"), H.TRISTATE_LABELS[p["aim_lockon"]],
                self.tristate("aim_lockon", "Follow a zombie"), disabled=aim_off),
            Row("aim_autoaim", tr("Auto-aim (ADS)"), H.TRISTATE_LABELS[p["aim_autoaim"]],
                self.tristate("aim_autoaim", "Auto-aim"), disabled=aim_off),
            section(tr("Local server (Local server mode)")),
            Row("map", tr("Game"),
                tr("{map}; {mods}").format(map=map_label(p['map'], app.root), mods=app.solo_summary()),
                lambda: self.app.show(2), help_text=H.ROW_HELP["host_game"]),
            Row("host_port", "Port", str(p["host_port"]),
                self.ask("host_port", "Local server port", "Port", "3074 by default", lambda t: _int(t, 1, 65535))),
            Row("host_password", tr("rcon password"), "•" * len(password) if password else tr("(no folder)"),
                self.edit_password, disabled=None if app.dist else tr("no game folder")),
        ]
        return rows

    def edit_password(self):
        def ok(v):
            if not valid_password(v):
                return tr('no space, no quote, no ";", no "+"')
            self.app.set_local_password(v)
            return None
        self.app.open(InputDialog(tr("Local server rcon password"), tr("Password"), self.app.local_password(),
                                  tr("shared with ZmAdmin; used at the next start of the server"), ok))


# ------------------------------------------------------------------------------------------------------- Game config
class ConfigView(RowsView):
    name, title = "config", "Game config"
    hints = "Enter edit  Ctrl+S save  u undo  n other dvar  b keys  r reload  ? help"

    def __init__(self, app):
        super().__init__(app)
        self.edits = {}             # setting or dvar -> new value
        self.bind_edits = {}        # key -> new command ("" removes the bind)
        self.loaded = False

    @property
    def cfg(self):
        return self.app.gamecfg

    def on_show(self):
        if not self.loaded and self.cfg:
            self.cfg.load()
            self.loaded = True

    def rows(self):
        if not self.cfg:
            return [Row(None, tr("No game folder"), "", None, disabled=tr("ZmClient is not next to BO1Zombies"))]
        rows = []
        for name, label, kind, opts, help_text in SETTINGS:
            edited = name in self.edits
            value = self.edits[name] if edited else self.cfg.value(name)
            shown = {"0": tr("0 (no)"), "1": tr("1 (yes)")}.get(value, value) if kind == "bool" else value
            rows.append(Row(name, ("* " if edited else "  ") + tr(label),
                            shown if value != "" else tr("(game default)"),
                            lambda n=name: self.edit(n), help_text=tr("{name}: {help}").format(name=name,
                                                                                               help=tr(help_text))))
            if name == "bo1_mod_fov":
                rows.append(self.resolution_row())
        others = [n for n in self.edits if n not in BY_NAME]
        if others or self.bind_edits:
            rows.append(section(tr("Other changes")))
        for n in others:
            rows.append(Row(n, f"* {n}", self.edits[n], lambda n=n: self.edit(n),
                            help_text=tr('Current value in the file: "{value}".').format(
                                value=self.cfg.values.get(n, ''))))
        for k, v in self.bind_edits.items():
            rows.append(Row(f"bind:{k}", tr("* key {key}").format(key=k), v or tr("(removed)"),
                            lambda k=k: self.edit_bind(k),
                            help_text=tr('Current command: "{command}".').format(command=self.cfg.binds.get(k, ''))))
        return rows

    def buttons(self):
        return [(tr("Save"), CTRL_S), (tr("Undo the changes"), "u"), (tr("Other dvar"), "n"), (tr("Keys"), "b"),
                (tr("Reload"), "r")]

    def resolution_row(self):
        """The Launch view's resolution (profile window_size), not a config.cfg line: changed here, it is saved at
        once, as in the Launch view."""
        p = self.p
        mode = H.WINDOW_LABELS[p["window"]]
        note = " " + tr("(no effect: Borderless)") if p["window"] == "borderless" else ""
        return Row("window_size", "  " + tr("Resolution (Launch view)"), p["window_size"] + note,
                   self.ask("window_size", "Resolution", "Size", "WIDTHxHEIGHT, e.g. 1920x1080", size_value),
                   help_text=tr("The same as the Launch view (F4), given to the game on the command line at every "
                                "launch: r_mode in Full screen, r_customMode in Window. Current display: {mode}; in "
                                "Borderless, the game takes the screen's size. Saved at once, not in "
                                "config.cfg.").format(mode=mode))

    def draw_header(self, scr, top, width):
        if not self.cfg:
            return top
        state = self.cfg.path if self.cfg.exists else tr("{path} (not created yet: the game writes it when it "
                                                         "quits)").format(path=self.cfg.path)
        put(scr, top, 1, state, color(C_DIM), width=width - 2)
        if self.app.client and self.app.client.running():
            put(scr, top + 1, 1, tr("The game is running: it will rewrite this file when it quits. Quit it before "
                                    "saving."), color(C_WARN), width=width - 2)
        return top + 2

    def edit(self, name):
        setting = BY_NAME.get(name)
        current = self.edits.get(name, self.cfg.value(name))

        def keep(v):
            value, why = validate(name, v)
            if why:
                return why
            if value == self.cfg.value(name):
                self.edits.pop(name, None)
            else:
                self.edits[name] = value
            return None
        if setting and setting[2] == "bool":
            keep("0" if current == "1" else "1")
        elif setting and setting[2] in ("choice", "picmip"):
            self.app.open(ChoiceDialog(tr(setting[1]), [(o, o, "") for o in setting[3]], keep, current=current))
        else:
            self.app.open(InputDialog(tr(setting[1]) if setting else name, tr("Value"), current,
                                      tr(setting[4])[:70] if setting else tr("text, without quotes"), keep))

    def other_dvar(self):
        def ok(v):
            name = v["name"].strip()
            if not name or not name.replace("_", "").isalnum():
                return tr('a dvar name: letters, digits, "_"')
            value, why = validate(name, v["value"])
            if why:
                return why
            self.edits[name] = value
            return None
        self.app.open(FormDialog(tr("Other dvar"), [
            ("name", tr("Name"), "", tr("e.g. cg_fov_default, r_aspectRatio"), False),
            ("value", tr("Value"), "", tr('written as: seta name "value"'), False),
        ], ok, intro=[tr("{n} dvars in the file. A missing dvar is added.").format(n=len(self.cfg.values))]))

    def edit_bind(self, key=None):
        def set_command(k):
            def ok(v):
                if '"' in v:
                    return tr("no quotes")
                self.bind_edits[k] = v.strip()
                return None
            self.app.open(InputDialog(tr("Key {key}").format(key=k), tr("Command"),
                                      self.bind_edits.get(k, self.cfg.binds.get(k, "")),
                                      tr("e.g. +attack, weapnext; empty: remove the key"), ok))
        if key:
            set_command(key)
            return
        items = [(k, f"{k:<14} {v}", "") for k, v in sorted(self.cfg.binds.items())]
        items.append(("__new__", tr("(another key…)"), tr("type its name: F1, KP_ENTER, MOUSE4, a…")))

        def picked(k):
            if k != "__new__":
                set_command(k)
                return

            def ok(v):
                if not valid_bind_key(v.strip()):
                    return tr('a key name: letters, digits, "_"')
                set_command(v.strip())
                return None
            self.app.open(InputDialog(tr("New key"), tr("Key"), "", tr("its name for the game, e.g. F5, MOUSE4"), ok))
        self.app.open(ChoiceDialog(tr("Keys"), items, picked))

    def save(self):
        if not self.edits and not self.bind_edits:
            self.app.msg(tr("Nothing to save."), C_INFO)
            return
        if self.app.client and self.app.client.running():
            self.app.msg(tr("The game is running: it would rewrite config.cfg when it quits. Quit it, then save."),
                         C_ERR)
            return
        values = self.cfg.changes(self.edits)
        binds = {k: v for k, v in self.bind_edits.items() if v}
        unbound = {k for k, v in self.bind_edits.items() if not v}
        try:
            self.cfg.save(values, binds, unbound)
        except OSError as e:
            self.app.msg(tr("config.cfg not written: {error}").format(error=e), C_ERR)
            return
        n = len(self.edits) + len(self.bind_edits)
        self.edits.clear()
        self.bind_edits.clear()
        self.app.msg(tr("config.cfg saved ({n} change(s)).").format(n=n), C_OK)

    def key(self, k):
        if not self.cfg:
            return False
        if k == CTRL_S:
            self.save()
        elif k == "u":
            self.edits.clear()
            self.bind_edits.clear()
            self.app.msg(tr("Changes undone."), C_INFO)
        elif k == "n":
            self.other_dvar()
        elif k == "b":
            self.edit_bind()
        elif k == "r":
            def reload(_=None):
                self.cfg.load()
                self.edits.clear()
                self.bind_edits.clear()
                self.app.msg(tr("config.cfg reloaded."), C_INFO)
            if self.edits or self.bind_edits:
                self.app.open(ConfirmDialog(tr("Reload"), [tr("Reload config.cfg and lose the changes?")], reload))
            else:
                reload()
        else:
            return super().key(k)
        return True


# ------------------------------------------------------------------------------------------------------------- Extra
class ExtraView(View):
    name, title = "extra", "Free dvars"
    hints = "a add  e edit  x remove  Space toggle  ? help"

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    @property
    def lines(self):
        return self.app.profile["extra"]

    def draw(self, scr, top, height, width):
        lines = self.lines
        self.sel = max(0, min(self.sel, len(lines) - 1))
        put(scr, top, 1, tr("Commands added to the command line, in order, before the map or the connection:"),
            curses.A_BOLD)
        y = top + 2
        if not lines:
            put(scr, y, 3, tr('None: "a" adds one (e.g. "set bo1_frameperf 200").'), color(C_INFO))
            y += 1
        # the command column takes what its lines need, up to half the width; the description gets the rest
        cmd_w = min(max([len(e["text"]) + 1 for e in lines] + [20]), (width - 10) // 2)
        desc_x = 7 + cmd_w + 2       # the command starts at 7, after "  [x] "
        if lines:
            put(scr, y - 1, 7, f"{tr('Command'):<{cmd_w}}  Description", color(C_DIM))
        shown = lines[:max(0, height - 12)]
        for i, e in enumerate(shown):
            mark = "[x]" if e.get("on") else "[ ]"
            why = check_extra(e["text"])
            sel = i == self.sel
            attr = curses.A_REVERSE if sel else (color(C_ERR) if why else 0)
            command = "+" + e["text"]
            if len(command) > cmd_w:
                command = command[:cmd_w - 1] + "…"
            put(scr, y, 1, f"  {mark} {command:<{cmd_w}}".ljust(width - 2), attr)
            short = why or describe(e["text"])[0]
            put(scr, y, desc_x, short, attr | (0 if sel or why else color(C_DIM)), width=width - desc_x - 1)
            self.zone(y, 1, 6, lambda i=i: self.select(i, " "))
            self.zone(y, 7, width - 8, lambda i=i: self.select(i), lambda i=i: self.select(i, "e"))
            y += 1
        y += 1
        x = 3
        for label, k in (("Add", "a"), ("Edit", "e"), ("Remove", "x"), ("Toggle", " ")):
            x = self.button(scr, y, x, f"[ {tr(label)} ]", curses.A_BOLD, lambda k=k: self.key(k))
        y += 2
        cur = lines[self.sel] if lines else None
        detail = describe(cur["text"])[1] if cur else ""
        if detail:
            put(scr, y, 3, f"+{cur['text']}", curses.A_BOLD | color(C_INFO), width=width - 4)
            y += 1
            for line in wrap(detail, width - 6)[:max(0, top + height - y - 3)]:
                put(scr, y, 3, line)
                y += 1
            y += 1
        for line in wrap(tr('Each line becomes "+line". No "+" inside a line: the game cuts its command line at each '
                            '"+" and keeps only 63 of them; ZmClient refuses to launch beyond that.'), width - 6):
            if y >= top + height:
                break
            put(scr, y, 3, line, color(C_DIM))
            y += 1

    def select(self, i, then=None):
        self.sel = i
        if then:
            self.key(then)

    def edit(self, entry, initial="set "):
        def ok(v):
            why = check_extra(v)
            if why:
                return why
            if entry is None:
                self.lines.append({"on": True, "text": v.strip()})
                self.sel = len(self.lines) - 1
            else:
                entry["text"] = v.strip()
            self.app.save_profile()
            return None
        intro = None
        if entry is None and initial.split()[1:]:
            intro = [describe(initial)[1]]
        self.app.open(InputDialog(tr("Add a command") if entry is None else tr("Edit the command"), tr("Command"),
                                  entry["text"] if entry else initial,
                                  tr('without the "+": "set r_fog 0", "set bo1_frameperf 200"'), ok, intro=intro))

    def add(self):
        """The known dvars first (dvarhelp), each with its description; then the command, prefilled."""
        items = [("", tr("(a free command…)"), tr("any command or dvar, typed in full"))]
        items += [(name, f"{name:<27} {short}", long) for name, (short, long) in sorted(KNOWN.items(),
                                                                                        key=lambda kv: kv[0].lower())]
        self.app.open(ChoiceDialog(tr("Add a command"), items,
                                   lambda name: self.edit(None, f"set {name} " if name else "set ")))

    def key(self, k):
        lines = self.lines
        cur = lines[self.sel] if lines else None
        if k == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif k == curses.KEY_DOWN:
            self.sel = min(len(lines) - 1, self.sel + 1)
        elif k == "a":
            self.add()
        elif k in ("e", ENTER) and cur:
            self.edit(cur)
        elif k == " " and cur:
            cur["on"] = not cur.get("on")
            self.app.save_profile()
        elif k in ("x", curses.KEY_DC) and cur:
            def remove(_):
                lines.remove(cur)
                self.app.save_profile()
            self.app.open(ConfirmDialog(tr("Remove"), [tr('Remove "+{command}"?').format(command=cur['text'])], remove))
        else:
            return False
        return True


# ------------------------------------------------------------------------------------------------------------- Setup
class SetupView(View):
    name, title = "setup", "Setup"
    hints = "c choose the install  v videos  z zones  s Vulkan shaders  i install  Esc cancel  r refresh  ? help"

    def __init__(self, app):
        super().__init__(app)
        self.state = None
        self.state_at = 0.0
        self.installs = None

    def on_show(self):
        self.state_at = 0.0
        if self.installs is None:
            self.installs = gamesetup.find_installs()
            if not self.app.profile["steam_install"] and self.installs:
                self.app.profile["steam_install"] = self.installs[0]
                self.app.save_profile()

    def draw(self, scr, top, height, width):
        app = self.app
        if not app.dist:
            put(scr, top + 1, 3, tr("No game folder: ZmClient must be next to BO1Zombies (or --dist)."),
                color(C_ERR))
            return
        now = time.monotonic()
        job = app.setup_job
        if self.state is None or now - self.state_at > 3 or (job and job.finished and self.state_at < job.ended):
            self.state = gamesetup.state(app.root)
            self.state_at = now
        p = app.profile
        install = p["steam_install"]
        y = top
        put(scr, y, 1, tr("Black Ops install:"), curses.A_BOLD)
        valid = gamesetup.is_install(install)
        put(scr, y, 29, install or tr('(none found: "c" to type it)'),
            color(C_OK if valid else C_ERR), width=width - 30)
        y += 1
        put(scr, y, 29, tr("read only, never modified") if valid else
            tr("not an install (zone/, main/*.iwd, localization.txt expected)"), color(C_DIM), width=width - 30)
        y += 1
        put(scr, y, 1, f"{tr('Package folder:'):<28}{app.root}", color(C_DIM), width=width - 2)
        y += 2
        labels = {"localization": "localization.txt", "iwd": "main/*.iwd", "video": "main/video/",
                  "zones": tr("zone/ (converted)"), "pack": "shaders.pack", "spirv": "shaders.spv"}
        needs_pack = gamesetup.Layout(app.root).needs_pack
        for part, (ok, text) in self.state.items():
            optional = part in gamesetup.OPTIONAL or (part == "pack" and not needs_pack)
            mark, pair = (OK_MARK, C_OK) if ok else (BAD_MARK, C_WARN if optional else C_ERR)
            put(scr, y, 3, f"{mark} {labels[part]:<20}", color(pair))
            put(scr, y, 27, text, 0, width=width - 28)
            y += 1
        y += 1
        put(scr, y, 3, f"[{'x' if p['setup_video'] else ' '}] " + tr("copy the videos (cutscenes, ~1 GB)"),
            curses.A_BOLD if not job else color(C_DIM))
        self.zone(y, 3, 45, lambda: self.key("v"))
        y += 1
        put(scr, y, 3, f"[{'x' if p['setup_convert'] else ' '}] " + tr("convert the zones (ffconv, ~6 minutes)"),
            curses.A_BOLD if not job else color(C_DIM))
        self.zone(y, 3, 45, lambda: self.key("z"))
        y += 1
        put(scr, y, 3, f"[{'x' if p['setup_spirv'] else ' '}] " +
            tr("compile the Vulkan shaders (shaders.spv, 5 to 15 minutes)"), curses.A_BOLD if not job else color(C_DIM))
        self.zone(y, 3, 60, lambda: self.key("s"))
        y += 2
        x = 3
        running = job and not job.finished
        buttons = [(tr("Cancel the install"), ESC)] if running else [(tr("Choose the install"), "c"),
                                                                     (tr("Install"), "i"), (tr("Refresh"), "r")]
        for label, k in buttons:
            x = self.button(scr, y, x, f"[ {label} ]", curses.A_BOLD, lambda k=k: self.key(k))
        y += 2
        if job:
            if job.phase == "copying" and job.total_bytes:
                pct = 100 * job.done_bytes // job.total_bytes
                status = tr("Copy: {done} / {total} MB ({pct}%)").format(
                    done=job.done_bytes >> 20, total=job.total_bytes >> 20, pct=pct)
            elif job.phase == "converting zones" and job.zone_count:
                status = tr("Conversion: zone {at} / {count}").format(at=job.zone_at, count=job.zone_count)
            elif job.phase == "Vulkan shaders" and job.shader_count:
                status = tr("Vulkan shaders: {at} / {count}").format(at=job.shader_at, count=job.shader_count)
            else:
                phase = tr(job.phase)
                status = phase[:1].upper() + phase[1:]
            warned = job.finished and not job.error and job.warning
            if job.finished:
                status = (tr("Failed: {error}").format(error=job.error) if job.error else
                          tr("Install finished, except Vulkan: {warning}").format(warning=job.warning)
                          if warned else tr("Install finished."))
            put(scr, y, 3, status, color(C_ERR if job.finished and job.error else C_WARN if warned else C_OK
                                         if job.finished else C_INFO), width=width - 4)
            y += 1
            for line in job.lines[-max(0, top + height - y - 1):]:
                put(scr, y, 5, line, color(C_DIM), width=width - 6)
                y += 1

    def choose_install(self):
        def keep(path):
            path = path.strip().strip('"')
            if not gamesetup.is_install(path):
                return tr("not a Black Ops install (zone/, main/*.iwd, localization.txt)")
            self.app.profile["steam_install"] = os.path.normpath(os.path.abspath(path))
            self.app.save_profile()
            return None

        def typed():
            self.app.open(InputDialog(tr("Black Ops install"), tr("Folder"), self.app.profile["steam_install"],
                                      tr("the folder that holds BlackOps.exe"), keep))

        def browse():
            start = start_folder(self.app.profile["steam_install"], self.installs or [])
            self.app.open(FolderDialog(tr("Choose the Black Ops folder"), start, keep))
        items = [(p, p, tr("found in a Steam library")) for p in self.installs or []]
        items.append(("__browse__", tr("(browse the folders…)"), tr("move through the folders with the arrows")))
        items.append(("__typed__", tr("(type the path…)"), tr("another folder")))

        def picked(v):
            if v == "__browse__":
                browse()
            elif v == "__typed__":
                typed()
            else:
                self.app.profile["steam_install"] = v
                self.app.save_profile()
        self.app.open(ChoiceDialog(tr("Black Ops install"), items, picked,
                                   current=self.app.profile["steam_install"]))

    def key(self, k):
        app = self.app
        running = app.setup_job and not app.setup_job.finished
        if k == ESC:
            if running:
                app.setup_job.cancel()
                app.msg(tr("Cancelling…"), C_WARN)
                return True
            return False
        if running:
            if k in ("c", "i", "v", "z", "s"):
                app.msg(tr("An install is running."), C_WARN)
                return True
            return False
        if k == "c":
            self.choose_install()
        elif k == "v":
            app.profile["setup_video"] = not app.profile["setup_video"]
            app.save_profile()
        elif k == "z":
            app.profile["setup_convert"] = not app.profile["setup_convert"]
            app.save_profile()
        elif k == "s":
            app.profile["setup_spirv"] = not app.profile["setup_spirv"]
            app.save_profile()
        elif k == "r":
            self.installs = gamesetup.find_installs()
            self.state_at = 0.0
        elif k == "i":
            app.start_setup()
        else:
            return False
        return True


# --------------------------------------------------------------------------------------------------------------- Log
class LogView(AdminLogView):
    name, title = "log", "Log"

    def draw(self, scr, top, height, width):
        path = self.app.log_path
        if not path:
            put(scr, top + 1, 3, tr("No game folder: nothing to follow."), color(C_INFO))
            return
        shown = [l for l in self.lines if self.filter.lower() in l.lower()] if self.filter else list(self.lines)
        rows = height - 1
        self.scroll = max(0, min(self.scroll, len(shown) - rows))
        end = len(shown) - self.scroll
        if not shown:
            put(scr, top + 1, 3, tr("Nothing yet: the log shows up when the game writes its console_mp.log."),
                color(C_INFO))
        for i, line in enumerate(shown[max(0, end - rows):end]):
            low = line.lower()
            pair = C_ERR if "error" in low else C_WARN if "warning" in low else 0
            put(scr, top + i, 1, line, color(pair) if pair else 0, width=width - 2)
        state = []
        if self.filter:
            state.append(tr('filter "{filter}": {n} lines').format(filter=self.filter, n=len(shown)))
        if self.paused:
            state.append(tr("PAUSED (Space to resume)"))
        elif self.scroll:
            state.append(tr("{n} lines further down (End)").format(n=self.scroll))
        buttons = ((f"[ {tr('Filter')} ]", "/"), (f"[ {tr('Resume')} ]" if self.paused else "[ Pause ]", " "),
                   (f"[ {tr('End')} ]", curses.KEY_END))
        bw = sum(len(b) + 1 for b, _ in buttons)
        put(scr, top + height - 1, 1, " | ".join(state) or path, color(C_WARN if state else C_DIM),
            width=width - 3 - bw)
        x = width - bw
        for label, k in buttons:
            put(scr, top + height - 1, x, label, curses.A_BOLD)
            self.zone(top + height - 1, x, len(label), lambda k=k: self.key(k))
            x += len(label) + 1
