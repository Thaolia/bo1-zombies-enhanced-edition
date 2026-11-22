"""Local server profiles without curses: a profile's saved game, and starting it as saved (the Servers view's Enter,
zmadmin --start). config.py keeps the profiles, launcher.py runs them.

A profile's server.cfg runs after its command line's +set (docs/SERVER.md, "Settings and their order"), so a setting
the Settings view kept wins over the same dvar on the game's line (zm_startpoints, bo2weapons_box...). The latest
explicit choice wins: choosing the game again (configure_game) drops the kept settings its new line sets.
"""
import os

from . import gamemods
from .launcher import LocalServer, server_game
from .settings import BY_NAME, build_server_cfg


def local_game(local):
    """A profile's saved game; a servers.json of an older ZmAdmin kept only the map and two mods."""
    if isinstance(local.get("game"), dict):
        return local["game"]
    box = local.get("bo2_box")
    return {"map": local.get("map", "zombie_theater"), "bo2_weapons": 0 if box is None else box + 1,
            "dual_wield": bool(local.get("dual_wield"))}


def profile_configured(local):
    """The profile was set up once (its game chosen), so it can start without asking anything. A ZmAdmin older than
    the saved game kept bo2_box and dual_wield instead."""
    return isinstance(local.get("game"), dict) or "bo2_box" in local or "dual_wield" in local


def start_profile(config, dist, server, name):
    """Starts profile `name` with what it saved: its server.cfg is written from its kept settings first. Returns
    None, or why not (raises nothing)."""
    local = config.local_profile(dist.root, name)
    if local is None:
        return f"pas de profil « {name} »"
    if server.running():
        return f"« {name} » tourne déjà (PID {server.pid})"
    for other, entry in config.local_profiles(dist.root):
        if other != name and LocalServer(dist, other).running() and abs(int(entry["port"]) - int(local["port"])) < 2:
            return (f"le port {local['port']} touche celui de « {other} » ({entry['port']}), qui tourne : chaque "
                    "serveur prend aussi port + 1")
    why = write_profile_cfg(server.home, local.get("settings") or {}, name)
    if why:
        return why
    try:
        server.start(local_game(local), int(local["port"]), local["password"])
    except (OSError, RuntimeError) as e:
        return f"lancement impossible : {e}"
    return None


def line_settings(game, dist_root):
    """The Settings view's dvars (settings.SETTINGS) that a game's command line sets."""
    argv = gamemods.mod_flags(server_game(game), dist_root)
    return {argv[i + 1] for i in range(len(argv) - 1) if argv[i] == "+set" and argv[i + 1] in BY_NAME}


def configure_game(local, game, home, name, dist_root):
    """Saves a newly chosen game in profile `local`; the kept settings its line sets go, from the profile and its
    server.cfg. Returns None, or why server.cfg could not be written."""
    local.update(map=game["map"], game=dict(game))
    settings = local.setdefault("settings", {})
    dropped = line_settings(game, dist_root) & set(settings)
    for n in dropped:
        del settings[n]
    return write_profile_cfg(home, settings, name, drop=dropped) if dropped else None


def write_profile_cfg(home, settings, name, drop=()):
    """The profile's server.cfg rebuilt from its kept settings, without the lines that set a name of `drop` (its other
    lines stay). None, or why not."""
    path = home.server_cfg
    try:
        with open(path, encoding="latin-1") as f:
            text = f.read()
    except FileNotFoundError:
        text = None
    except OSError as e:
        return f"server.cfg illisible : {e}"
    if text is None and not settings:
        return None
    new = build_server_cfg(text, settings, name, drop)
    if new == text:
        return None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="latin-1", newline="\n") as f:
            f.write(new)
    except OSError as e:
        return f"server.cfg non écrit : {e}"
    return None
