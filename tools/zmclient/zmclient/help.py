"""The texts the views show to explain a key or a setting (English, French through zmclient/fr/help.py)."""

from zmadmin.i18n import TrDict, tr


class _TrLines(dict):
    """A table of help pages (lists of lines) whose lines translate when read."""

    def __getitem__(self, key):
        return [tr(line) for line in super().__getitem__(key)]

    def get(self, key, default=None):
        return self[key] if key in self else default

    def values(self):
        return [self[k] for k in self]

    def items(self):
        return [(k, self[k]) for k in self]


MODE_LABELS = TrDict({
    "solo": "Solo (offline)",
    "join": "Join a server",
    "host": "Local server + join it",
})
MODE_HELP = TrDict({
    "solo": "A game alone on this PC, set up in the Solo view (F3): map, mods, horde, difficulty.",
    "join": "Join a dedicated server (LAN or internet), chosen in the Servers view (F2). The server decides the map, "
            "the mods and god mode; ZmClient asks it what to load.",
    "host": "Starts this folder's dedicated server (like ZmAdmin, which can then administer it) with the game of the "
            "Solo view (F3), then the game, which joins it as soon as it has loaded its map. Other players on the "
            "network can come.",
})
WINDOW_LABELS = TrDict({"borderless": "Borderless (windowed fullscreen)", "window": "Window",
                        "fullscreen": "Fullscreen"})
TRISTATE_LABELS = TrDict({"": "game setting", "1": "yes", "0": "no"})
SPLIT_LABELS = TrDict({"off": "no", "kbm_pad": "keyboard/mouse + controller", "pad_pad": "two controllers"})
SPLIT_HELP = TrDict({
    "off": "a single player on this PC",
    "kbm_pad": "player 1 on keyboard and mouse, player 2 on the first controller",
    "pad_pad": "player 1 on the first controller, player 2 on the second",
})
SPLIT_LAYOUT_LABELS = TrDict({"side": "side by side", "stack": "one above the other"})
SPLIT_LAYOUT_HELP = TrDict({
    "side": "player 1 on the left, player 2 on the right: each gets half of the screen, full height",
    "stack": "player 1 at the top, player 2 at the bottom: each gets half of the screen, full width",
})
DIFFICULTY_LABELS = TrDict({0: "Normal", 1: "Nightmare", 2: "Hell"})

SPAWN_RATE_HELP = TrDict({
    0: "the original game's pace",
    2: "twice as fast, short breaks between rounds",
    3: "three times as fast (the mod's setting)",
    5: "five times as fast",
    10: "ten times as fast: the round comes out almost at once",
})

