"""The games a server or a solo client can start: the maps (base maps and MapKit layouts, Black Ops II's among them)
and the mods' command line (horde, nightmare, zinfo, noperks, hit marker, unlimited Pack-a-Punch, spawn rate, the
start kit, Black Ops II's weapons, dual wield). ZmClient's Solo view and both local servers (ZmAdmin's and ZmClient's
host mode) build their line here, so a server runs a game exactly as solo would.

The rules follow tools/mod-launcher.hta's args() rule for rule.
"""
import functools
import json
import os
import time

from .i18n import TrDict, tr
from .modflags import horde_flags, nightmare_flags

# (bsp, label, horde's napalm/shrieker spawner files exist: mods/horde maps/<map>.zombie_temple.ents)
BASE_MAPS = [
    ("zombie_theater", "Kino der Toten", True),
    ("zombie_pentagon", "Five", True),
    ("zombie_cosmodrome", "Ascension", False),
    ("zombie_coast", "Call of the Dead", False),
    ("zombie_temple", "Shangri-La", False),
    ("zombie_moon", "Moon", False),
    ("zombie_cod5_prototype", "Nacht der Untoten", False),
    ("zombie_cod5_asylum", "Verrückt", False),
    ("zombie_cod5_sumpf", "Shi No Numa", False),
    ("zombie_cod5_factory", "Der Riese", False),
    ("zombietron", "Dead Ops Arcade", False),
]
MAP_LABELS = {bsp: label for bsp, label, _ in BASE_MAPS}
# the labels tools/mod-launcher.hta gives its mapkit maps; other layouts show their file name
MAPKIT_LABELS = TrDict({
    "mapkit_test": "Mapkit test (Five + one built room)",
    "mapkit_room": "Mapkit room (fully built)",
    "relay_station": "Relay Station (three rooms, four windows)",
    "sluice_works": "Sluice Works (loop of four zones)",
    "aldric_sanatorium": "Aldric Sanatorium (two floors, power, Pack-a-Punch)",
    # docs/BO2_MAPS.md: the player's own extraction of Black Ops II's Nuketown, which make_dist.sh --bo2 packages
    "bo2_zm_nuked": "Nuketown (Black Ops II)",
    "bo2_zm_transit": "TranZit (Black Ops II)",
    # the same Nuketown on a world of its own BSP (tools/bo2/bo2_bsp.py): BO2's props, lightmaps and sky
    "bo2_zm_nuked_bsp": "Nuketown native (Black Ops II, BSP world)",
    "bo2_zm_transit_bsp": "TranZit native (Black Ops II, BSP world)",
    "bo2_zm_prison_bsp": "Mob of the Dead native (Black Ops II, BSP world)",
    "bo2_zm_buried_bsp": "Buried native (Black Ops II, BSP world)",
})
# the zones a layout's assets come from beside Five's (bo1_mod_zones): TranZit's Stamin-Up machine and bottle are
# Ascension's (_mapkit.gsc mapkit_marathon_perk)
MAPKIT_ZONES = {"bo2_zm_transit": "zombie_cosmodrome", "bo2_zm_transit_bsp": "zombie_cosmodrome",
                "bo2_zm_buried_bsp": "zombie_cosmodrome"}
# a zone of the package loaded last, usermaps/<zone>/<zone>.ff, that the layout needs: the BO1 effects its "fx" edits
# place on a BO2 map (tools/bo2/bo2_createfx.py)
MAPKIT_FX_ZONES = {"bo2_zm_nuked_bsp": "zombie_bo2fx", "bo2_zm_transit_bsp": "zombie_bo2fx",
                   "bo2_zm_prison_bsp": "zombie_bo2fx", "bo2_zm_buried_bsp": "zombie_bo2fx"}
# a layout played on a world of its own BSP (docs/BO2_MAPS.md, "Props, gameplay and lighting on the native world"):
# its zone usermaps/<zone>/<zone>.ff (bo1_mod_zones) and its world main/maps/<zone>.d3dbsp (bo1_bspworld)
MAPKIT_BSP_WORLDS = {"bo2_zm_nuked_bsp": "zombie_bo2nuked", "bo2_zm_transit_bsp": "zombie_bo2transit",
                     "bo2_zm_prison_bsp": "zombie_bo2prison", "bo2_zm_buried_bsp": "zombie_bo2buried"}
