"""ZmClient's profile (what to play and how) and the client command line it gives.

The solo part follows tools/mod-launcher.hta's args() rule for rule (horde, mapkit, nightmare, zinfo, noperks, quick
restart); the base and the join part follow Play.bat / play.sh (tools/make_dist.sh) and the Switch launcher
(src/platform/switch/launcher_config.cpp).
"""
import copy
import json
import os
import re

from zmadmin.gamemods import (  # noqa: F401  (the views and tests read them here)
    BASE_MAPS, BO2_WEAPON_CHOICES, CLIENT_DVARS, FAR_RESPAWN_CHOICES, MAPKIT_BSP_WORLDS, MAPKIT_FX_ZONES,
    MAPKIT_LABELS, MAPKIT_ZONES, MAP_LABELS, MOD_DEFAULTS, NIGHTMARE_MAPS, SPAWN_RATE_CHOICES, START_PERKS,
    START_POINT_CHOICES, add_admin_mod, add_bo2_weapons, bo2_weapons_available, bo2_weapons_installed,
    bsp_world_files, client_values, dual_wield_installed, installed_maps, line_values, map_installed, map_label,
    mapkit_layouts, missing_files, mod_flags, nightmare_available, resolve_map, solo_maps, specials_available,
    stack_mod, unlimited_pap_installed)

# the Solo view's line is the one a server gets
solo_mod_flags = mod_flags

MODES = ("solo", "join", "host")
WINDOW_MODES = ("borderless", "window", "fullscreen")
# Split screen on one PC: two game windows side by side, each a client of the local or the remote server. The engine's
# bo1_splitInput tells each window its input (kbm: keyboard and mouse; padN: controller N only, focused or not) and
# r_borderlessRect the part of the monitor it takes (x,y,w,h in fractions of it). Player 2 has its own fs_h (SPLIT2_HOME
# under the game folder): its own config, profile and log.
SPLIT_MODES = ("off", "kbm_pad", "pad_pad")
SPLIT_LAYOUTS = ("side", "stack")
SPLIT_INPUTS = {"kbm_pad": ("kbm", "pad0"), "pad_pad": ("pad0", "pad1")}
SPLIT_RECTS = {"side": ("0,0,0.5,1", "0.5,0,0.5,1"), "stack": ("0,0,1,0.5", "0,0.5,1,0.5")}
SPLIT2_HOME = "split2"
DEFAULT_NAME2 = "Joueur2"
DEFAULT_PORT = 3074

AIM_DVARS = (("aim_assist", "bo1_aimassist"), ("aim_slowdown", "aim_slowdown_enabled"),
             ("aim_lockon", "aim_lockon_enabled"), ("aim_autoaim", "aim_autoaim_enabled"))
MAX_COMMAND_LINES = 63      # Com_ParseCommandLine keeps 64 lines, the first being the text before the first '+'
# r_mod_sceneModels: the models the renderer draws per frame (retail 1024, the engine's cap 4096). A map imported by
# MapKit (Nuketown: 2 096 props) needs more; each model past retail's also takes a model lighting entry
SCENE_MODEL_CHOICES = (1024, 2048, 4096)
MODEL_LIGHTING_ENTRIES_MAX = 5120   # r_mod_modelLightingEntries' cap (r_model_lighting.cpp)
# The renderer (docs/VULKAN.md): "default" is the system's Direct3D 9 on Windows and OpenGL on Linux; "vulkan" is
# r_mod_gfxApi vulkan on win64 (an archived dvar, so ZmClient always sets it) and BO1_GFX_BACKEND=vulkan on Linux.
GFX_APIS = ("default", "vulkan")