ROW_HELP = TrDict({
    "mode": "How to play. Enter: choose.",
    "map": "The solo game's map. The \"Mapkit\" maps are built by the mapkit mod on a base map.",
    "server": "The server to join: address, port and players' password (g_password, empty if it has none). The "
              "Servers view (F2) lists the favourites and those of the local network.",
    "name": "Your name on servers (1 to 15 letters, digits, \"_\", \"-\", \".\"). Empty: the one in config.cfg.",
    "god": "Invincible (bo1_testclient_god: the game sets god mode again every frame). Solo only: a server decides "
           "for its players.",
    "zinfo": "While holding Tab, the zombies alive and those left in the round show on the left (zinfo mod).",
    "noperks": "No perk machines (noperks mod). The Pack-a-Punch and the box stay.",
    "quickrestart": "After the game ends, R restarts the same map with the same settings.",
    "hitmarker": "An X at the centre of the screen for each zombie hit (hitmarker mod): white on the body, orange on "
                 "the head, red for the killing blow. \"hitmarker 0\" in the console hides it.",
    "unlimited_pap": "The Pack-a-Punch takes an already upgraded weapon again, as many times as you like: each pass "
                     "doubles the price (5,000, 10,000, 20,000...) and the damage (unlimitedpap mod). Reserve ammo "
                     "does not double. Its script is written from your own zones "
                     "(tools/unlimitedpap/make_perks.py, which the packages run).",
    "spawn_rate": "Each round's zombies appear faster, and the break between two rounds goes from 12 s to 3 s "
                  "(spawnrate mod). The zombies' number, health and speed stay the game's. \"spawnrate_mult\" in "
                  "the console changes the speed in game.",
    "spawn_rush": "With faster spawning: each zombie runs to its barricade, then takes its round's speed again "
                  "(spawnrate_rush).",
    "start_points": "Each player's points on arriving on the map, instead of the game's 500 (admin mod, "
                    "zm_startpoints). Solo only: a server decides for its players.",
    "start_power": "The power is turned on when the first player arrives (admin mod, zm_startpower): the machines, "
                   "the Pack-a-Punch and the electric doors work right away. No effect on a map without power.",
    "start_pap": "A Pack-a-Punch always on, placed at the centre of the players' spawn points (admin mod, "
                 "zm_startpap). It also runs the map's own one without power, and gives one to maps that have none "
                 "(Nacht der Untoten).",
    "far_respawn": "A zombie farther than this distance from every player (zm_where units) and seen by none is "
                   "replaced by another one, which appears near the players (admin mod, zm_farrespawn; the game "
                   "does it on Moon at 1500). Not dogs or bosses, nor a wounded zombie.",
    "start_perk": "A perk given for free on arriving on the map (admin mod, zm_startperks). Only if its machine is "
                  "on this map: Kino and Five only have Juggernog, Quick Revive, Speed Cola and Double Tap.",
    "horde": "Horde mod: many zombies at once; the next round starts when the round's last zombie has appeared.",
    "horde_max": "Zombies at the same time (24 to 1024). Above 300 it is heavy: the game turns on its performance "
                 "options (like the .hta launcher).",
    "horde_round": "The starting round (1: normal).",
    "horde_napalm": "Napalm zombies (from Shangri-La). Kino and Five only (horde mod spawn files).",
    "horde_sonic": "Screaming zombies (shriekers, from Shangri-La). Kino and Five only.",
    "horde_spawn_all": "Zombies come out of every window of the open zones, not only near you.",
    "horde_unjam": "A zombie stuck in the crowd walks through the others for 1.5 s.",
    "horde_clear_round": "The next round only comes when every zombie is dead (otherwise: as soon as the last one "
                         "has appeared, the living ones stay).",
    "difficulty": "Nightmare: George, an astronaut, napalm and screaming zombies, dogs... from round 1. Hell: "
                  "several of each at once. Kino and Five only; loads three more maps (slower start).",
    "bo2_weapons": "The Black Ops II weapons (HAMR, AN-94, DSR-50, Ray Gun Mark II...) and their Pack-a-Punch "
                   "version, in the box (bo2weapons mod). Their mod.ff is built from your own Black Ops II "
                   "(docs/BO2_WEAPONS.md) and goes in mods/bo2weapons/. The wall weapons stay the map's. A player "
                   "who joins a server with these weapons needs the same mod.ff (Play view, Join mode: \"Black Ops "
                   "II weapons\").",
    "dual_wield": "The Pack-a-Punch doubles the Ray Gun (two Ray Guns) and the Thundergun (\"Zeus and Hera\") "
                  "(dualwield mod, settings dualwield_pap and dualwield_ppsh). Their mod.ff is built from your "
                  "game's zones, or from your copy of the \"Relaxing Dual Wield\" mod: it then also doubles the PPSh "
                  "(\"The Grim Reapers\") and puts the PPSh-41 in the box (mods/dualwield/README.md). Stacks with "
                  "the Black Ops II weapons.",
    "join_dual_wield": "Tick to join a server that has the dual-wield weapons (dualwield mod): the game then loads "
                       "the same mods/dualwield/mod.ff. Without it, joining that server fails, naming the missing "
                       "weapon.",
    "join_detect_mods": "At launch, ZmClient asks the server what it loads (its mods, its zones, the imported map "
                        "and its BSP world), with the players' password if it has one, and the game loads the same. "
                        "An older server does not answer, and a protected server only answers the right password: "
                        "the two boxes below are then used.",
    "join_bo2_weapons": "Tick to join a server that has the Black Ops II weapons (bo2weapons mod): the game then "
                        "loads the same mods/bo2weapons/mod.ff. Without it, joining that server fails and the game "
                        "goes back to the menu with a message (missing weapon).",
    "window": "Borderless: a window the size of the screen (like Play.bat). Window: the size below. Fullscreen: at "
              "the resolution below.",
    "window_size": "The resolution in Window (the window's size) and in Fullscreen (the screen mode; a size the "
                   "screen does not offer falls back to the game's), WIDTHxHEIGHT. Also in Game config (F5). No "
                   "effect in Borderless.",
    "run_info": "The settings that change a game and a SHA-512 hash of the program and the loaded zones "
                "(bo1_runinfo), at the bottom of the loading screen, or also in a corner during the game, for a "
                "stream or a speedrun. The full hash is also written to console_mp.log (runinfo: line).",
    "gfx_api": "The renderer: Direct3D 9 (Windows) or OpenGL (Linux, OpenBSD) by default, or Vulkan (r_mod_gfxApi "
               "on Windows, BO1_GFX_BACKEND on Linux and OpenBSD). At the next launch.",
    "fsr": "With Vulkan only (r_mod_upscale): the game renders smaller than the window, then enlarges it while "
           "keeping edges sharp (FSR 1.0 or Arm ASR, see the next line). The HUD stays at the window's size. More "
           "FPS on a limited GPU (Intel). At the next launch.",
    "upscaler": "How the image is enlarged (r_mod_upscaler): AMD's FSR 1.0, frame by frame, or Arm ASR, which "
                "accumulates successive frames to recover fine detail (sharper, a little more costly, slight trails "
                "possible on what moves). If the GPU lacks what ASR needs, the game takes FSR 1.0 (\"upscale\" line "
                "of the log). At the next launch.",
    "fsr_sharpness": "Edge sharpening after enlarging (r_mod_upscaleSharpness): \"strong\" is AMD's setting; "
                     "\"soft\" or \"low\" if the image looks grainy.",
    "fps_counter": "The port's small frames-per-second counter, at the top left.",
    "shader_warming": "On a map's first render, the game draws each material once so the driver compiles its "
                      "shaders ahead (r_shaderWarming): fewer stutters afterwards, but the image freezes for a long "
                      "time while loading (\"shader warming\" in red, 2 minutes or more on a laptop). Off by "
                      "default; ZmClient gives it at every launch, it overrides config.cfg.",
    "scene_models": "The models the game draws per frame (r_mod_sceneModels; 1024 in the original game). A map "
                    "imported by Mapkit has many more (Nuketown: 2,096 props): at 1024 the farthest are missing (the "
                    "tower clock seen from the street). 4096 draws them all and enlarges the models' lighting "
                    "reserve as much. Useful mostly for imported maps.",
    "aim_assist": "Controller aim assist (bo1_aimassist). The next three settings only act when it is on. \"game "
                  "setting\": nothing is forced.",
    "aim_slowdown": "Aim slows down on a zombie.",
    "aim_lockon": "Aim follows a moving zombie.",
    "aim_autoaim": "Aim snaps to a zombie when aiming down sights (ADS).",
    "host_game": "The local server plays the game set up in the Solo view (F3): its map (imported Black Ops II maps "
                 "included), the horde, the difficulty, zinfo, noperks, the hit marker, unlimited Pack-a-Punch, the "
                 "spawn rate, the starting kit, the Black Ops II weapons and the dual-wield weapons. The game then "
                 "loads what it needs to join it. Enter: Solo view.",
    "host_port": "The local server's UDP port (3074 by default; port + 1 receives the clients' logs). Open them in "
                 "the firewall for players on other machines.",
    "host_password": "The local server's rcon password, shared with ZmAdmin (its servers.json file): ZmAdmin "
                     "administers the server ZmClient started.",
    "split": "Two players on this PC: two game windows share the main screen and join the same server (Local server "
             "mode, or Join). Not in Solo: choose \"Local server + join it\". The controller's window reads its "
             "controller even when the other one has focus, ignores keyboard and mouse, and never takes focus: the "
             "keyboard stays with the other window (after an Alt+Tab, a click on it gives it back).",
    "split_layout": "How the two windows share the main screen.",
    "split_sound2": "Sound of player 2's window. Both windows play the same game: with both, every sound is heard "
                    "twice (no by default).",
    "name2": "Player 2's name (1 to 15 letters, digits, \"_\", \"-\", \".\"). Empty: Player2. Its config, profile "
             "and log are in the game's split2/ folder.",
})