NIGHTMARE_MAPS = ("zombie_pentagon", "zombie_theater")
# mods/bo2weapons (docs/BO2_WEAPONS.md): the player's own Black Ops II weapons, in mods/bo2weapons/mod.ff, which the
# engine loads when fs_mods names the mod (DB_FindModZone). Choice 0 is off; 1 to 3 are the script's bo2weapons_box 0
# to 2. A client joining a server that has them loads the same mod.ff (join_bo2_weapons), or the weapons' indices do not
# match: the game goes back to the menu on entering, naming the missing weapon (cg_weapons.cpp).
# The labels are English: tr() them where they are shown.
BO2_WEAPON_CHOICES = ((0, "no"), (1, "in the box, with the map's own"),
                      (2, "alone in the box, + the map's special weapons"),
                      (3, "alone in the box"))
# mods/dualwield (mods/dualwield/README.md): dual-wield weapons after Pack-a-Punch, from the player's own copy of the
# "Relaxing Dual Wield" mod, in mods/dualwield/mod.ff (tools/dualwield/dualwield_mod.py). The engine loads it beside
# bo2weapons' (DB_ListModZones). A client joining a server that has them loads it too (join_dual_wield).
# mods/spawnrate (mods/spawnrate/README.md): spawnrate_mult, the zombies' spawn speed as a multiple of retail's; 0 is off.
SPAWN_RATE_CHOICES = (0, 2, 3, 5, 10)
START_PERKS = (("jugg", "Juggernog"), ("revive", "Quick Revive"), ("speed", "Speed Cola"), ("doubletap", "Double Tap"),
               ("staminup", "Stamin-Up"), ("phd", "PhD Flopper"), ("deadshot", "Deadshot Daiquiri"),
               ("mule", "Mule Kick"))

# The start kit of a solo game, given by mods/admin when the player first spawns (zm_startpoints, zm_startperks): 0
# points keeps the game's own 500. The perk names are those _admin.gsc admin_perk_name takes, in its order; a perk
# without a machine on the map is not given.
START_POINT_CHOICES = (0, 1000, 2500, 5000, 10000, 25000, 50000, 100000)
FAR_RESPAWN_CHOICES = (0, 1500, 2500, 4000)    # mods/admin's zm_farrespawn, in zm_where's units (1500: Moon's own)

# What mod_flags reads, with ZmClient's defaults (its profile holds them under the same keys; ZmAdmin keeps its local
# server's in servers.json)
MOD_DEFAULTS = {
    "map": "zombie_theater",            # a bsp, or "mapkit:<layout>"
    "zinfo": True,
    "noperks": False,
    "quickrestart": True,
    "start_points": 0,                  # one of START_POINT_CHOICES
    "start_perks": [],                  # names of START_PERKS
    "start_power": False,               # mods/admin's zm_startpower: the power switch used at the start
    "start_pap": False,                 # mods/admin's zm_startpap: a Pack-a-Punch, always on, at the start points
    "far_respawn": 0,                   # one of FAR_RESPAWN_CHOICES: mods/admin's zm_farrespawn
    "horde": False,
    "horde_max": 128,
    "horde_round": 1,
    "horde_napalm": True,
    "horde_sonic": True,
    "horde_spawn_all": False,
    "horde_unjam": True,
    "horde_clear_round": False,
    "difficulty": 0,                    # 0 Normal, 1 Nightmare, 2 Hell
    "bo2_weapons": 0,                   # one of BO2_WEAPON_CHOICES
    "dual_wield": False,                # mods/dualwield: Ray Gun, Thundergun (and PPSh) doubled by Pack-a-Punch
    "hitmarker": False,                 # mods/hitmarker: an X at the crosshair on each hit
    "unlimited_pap": False,             # mods/unlimitedpap: Pack-a-Punch again and again, price and damage doubled
    "spawn_rate": 0,                    # one of SPAWN_RATE_CHOICES: mods/spawnrate's spawnrate_mult, 0 off
    "spawn_rush": True,                 # mods/spawnrate's spawnrate_rush: zombies sprint to their barrier
}