DEFAULTS = {
    "mode": "solo",
    **MOD_DEFAULTS,
    "god": False,
    "name": "",
    "split": "off",                     # one of SPLIT_MODES
    "split_layout": "side",             # one of SPLIT_LAYOUTS
    "split_sound2": False,              # player 2's window plays the sound too (both windows hear the same game)
    "name2": "",                        # player 2's name; empty: DEFAULT_NAME2
    "window": "borderless",
    "window_size": "1280x720",
    "fps_counter": False,
    "run_info": 1,                      # bo1_runinfo: 0 off, 1 on the loading screen, 2 also in a corner in game
    "scene_models": 1024,              # one of SCENE_MODEL_CHOICES
    "gfx_api": "default",              # one of GFX_APIS
    # aim assist (gamepad): "" leaves the game's value, "1" / "0" sets it
    "aim_assist": "",
    "aim_slowdown": "",
    "aim_lockon": "",
    "aim_autoaim": "",
    "join_host": "",
    "join_port": DEFAULT_PORT,
    "join_password": "",                # the server's g_password, not rcon
    "host_port": DEFAULT_PORT,
    # the local server runs the Solo view's game (map, mods); its clients load what that game needs (host_values)
    # ask the server what to load (getmodinfo, with join_password) and load it; without an answer, the two below
    "join_detect_mods": True,
    "join_bo2_weapons": False,          # load mods/bo2weapons/mod.ff to join a server that has the BO2 weapons
    "join_dual_wield": False,           # load mods/dualwield/mod.ff to join a server that has them
    "extra": [],                        # {"on": bool, "text": "set r_foo 1"}: one + command each
    "favorites": [],                    # {"name", "host", "port", "password"}
    "steam_install": "",                # the Black Ops install the Installation view copies from
    "setup_video": True,
    "setup_convert": True,
}

_NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,15}$")
_HOST = re.compile(r"^[A-Za-z0-9.\-]{1,63}$")
_SIZE = re.compile(r"^(\d{3,5})x(\d{3,5})$")
_TOKEN = re.compile(r'^[^\s";+]+$')


def valid_name(name):
    """The Switch launcher's rule (Launcher_ValidPlayerName): 1-15 letters, digits, '_', '-' or '.'."""
    return bool(_NAME.match(name))


def valid_host(host):
    """Launcher_ValidServerHost: an IPv4 address or a host name, 1-63 letters, digits, '.' or '-'."""
    return bool(_HOST.match(host))


def valid_password(password):
    """No blank, quote, ';' or '+': the command line is cut at every '+' (Com_ParseCommandLine)."""
    return bool(_TOKEN.match(password))


def parse_size(text):
    m = _SIZE.match(text.strip())
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    return (w, h) if 320 <= w <= 16384 and 200 <= h <= 16384 else None


def check_extra(text):
    """None when one free command line is usable, else why not."""
    text = text.strip()
    if not text:
        return "la ligne est vide"
    if "+" in text:
        return "pas de « + » : le jeu coupe sa ligne de commande à chaque « + »"
    if '"' in text or "\n" in text:
        return "pas de guillemet ni de retour à la ligne"
    return None


class Profile:
    def __init__(self, path=None):
        self.path = path
        self.data = copy.deepcopy(DEFAULTS)
        if path:
            self.load()

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(saved, dict):
            return
        # an unknown key or a value of the wrong type keeps the default: a file of another version still loads
        for key, default in DEFAULTS.items():
            value = saved.get(key)
            if value is not None and type(value) is type(default):
                self.data[key] = value
        if self.data["mode"] not in MODES:
            self.data["mode"] = DEFAULTS["mode"]
        if self.data["window"] not in WINDOW_MODES:
            self.data["window"] = DEFAULTS["window"]
        if self.data["split"] not in SPLIT_MODES:
            self.data["split"] = DEFAULTS["split"]
        if self.data["split_layout"] not in SPLIT_LAYOUTS:
            self.data["split_layout"] = DEFAULTS["split_layout"]
        if self.data["gfx_api"] not in GFX_APIS:
            self.data["gfx_api"] = DEFAULTS["gfx_api"]
        if self.data["scene_models"] not in SCENE_MODEL_CHOICES:
            self.data["scene_models"] = DEFAULTS["scene_models"]
        if self.data["bo2_weapons"] not in dict(BO2_WEAPON_CHOICES):
            self.data["bo2_weapons"] = 0
        if self.data["start_points"] not in START_POINT_CHOICES:
            self.data["start_points"] = DEFAULTS["start_points"]
        if self.data["run_info"] not in (0, 1, 2):
            self.data["run_info"] = DEFAULTS["run_info"]
        if self.data["far_respawn"] not in FAR_RESPAWN_CHOICES:
            self.data["far_respawn"] = DEFAULTS["far_respawn"]
        if self.data["spawn_rate"] not in SPAWN_RATE_CHOICES:
            self.data["spawn_rate"] = DEFAULTS["spawn_rate"]
        self.data["start_perks"] = [k for k, _ in START_PERKS if k in self.data["start_perks"]]
        self.data["extra"] = [e for e in self.data["extra"] if isinstance(e, dict) and isinstance(e.get("text"), str)]
        self.data["favorites"] = [f for f in self.data["favorites"] if isinstance(f, dict) and f.get("host")]

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        # server passwords inside: readable by the user only
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)