BO2_WEAPON_HELP = TrDict({
    0: "the map's weapons only",
    1: "the Black Ops II weapons are added to the map's (bo2weapons_box 0)",
    2: "the box only gives Black Ops II weapons, plus the map's special weapons: Ray Gun, Thundergun, Wunderwaffe, "
       "monkey, Gersh... (bo2weapons_box 1)",
    3: "the box only gives Black Ops II weapons (bo2weapons_box 2)",
})

VIEW_HELP = _TrLines({
    "play": [
        "Play: choose how to play, then launch.",
        "Up/Down     choose a line; Enter, Space or double-click: change it",
        "L           launch the game (and the local server in Local server mode; both windows in split screen)",
        "S           stop the game ZmClient launched (both windows in split screen)",
        "K           stop the local server",
        "The exact command line is shown at the bottom. The settings are kept in profile.json (ZmClient's config "
        "folder).",
    ],
    "servers": [
        "Servers: your favourites and the local network's servers, queried every 3 seconds (getstatus).",
        "Enter       join the chosen server (double-click too)",
        "a           add a favourite          e  edit          x  remove",
        "f           add the chosen network server to the favourites",
        "r           query now",
        "A network server is found by broadcast on ports 3074 to 3083; a server on the internet must be added by "
        "hand (its address and port). A favourite's password is the players' one (g_password), not rcon.",
    ],
    "solo": [
        "Solo: the offline game. Greyed options do not apply to the chosen map (the reason is shown at the bottom).",
        "Up/Down     choose; Enter, Space or double-click: change",
        "The mod flags are those of tools/mod-launcher.hta (horde_flags.js, nightmare_flags.js), identical.",
    ],
    "launch": [
        "Launch: what ZmClient adds to the command line in every mode.",
        "Up/Down     choose; Enter, Space or double-click: change",
        "The command line wins over config.cfg for these settings.",
    ],
    "config": [
        "Game config: the folder's players/config.cfg, the file the game writes when it quits. ZmClient launches "
        "the game with bo1_mod_sharedconfig 1: one file for every mod.",
        "Up/Down     choose; Enter or double-click: change (marked *)",
        "Ctrl+S      save (nothing is written before);  u  undo the changes",
        "n           change another dvar of the file (its name, then its value)",
        "b           keys: change or remove a bound command (bind)",
        "r           reread the file",
        "The game rewrites config.cfg when it quits: ZmClient refuses to save while it runs.",
        "The Resolution line is the Launch view's (F4), not a config.cfg line: the game gets it on the command line "
        "(r_mode in Fullscreen, r_customMode in Window); in Borderless it takes the screen's size. Changed here, it "
        "is saved at once.",
    ],
    "extra": [
        "Free dvars: commands added to the command line, before the map or the connection.",
        "a           add a line: a known dvar from the list (with its explanation), or a free command",
        "e           edit          x  remove          Space  enable / disable",
        "The Description column explains the dvars ZmClient knows (mostly the port's); the chosen line's full text "
        "shows under the buttons.",
        "Each line becomes a \"+line\" command. No \"+\" in a line: the game cuts its command line at each \"+\", "
        "and only reads 63 of them.",
    ],
    "setup": [
        "Setup: the game files, from your Call of Duty: Black Ops installation (Steam).",
        "Copies localization.txt, main/*.iwd and main/video/, then converts the zombies zones with the package's "
        "ffconv (about 6 minutes; it also writes shaders.pack), then compiles shaders.pack into shaders.spv for "
        "Vulkan with glslang (5 to 15 minutes depending on the CPU; glslang is in the Windows and Linux packages, "
        "otherwise the system's: glslang-tools on Linux, glslang on OpenBSD). Your installation is never modified.",
        "c           choose the installation: found in the Steam libraries, by browsing folders (arrows, Enter to "
        "open, Backspace to go up, Space to choose; an installation is marked \"Black Ops\"), or by typing the path",
        "v           with or without the videos      z  with or without converting the zones",
        "s           with or without the Vulkan shaders (redone only if missing or older than shaders.pack)",
        "i           install          Esc  cancel an installation in progress",
        "A file already copied (same size, same date) is not copied again. If ffconv fails, the previous zones "
        "stay. Without glslang, everything else installs and the game keeps its usual renderer. Log: "
        "main/zmclient_setup.log.",
    ],
    "log": [
        "Log: the launched game's console_mp.log, live.",
        "/           filter       Space  pause       PgUp/PgDn, wheel: scroll       End  last lines",
    ],
})

