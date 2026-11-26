"""What the Free dvars view knows of the dvars a player may add: a short line for its Description column and a longer
text under the list. Each text follows the dvar's registration in src/ (its description and limits); the tests check
that every name here is still a quoted string in src/. The texts are English; French comes from zmclient/fr/help.py."""

from zmadmin.i18n import tr


class _TrPairs(dict):
    """name -> (short, long), both translated when read."""

    def __getitem__(self, key):
        short, long = super().__getitem__(key)
        return tr(short), tr(long)

    def get(self, key, default=None):
        return self[key] if key in self else default

    def values(self):
        return [self[k] for k in self]

    def items(self):
        return [(k, self[k]) for k in self]


# name: (short, long). Names as the engine registers them; lookups ignore case, as the engine does.
KNOWN = _TrPairs({
    "bo1_netlog": (
        "Sends the log to the joined server",
        "1 (default): the game sends its console log to the server it joins (server port + 1), which writes it in its "
        "logs/. 0: nothing is sent."),
    "bo1_logserver": (
        "Server receiving the log (host[:port])",
        "The host[:port] address of the game port of the server to send the log to (it receives it on port + 1). "
        "Empty: the cl_autoConnect server."),
    "r_shaderWarming": (
        "Prewarms the shaders while loading (long)",
        "1: on a map's first render, the game draws each lit pass once so the driver compiles its shaders ahead "
        "(fewer stutters afterwards). The image freezes for a long time at that moment (2 minutes or more on a "
        "laptop). 0 by default; the Launch view has this option (\"Shader warming\") and gives it at every "
        "launch."),
    "bo1_frameperf": (
        "Profiler: logs frames slower than N ms",
        "\"set bo1_frameperf 200\": the game writes a BO1_FRAMEHITCH line for each frame over 200 ms and a "
        "BO1_FRAMEPERF statistics line (fps, percentiles) every 5 s, in console_mp.log. Only read on the command "
        "line."),
    "bo1_fpscounter": (
        "The port's FPS counter (top right)",
        "1: frames-per-second counter (and battery level) at the top right. The Launch view also has this option."),
    "bo1_runinfo": (
        "Settings + program hash (speedrun)",
        "1: the game's settings and the hash of the program and zones on the loading screen; 2: also during the "
        "game; 0: nothing. The Launch view also has this option."),
    "bo1_mod_fov": (
        "Field of view for every mode",
        "0: the game's; 65 to 120: wider. Kept in players/bo1_shared.cfg (the Game config view also has this "
        "setting)."),
    "bo1_quitOnDisconnect": (
        "Quit the game from the pause menu",
        "1 (default, every platform): the disconnect command (\"Quit\" in the pause menu) closes the game instead of "
        "going back to the menu. The Game config view also has this setting."),
    "bo1_autoquit": (
        "Quit by itself after N ms",
        "The game closes N milliseconds after it starts (0: never). For timed tests."),
    "bo1_dvardump": (
        "Lists every dvar on quitting (bo1_autoquit)",
        "1: when bo1_autoquit closes the game, it writes every dvar (type, flags, default and current value) to "
        "console_mp.log."),
    "bo1_audio": (
        "Logs each sound played (debug)",
        "1: every sound request (alias, entity, position, result) is written to the log. Measurement only, "
        "verbose."),
    "bo1_aimassist": (
        "Controller aim assist",
        "1: aim slowdown and lock-on with the controller (absent from the original PC game). The Launch view also "
        "has this option."),
    "bo1_mod_lazymodels": (
        "Loads the added zones' scenery on demand",
        "1 (default): the models (scenery) of a bo1_mod_zones zone are only linked when something uses them: "
        "shorter loading of imported maps."),
    "bo1_mod_ailod": (
        "Far zombies animated less often",
        "1: a zombie far from every player updates its running animation every 0.2 s instead of every frame (less "
        "CPU with many zombies)."),
    "bo1_mod_maxactors": (
        "AI slots (32 originally, 1024 at most)",
        "The number of zombies the game can have at the same time (32 in the original game, up to 1024). Read when "
        "a map starts; the horde sets it itself."),
    "bo1_mod_tabinfo": (
        "Zombies alive / left with the Tab scoreboard",
        "1: the number of zombies alive and left in the round shows next to the scoreboard (mods/zinfo sets it)."),
    "bo1_mod_pcore": (
        "Hybrid CPUs: threads on the P-cores",
        "1: server thread on the performance cores and above-normal priority; 2: the client's threads too. No "
        "effect on a non-hybrid CPU."),
    "bo1_mod_priority": (
        "Process priority (0, 1, 2)",
        "1: above-normal priority (process and main thread); 2: high priority; 0: the one it was launched with (a "
        "client's default)."),
    "r_mod_sceneModels": (
        "Models drawn per frame (1024 originally)",
        "The cap on models drawn per frame (1024 originally, up to 4096): more distant scenery on imported maps. "
        "The Launch view also has this setting."),
    "r_mod_modelLightingEntries": (
        "Model lighting: reserved entries",
        "The number of dynamic model lighting entries reserved at start-up (0: the game's, up to 5120). ZmClient "
        "already raises it with the models per frame."),
    "r_mod_skinCacheMB": (
        "Animated model cache, in MB (8 originally)",
        "The size in MB of each animated model vertex cache (8 originally, up to 256): useful with many zombies on "
        "screen."),
    "r_mod_fxElems": (
        "Effect elements at once (2048 originally)",
        "The number of effect elements (particles) alive at the same time (2048 originally, up to 4096), read when "
        "the map loads."),
    "r_mod_gfxEnts": (
        "Special models per frame (256 originally)",
        "The zombies, bodies and the weapon in hand drawn per frame (256 originally, up to 2048): raise it with a "
        "big horde."),
    "r_mod_drawStats": (
        "Logs the draw calls every N frames",
        "Every N frames, the game writes its draw calls by technique and surface type (drawstats: lines); 0: never. "
        "Measurement only."),
    "r_mod_scsShare": (
        "Shares identical shader constants",
        "1: models with identical shader constants share one of the frame's 128 slots (0 originally)."),
    "cl_allowWanConnect": (
        "Allows servers outside the local network",
        "1: connect and cl_autoConnect also accept an address outside the local network (internet). 0 by default."),
    "cl_autoConnect": (
        "Server joined from the menu (and after a drop)",
        "The host[:port] address of a server the game joins as soon as the menu is ready, and again each time it "
        "goes back to the menu. The Servers view already does it."),
    "com_maxfps": (
        "Maximum FPS (0: no limit)",
        "Frames-per-second limit (85 by default, 0: no limit, 1000 at most). The Game config view also has this "
        "setting."),
    "r_fog": (
        "Fog (0: off)",
        "0: no fog (you see farther, the atmosphere changes). Default 1."),
    "r_vsync": (
        "Vertical sync",
        "1: no screen tearing, FPS capped at the screen's refresh rate. The Game config view also has this setting."),
    "developer": (
        "Developer mode (extra messages)",
        "1 or 2: turns on the development systems (more messages and checks in the log)."),
    "logfile": (
        "Writing of console_mp.log",
        "0: no log file; 1: written in the background (default); 2: each line written at once (slower, but nothing "
        "lost if the game crashes)."),
    "cg_fov": (
        "Game field of view (65 originally)",
        "The view angle in degrees (65 by default). bo1_mod_fov sets it for every mode."),
    "r_borderlessRect": (
        "Borderless: part of the screen used",
        "With Borderless: \"x,y,w,h\" in fractions of the screen (e.g. 0,0,0.5,1: left half); empty: the whole "
        "screen. Split screen sets it itself."),
})

_BY_LOWER = {name.lower(): name for name in KNOWN}
_SET_WORDS = ("set", "seta", "sets", "setu")


def dvar_of(text):
    """The dvar a free command line sets ("set r_fog 0" -> "r_fog"), or its first word."""
    words = text.split()
    if not words:
        return ""
    if words[0].lower() in _SET_WORDS and len(words) > 1:
        return words[1]
    return words[0]


def describe(text):
    """(short, long) for a free command line's dvar, in the interface language, or ("", "") when unknown."""
    name = _BY_LOWER.get(dvar_of(text).lower())
    return KNOWN[name] if name else ("", "")