def fs_game(p, dist_root=None, server_mods=None):
    """The fs_game the client's line sets ('' for none): where its console_mp.log goes."""
    if p["mode"] != "solo":
        return server_values(p, dist_root, server_mods).get("fs_game", "")
    return line_values(solo_mod_flags(p, dist_root), ("fs_game",)).get("fs_game", "")


def window_flags(p):
    if p["window"] == "fullscreen":
        return ["+set", "r_fullscreen", "1", "+set", "r_borderless", "0"]
    if p["window"] == "window":
        size = parse_size(p["window_size"]) or (1280, 720)
        return ["+set", "r_fullscreen", "0", "+set", "r_borderless", "0", "+set", "r_customMode",
                f"{size[0]}x{size[1]}", "+set", "vid_xpos", "60", "+set", "vid_ypos", "60"]
    return ["+set", "r_fullscreen", "0", "+set", "r_borderless", "1", "+set", "vid_xpos", "0", "+set", "vid_ypos", "0"]


def split_on(p):
    """Two windows: split screen chosen, and a server to join (solo is a listen server of one player)."""
    return p["split"] != "off" and p["mode"] != "solo"


def split_flags(p, player):
    """Window and input of one split screen window (player 1 or 2): a borderless window on its part of the primary
    monitor, and its input."""
    rect = SPLIT_RECTS[p["split_layout"]][player - 1]
    return ["+set", "r_fullscreen", "0", "+set", "r_borderless", "1", "+set", "r_borderlessRect", rect,
            "+set", "vid_xpos", "0", "+set", "vid_ypos", "0",
            "+set", "bo1_splitInput", SPLIT_INPUTS[p["split"]][player - 1]]


def split_home(dist_root):
    return os.path.join(dist_root, SPLIT2_HOME)


def add_scene_models(argv, count):
    """Raises the renderer's models per frame to count: r_mod_sceneModels, and a model lighting pool of count + 1024
    (the retail pool, which DObjs and dyn models share; measured on Nuketown at 4096: none refused). A larger pool the
    line already asks for (the horde's past 300 zombies) is kept."""
    if count <= 1024:
        return
    entries = min(MODEL_LIGHTING_ENTRIES_MAX, count + 1024)
    for i in range(len(argv) - 2):
        if argv[i] == "+set" and argv[i + 1] == "r_mod_modelLightingEntries":
            argv[i + 2] = str(max(int(argv[i + 2]), entries))
            break
    else:
        argv += ["+set", "r_mod_modelLightingEntries", str(entries)]
    argv += ["+set", "r_mod_sceneModels", str(count)]


def launch_env(p):
    """The environment the client starts with: None keeps ZmClient's own; Vulkan on Linux is BO1_GFX_BACKEND."""
    if p["gfx_api"] != "vulkan":
        return None
    env = dict(os.environ)
    env["BO1_GFX_BACKEND"] = "vulkan"
    return env


def server_address(p):
    if p["mode"] == "host":
        return f"127.0.0.1:{p['host_port']}"
    return f"{p['join_host']}:{p['join_port']}"


def host_values(p, dist_root=None):
    """What a client of the local server loads: the Solo view's game, as the server runs it (gamemods.client_values)."""
    return client_values(p, dist_root)


def server_values(p, dist_root=None, server_mods=None):
    """The settings this client takes from its server ({} for solo): the local server's game, or a remote server's
    getmodinfo answer (server_mods, a protocol.ModInfo; None or refused: the join_* choices instead)."""
    if p["mode"] == "host":
        return host_values(p, dist_root)
    if p["mode"] == "join" and server_mods is not None and not server_mods.refused:
        return dict(server_mods.values)
    return {}