_GLOBAL_HELP = [
    "F1 Play  F2 Servers  F3 Solo  F4 Launch  F5 Game config  F6 Free dvars  F7 Setup  F8 Log",
    "Tab / Shift+Tab  next / previous view",
    "?  or F9    this help                 q  or F10   quit",
    "Mouse       click: choose a tab, a line or a button; double-click: change or run the line; wheel: scroll. To "
    "select text in the terminal, hold Shift (or run zmclient --no-mouse).",
]


def global_help():
    """The help lines shared by every view, in the interface language."""
    return [tr(line) for line in _GLOBAL_HELP]


RUN_INFO_LABELS = TrDict({0: "no", 1: "while loading", 2: "loading + in game"})
GFX_API_LABELS = TrDict({"default": "Direct3D 9 (Windows) / OpenGL (Linux, OpenBSD)", "vulkan": "Vulkan"})
FSR_LABELS = TrDict({"off": "no", "ultra": "Ultra quality (x1.3)", "quality": "Quality (x1.5)",
                     "balanced": "Balanced (x1.7)", "performance": "Performance (x2)",
                     "native": "Native (ASR anti-aliasing)", "ssaa_1.5x": "Supersampling x1.5 (SSAA)",
                     "ssaa_2x": "Supersampling x2 (SSAA)"})