# ------------------------------------------------------------------------------------------------------------ maps
@functools.lru_cache(maxsize=8)
def mapkit_layouts(dist_root):
    """(layout, base bsp) of mods/mapkit/layouts/*.json that name a base map. Read once per folder: the views ask at
    every frame."""
    folder = os.path.join(dist_root, "mods", "mapkit", "layouts") if dist_root else None
    out = []
    try:
        names = sorted(os.listdir(folder)) if folder else []
    except OSError:
        names = []
    for n in names:
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, n), encoding="utf-8") as f:
                base = json.load(f).get("base")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(base, str) and base in MAP_LABELS:
            out.append((n[:-len(".json")], base))
    known = [l for l in out if l[0] in MAPKIT_LABELS]
    return tuple(sorted(known, key=lambda l: list(MAPKIT_LABELS).index(l[0]))
                 + [l for l in out if l[0] not in MAPKIT_LABELS])


def bsp_world_files(layout, dist_root):
    """The files a BSP-world layout needs that the package lacks (empty for any other layout)."""
    zone = MAPKIT_BSP_WORLDS.get(layout)
    if not zone:
        return []
    need = [os.path.join("usermaps", zone, zone + ".ff"), os.path.join("main", "maps", zone + ".d3dbsp")]
    fx = MAPKIT_FX_ZONES.get(layout)
    if fx:
        need.append(os.path.join("usermaps", fx, fx + ".ff"))
    return [f for f in need if not (dist_root and os.path.isfile(os.path.join(dist_root, f)))]


def solo_maps(dist_root):
    """(value, label, bsp, layout or None) of every map the Solo view offers."""
    maps = [(bsp, label, bsp, None) for bsp, label, _ in BASE_MAPS]
    for layout, base in mapkit_layouts(dist_root):
        if bsp_world_files(layout, dist_root):
            continue
        label = MAPKIT_LABELS.get(layout, layout)
        maps.append((f"mapkit:{layout}", tr("Mapkit: {label}").format(label=label), base, layout))
    return maps


def resolve_map(value, dist_root=None):
    """(bsp, layout or None) of a profile's map value."""
    if value.startswith("mapkit:"):
        layout = value[len("mapkit:"):]
        for name, base in mapkit_layouts(dist_root):
            if name == layout:
                return base, layout
        return "zombie_pentagon", layout     # the .hta's base for every kit map
    return value, None


_installed = {}


def installed_maps(dist_root):
    """The base maps whose zone is in zone/<any folder>/<map>.ff, or None when the folder has no zone/ at all (an
    install without the DLCs converts only Kino, Five and Dead Ops). Cached 5 s: the views ask at every frame."""
    now = time.monotonic()
    hit = _installed.get(dist_root)
    if hit and now - hit[0] < 5:
        return hit[1]
    zone = os.path.join(dist_root, "zone") if dist_root else ""
    try:
        folders = [os.path.join(zone, d) for d in os.listdir(zone)]
    except OSError:
        result = None
    else:
        names = set()
        for folder in folders:
            try:
                names |= {n[:-3].lower() for n in os.listdir(folder) if n.lower().endswith(".ff")}
            except OSError:
                pass
        result = frozenset(b for b, _, _ in BASE_MAPS if b in names)
    _installed[dist_root] = (now, result)
    return result


def map_installed(bsp, dist_root):
    maps = installed_maps(dist_root)
    return maps is None or bsp in maps


def map_label(value, dist_root=None):
    for v, label, _, _ in solo_maps(dist_root):
        if v == value:
            return label
    return MAP_LABELS.get(value, value)


def specials_available(bsp, layout):
    return not layout and any(b == bsp and s for b, _, s in BASE_MAPS)


def nightmare_available(bsp, layout):
    return not layout and bsp in NIGHTMARE_MAPS


def bo2_weapons_installed(dist_root):
    """mods/bo2weapons/mod.ff is there: the player built it from their own Black Ops II (docs/BO2_WEAPONS.md)."""
    return bool(dist_root) and os.path.isfile(os.path.join(dist_root, "mods", "bo2weapons", "mod.ff"))


def bo2_weapons_available(bsp):
    """Dead Ops Arcade has no box."""
    return bsp != "zombietron"


def dual_wield_installed(dist_root):
    """mods/dualwield/mod.ff is there: the player built it from their own copy of the mod (mods/dualwield/README.md)."""
    return bool(dist_root) and os.path.isfile(os.path.join(dist_root, "mods", "dualwield", "mod.ff"))