def answered(p, server_mods):
    """The client knows its server's settings: the local server's, or a remote one that answered getmodinfo."""
    return p["mode"] == "host" or (p["mode"] == "join" and server_mods is not None and not server_mods.refused)


def wants_bo2_weapons(p, dist_root=None):
    """The client loads mods/bo2weapons/mod.ff: solo with the BO2 weapons, or the manual choice for a server that did
    not say what it runs."""
    if p["mode"] == "solo":
        return bool(p["bo2_weapons"]) and bo2_weapons_available(resolve_map(p["map"], dist_root)[0])
    return p["mode"] == "join" and p["join_bo2_weapons"]


def wants_dual_wield(p, dist_root=None):
    """The client loads mods/dualwield/mod.ff: solo with the dual-wield weapons, or the manual choice for a server
    that did not say what it runs."""
    if p["mode"] == "solo":
        return p["dual_wield"] and bo2_weapons_available(resolve_map(p["map"], dist_root)[0])
    return p["mode"] == "join" and p["join_dual_wield"]


def problems(p, dist_root=None, server_mods=None):
    """Why the profile cannot be launched as it is (empty when it can). server_mods: a joined server's getmodinfo
    answer (protocol.ModInfo), whose files this folder must have."""
    out = []
    if p["name"] and not valid_name(p["name"]):
        out.append("nom du joueur : 1 à 15 lettres, chiffres, « _ », « - » ou « . »")
    if split_on(p) and p["name2"] and not valid_name(p["name2"]):
        out.append("nom du joueur 2 : 1 à 15 lettres, chiffres, « _ », « - » ou « . »")
    if p["mode"] == "join":
        if not valid_host(p["join_host"]):
            out.append("adresse du serveur absente ou invalide (vue Serveurs, F2)")
        if not 1 <= p["join_port"] <= 65535:
            out.append("port du serveur hors de 1-65535")
        if p["join_password"] and not valid_password(p["join_password"]):
            out.append("mot de passe du serveur : ni espace, ni guillemet, ni « ; », ni « + »")
    if p["mode"] == "host" and not 1 <= p["host_port"] <= 65535:
        out.append("port du serveur local hors de 1-65535")
    if p["mode"] in ("solo", "host"):
        bsp = resolve_map(p["map"], dist_root)[0]
        if not map_installed(bsp, dist_root):
            out.append(f"{MAP_LABELS.get(bsp, bsp)} n'est pas installée (pas de zone {bsp}.ff : votre Black Ops "
                       "n'a pas ce DLC)")
    if p["mode"] in ("solo", "host"):
        layout = resolve_map(p["map"], dist_root)[1]
        missing = bsp_world_files(layout, dist_root) if layout else []
        if missing:
            out.append(f"{MAPKIT_LABELS.get(layout, layout)} : il manque {', '.join(missing)} (votre extraction de "
                       "Black Ops II, docs/BO2_MAPS.md)")
    if wants_bo2_weapons(p, dist_root) and not bo2_weapons_installed(dist_root):
        out.append("armes de Black Ops II : pas de mods/bo2weapons/mod.ff (à construire depuis votre Black Ops II, "
                   "docs/BO2_WEAPONS.md)")
    if p["mode"] in ("join", "host"):
        missing = missing_files(server_values(p, dist_root, server_mods), dist_root)
        if p["mode"] == "host":
            missing = [m for m in missing if m.startswith("mods")]    # the map's own files: the check above
        if missing:
            out.append(f"le serveur charge {', '.join(missing)}, absent(s) de ce dossier")
    if p["mode"] in ("solo", "host") and p["unlimited_pap"] and not unlimited_pap_installed(dist_root):
        out.append("Pack-a-Punch illimité : pas de mods/unlimitedpap/maps/_zombiemode_perks.gsc (à écrire depuis vos "
                   "zones : tools/unlimitedpap/make_perks.py)")
    if wants_dual_wield(p, dist_root) and not dual_wield_installed(dist_root):
        out.append("armes doublées : pas de mods/dualwield/mod.ff (à construire depuis le mod « Relaxing Dual "
                   "Wield », mods/dualwield/README.md)")
    if p["window"] == "window" and not parse_size(p["window_size"]):
        out.append("taille de fenêtre : LARGEURxHAUTEUR, ex. 1280x720")
    for e in p["extra"]:
        if e.get("on"):
            why = check_extra(e["text"])
            if why:
                out.append(f"dvar libre « {e['text']} » : {why}")
    if dist_root and "+" in dist_root:
        out.append("le chemin du dossier du jeu contient un « + » : le jeu couperait sa ligne de commande")
    return out