FSR_HELP = TrDict({
    "off": "The game renders at the window's size.",
    "ultra": "Rendered at 77% of the window, then enlarged by FSR 1.0: almost no loss.",
    "quality": "Rendered at two thirds of the window (1280x720 for 1920x1080).",
    "balanced": "Rendered at 59% of the window.",
    "performance": "Rendered at half the window: the fastest, the blurriest.",
    "native": "Rendered at the window's size, Arm ASR serves as anti-aliasing (smooth edges, no FPS gain). Choose an "
              "Arm ASR method on the next line: with FSR 1.0, nothing changes.",
    "ssaa_1.5x": "Rendered at 1.5 times the window on each side (2880x1620 for 1920x1080), then reduced: smooth edges "
                 "and stable fine detail, but 2.25 times more pixels to draw.",
    "ssaa_2x": "Rendered at twice the window on each side (3840x2160 for 1920x1080), then reduced: the best image, "
               "4 times more pixels to draw. For powerful graphics cards.",
})
FSR_SHARPNESS_LABELS = TrDict({0.0: "maximum", 0.2: "strong (AMD default)", 0.5: "medium", 1.0: "soft", 2.0: "low"})
UPSCALER_LABELS = TrDict({"fsr1": "FSR 1.0", "asr_quality": "Arm ASR quality", "asr_balanced": "Arm ASR balanced",
                          "asr_performance": "Arm ASR performance"})
UPSCALER_HELP = TrDict({
    "fsr1": "AMD's FSR 1.0: each frame is enlarged on its own. The lightest.",
    "asr_quality": "Arm ASR (temporal) with its finest shaders: the best image.",
    "asr_balanced": "Arm ASR with lighter shaders: almost the same image, a little faster.",
    "asr_performance": "Arm ASR with its fastest shaders: a little less fine.",
})
GFX_API_HELP = TrDict({
    "default": "The usual renderer: Windows' Direct3D 9, OpenGL on Linux and OpenBSD.",
    "vulkan": "Rendering through Vulkan (64-bit Windows, Linux, OpenBSD). It needs shaders.spv next to the program; "
              "without it, or without a Vulkan driver, the game falls back to the usual renderer (Windows) and says "
              "so in console_mp.log.",
})