def unlimited_pap_installed(dist_root):
    """mods/unlimitedpap's Pack-a-Punch script is there: written from the player's own zones
    (tools/unlimitedpap/make_perks.py, which the packages run)."""
    return bool(dist_root) and os.path.isfile(
        os.path.join(dist_root, "mods", "unlimitedpap", "maps", "_zombiemode_perks.gsc"))


def stack_mod(argv, name):
    """Stacks mods/<name> on the line's fs_mods, or adds one, naming fs_game's mod first as the engine stacks it
    (fs_mods must name the mod: an empty fs_mods runs no mod's hooks)."""
    for i in range(1, len(argv)):
        if argv[i] == "fs_mods" and argv[i - 1] == "+set":
            j = i + 1
            while j < len(argv) and not argv[j].startswith("+"):
                j += 1
            if name not in argv[i + 1:j]:
                argv.insert(j, name)
            return
    game = next((argv[i + 2] for i in range(len(argv) - 2) if argv[i] == "+set" and argv[i + 1] == "fs_game"), "")
    argv += ["+set", "fs_mods"] + ([game[len("mods/"):]] if game.startswith("mods/") else []) + [name]


def add_bo2_weapons(argv, choice=None):
    """Stacks mods/bo2weapons (stack_mod). choice: the solo box choice (1 to 3), which sets bo2weapons_box; None for a
    client of a server, whose server decides."""
    stack_mod(argv, "bo2weapons")
    if choice:
        argv += ["+set", "bo2weapons_box", str(choice - 1)]


# ---------------------------------------------------------------------------------------------------- command line
def mod_flags(p, dist_root=None):
    """The mod part of mod-launcher.hta's args(), from the map's flags to the quick restart. p: a dict with
    MOD_DEFAULTS' keys (a ZmClient profile has them all)."""
    bsp, layout = resolve_map(p["map"], dist_root)
    a = ""
    horde_opts = dict(n=p["horde_max"], round_=p["horde_round"], zinfo=p["zinfo"], spawn_all=p["horde_spawn_all"],
                      unjam=p["horde_unjam"], noperks=p["noperks"], carryover=not p["horde_clear_round"])
    if layout:
        if p["horde"]:
            a += " " + horde_flags(**horde_opts).replace("+set fs_mods ", "+set fs_mods mapkit ", 1)
            a += " +set bo1_mod_mapkit " + layout
        else:
            a += " +set fs_game mods/mapkit +set bo1_mod_mapkit " + layout
            if p["zinfo"] or p["noperks"]:
                a += (" +set fs_mods mapkit" + (" zinfo" if p["zinfo"] else "")
                      + (" noperks +set noperks 1" if p["noperks"] else ""))
        # the world's zone first, as the self-tests load them (docs/BO2_MAPS.md)
        zones = [z for z in (MAPKIT_BSP_WORLDS.get(layout), MAPKIT_ZONES.get(layout), MAPKIT_FX_ZONES.get(layout)) if z]
        if zones:
            a += " +set bo1_mod_zones " + " ".join(zones)
        if layout in MAPKIT_BSP_WORLDS:
            a += f" +set bo1_bspworld maps/{MAPKIT_BSP_WORLDS[layout]}.d3dbsp"
    elif p["horde"]:
        specials = specials_available(bsp, layout)
        a += " " + horde_flags(**horde_opts, napalm=p["horde_napalm"] and specials, sonic=p["horde_sonic"] and specials)
    elif p["zinfo"] or p["noperks"]:
        a += " +set fs_mods" + (" zinfo" if p["zinfo"] else "") + (" noperks +set noperks 1" if p["noperks"] else "")
    if nightmare_available(bsp, layout):
        a = nightmare_flags(p["difficulty"], a, bsp)
    argv = a.split()
    # after the others, as mod-launcher.hta's args(): spawnrate last, it wraps horde's spawner
    if p["hitmarker"]:
        stack_mod(argv, "hitmarker")
    if p["unlimited_pap"] and unlimited_pap_installed(dist_root):
        stack_mod(argv, "unlimitedpap")
    if p["spawn_rate"]:
        stack_mod(argv, "spawnrate")
        argv += ["+set", "spawnrate_mult", str(p["spawn_rate"])]
        if not p["spawn_rush"]:
            argv += ["+set", "spawnrate_rush", "0"]
    if p["quickrestart"]:
        argv += ["+set", "bo1_mod_quickrestart", "1"]
    if p["start_points"] or p["start_perks"] or p["start_power"] or p["start_pap"] or p["far_respawn"]:
        add_admin_mod(argv, bool(layout) and not p["horde"])
        if p["far_respawn"]:
            argv += ["+set", "zm_farrespawn", str(p["far_respawn"])]
        if p["start_power"]:
            argv += ["+set", "zm_startpower", "1"]
        if p["start_pap"]:
            argv += ["+set", "zm_startpap", "1"]
        if p["start_points"]:
            argv += ["+set", "zm_startpoints", str(p["start_points"])]
        if p["start_perks"]:
            argv += ["+set", "zm_startperks", ",".join(k for k, _ in START_PERKS if k in p["start_perks"])]
    if p["bo2_weapons"] and bo2_weapons_available(bsp):
        add_bo2_weapons(argv, p["bo2_weapons"])
    if p["dual_wield"] and bo2_weapons_available(bsp):
        stack_mod(argv, "dualwield")
    return argv