def build_command(p, exe, dist_root, launch_cfg="", player=1, server_mods=None):
    """The client's argv; player 2 is the second window of a split screen (split_on). launch_cfg: the text of the
    launch.cfg next to the program, which the engine puts before the command line; it only counts towards the
    63-command limit here. server_mods: the joined server's getmodinfo answer (protocol.ModInfo), None when not asked
    or not answered. Raises ValueError when the line is unusable."""
    issues = problems(p, dist_root, server_mods)
    if issues:
        raise ValueError(issues[0])
    if player == 2 and not split_on(p):
        raise ValueError("pas d'écran partagé")
    home = split_home(dist_root) if player == 2 else dist_root
    argv = [exe, "+set", "bo1_zombies", "1", "+set", "fs_b", dist_root, "+set", "fs_h", home,
            "+set", "logfile", "2", "+set", "bo1_mod_sharedconfig", "1"]
    name = (p["name2"] or DEFAULT_NAME2) if player == 2 else p["name"]
    if name:
        argv += ["+set", "name", name]
    if p["mode"] == "solo":
        # a listen server bound to loopback, as Play.bat: no firewall question and nobody else can join
        argv += ["+set", "net_ip", "127.0.0.1"]
        if p["god"]:
            # not the `god` command, which ClientSpawn clears: this dvar puts the bit back on every playing client
            argv += ["+set", "bo1_testclient_god", "1"]
        argv += solo_mod_flags(p, dist_root)
    elif answered(p, server_mods):
        # what the server runs, as it said (or as the local server is started)
        values = server_values(p, dist_root, server_mods)
        for dvar in CLIENT_DVARS:
            if values.get(dvar):
                argv += ["+set", dvar] + values[dvar].split()
    else:
        if wants_bo2_weapons(p, dist_root):
            add_bo2_weapons(argv)
        if wants_dual_wield(p, dist_root):
            stack_mod(argv, "dualwield")
    if split_on(p):
        argv += split_flags(p, player)
        if player == 2:
            argv += ["+set", "snd_menu_master", "1" if p["split_sound2"] else "0"]
    else:
        argv += window_flags(p)
    add_scene_models(argv, p["scene_models"])
    argv += ["+set", "r_mod_gfxApi", "vulkan" if p["gfx_api"] == "vulkan" else "d3d9"]
    if p["fps_counter"]:
        argv += ["+set", "bo1_fpscounter", "1"]
    argv += ["+set", "bo1_runinfo", str(p["run_info"])]
    for key, dvar in AIM_DVARS:
        if p[key] in ("0", "1"):
            argv += ["+set", dvar, p[key]]
    if p["mode"] == "join" and p["join_password"]:
        argv += ["+set", "password", p["join_password"]]
    for e in p["extra"]:
        if e.get("on"):
            argv += ("+" + e["text"].strip()).split()
    if p["mode"] == "solo":
        bsp, _ = resolve_map(p["map"], dist_root)
        argv += ["+devmap", bsp]
    else:
        # cl_autoConnect, not +connect: the menu's own load undoes a connect from the command line, and it retries
        # while the server is not up yet (a local server takes a while to load its map) or after it went away
        argv += ["+set", "cl_allowWanConnect", "1", "+set", "cl_autoConnect", server_address(p)]
    count = sum(1 for a in argv[1:] if a.startswith("+")) + launch_cfg.count("+")
    if count > MAX_COMMAND_LINES:
        raise ValueError(f"{count} commandes « + » : le jeu n'en lit que {MAX_COMMAND_LINES} (retirer des dvars libres)")
    return argv


def quote_command(argv):
    """argv as one line to show (the engine joins its arguments the same way, quoting those with blanks)."""
    return " ".join(f'"{a}"' if (not a or any(c in a for c in ' \t"')) else a for a in argv)