def add_admin_mod(argv, mapkit):
    """Stacks mods/admin (the start kit's script) on the line's fs_mods, or adds one: "mapkit admin" on a MapKit map
    without other mods, whose line only sets fs_game."""
    for i in range(1, len(argv)):
        if argv[i] == "fs_mods" and argv[i - 1] == "+set":
            j = i + 1
            while j < len(argv) and not argv[j].startswith("+"):
                j += 1
            if "admin" not in argv[i + 1:j]:
                argv.insert(j, "admin")
            return
    argv += ["+set", "fs_mods"] + (["mapkit", "admin"] if mapkit else ["admin"])


# ------------------------------------------------------------------------------------------- what a client loads
# The settings a server's clients must share (SV_ModInfoRequest's list, protocol.ModInfo.DVARS): the mods' zones and
# mod.ff, the extra zones, the MapKit layout and its BSP world. The rest of a game's line (horde's sizes, start kit,
# difficulty...) is the server's alone.
CLIENT_DVARS = ("fs_game", "fs_mods", "bo1_mod_zones", "bo1_bspworld", "bo1_mod_mapkit")
MOD_FF_MODS = ("bo2weapons", "dualwield")


def line_values(argv, names=CLIENT_DVARS):
    """{dvar: value} of the "+set dvar value..." of a command line, for the dvars in names (a value runs to the next
    "+" word, its words joined by spaces)."""
    out = {}
    for i in range(len(argv) - 1):
        if argv[i] == "+set" and argv[i + 1] in names:
            j = i + 2
            while j < len(argv) and not argv[j].startswith("+"):
                j += 1
            out[argv[i + 1]] = " ".join(argv[i + 2:j])
    return out


def client_values(game, dist_root=None):
    """What a client of a server running game (MOD_DEFAULTS' keys) must load: line_values of its mod_flags."""
    return line_values(mod_flags(game, dist_root))


def missing_files(values, dist_root):
    """What this folder lacks to load a server's settings (values: client_values or a getmodinfo answer): the mod.ff
    of a mod built from the player's own files (MOD_FF_MODS: without it the client goes back to the menu on entering),
    a zone of bo1_mod_zones, the BSP world. Paths relative to the folder. The other mods come with every package."""
    out = []
    if not dist_root:
        return out
    for mod in values.get("fs_mods", "").split():
        need = os.path.join("mods", mod, "mod.ff")
        if mod in MOD_FF_MODS and not os.path.isfile(os.path.join(dist_root, need)):
            out.append(need)
    for zone in values.get("bo1_mod_zones", "").split():
        if zone in MAP_LABELS:
            continue    # a retail map's zone: map_installed's business
        need = os.path.join("usermaps", zone, zone + ".ff")
        if not os.path.isfile(os.path.join(dist_root, need)):
            out.append(need)
    world = values.get("bo1_bspworld", "")
    if world and not os.path.isfile(os.path.join(dist_root, "main", world)):
        out.append(os.path.join("main", world))
    return out
