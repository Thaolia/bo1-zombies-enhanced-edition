"""The player's config.cfg (players/config.cfg of the folder: ZmClient always starts the game with
bo1_mod_sharedconfig 1, so every mod reads this one file) and players/bo1_shared.cfg (bo1_mod_fov, read after it).

The game writes config.cfg itself when it quits: never write it while the game runs, or the game's copy wins.
Lines ZmClient does not change are kept as they are, in their order.
"""
import os
import re

from zmadmin.i18n import tr

_SETA = re.compile(r'^\s*seta\s+(\S+)\s+"([^"]*)"\s*$')
_BIND = re.compile(r'^\s*bind\s+(\S+)\s+"(.*)"\s*$')
_BIND_KEY = re.compile(r"^[A-Za-z0-9_]{1,24}$")

# (dvar, label, kind, options, help). kinds: bool, int (min, max), float (min, max), choice (values), text, fov,
# picmip (writes the r_picmip_* family). Ranges are the engine's (_Dvar_Register* in src/). No r_mode: the resolution is
# the Launch view's (profile window_size), which the command line gives (profile.window_flags) and which wins over
# config.cfg; the Config view shows it as a row of its own. The labels and help are English: tr() them where shown.
SETTINGS = [
    ("sensitivity", "Mouse sensitivity", "float", (0.01, 100.0),
     "Speed of mouse aiming. Default 5."),
    ("cl_mouseAccel", "Mouse acceleration", "float", (0.0, 100.0),
     "0: none (default). Higher: a quick move turns further."),
    ("gpad_enabled", "Controller enabled", "bool", None,
     "1: the controller plays (XInput). Default 0 on PC."),
    ("input_invertPitch", "Controller: invert Y axis", "bool", None,
     "1: pushing the stick up makes you look down."),
    ("gpad_rumble", "Controller: rumble", "bool", None, "1: rumble on."),
    ("bo1_mod_fov", "Field of view (FOV)", "fov", None,
     "0: the game's own (65). 65 to 120: wider. One setting for every mode (also written to "
     "players/bo1_shared.cfg, which the game reads after config.cfg)."),
    ("r_displayRefresh", "Screen refresh rate", "text", None, 'E.g. "60 Hz", "144 Hz" (fullscreen).'),
    ("r_vsync", "Vertical sync", "bool", None,
     "1: no screen tearing, FPS capped at the screen's refresh rate. At the next launch."),
    ("com_maxfps", "Maximum FPS", "int", (0, 1000), "0: no limit. Default 85."),
    ("r_gamma", "Brightness (gamma)", "float", (0.5, 3.0), "Default 0.9; higher: brighter."),
    ("r_aaSamples", "Anti-aliasing (MSAA)", "choice", ("1", "2", "4", "8", "16"),
     "Samples per pixel; 1: off. At the next launch."),
    ("r_texFilterAnisoMax", "Anisotropic filtering", "choice", ("1", "2", "4", "8", "16"),
     "Sharpness of textures seen at an angle; 16: the best."),
    ("r_picmip", "Texture quality", "picmip", ("auto", "0", "1", "2", "3"),
     "auto: the game chooses; 0: the best; 3: the lowest (less video memory). Also writes "
     "r_picmip_manual, r_picmip_bump and r_picmip_spec."),
    ("sm_enable", "Shadows", "bool", None, "1: dynamic shadows (heavier)."),
    ("r_dof_enable", "Depth of field", "bool", None, "1: distant objects blur while aiming."),
    ("cg_blood", "Blood", "bool", None, "1: blood effects."),
    ("cg_subtitles", "Subtitles", "bool", None, "1: dialogue subtitles."),
    ("cg_drawFPS", "Game's FPS counter", "choice", ("Off", "Simple", "SimpleRanges", "Verbose"),
     "The game's original counter (the port's counter is in Launch, F4)."),
    ("bo1_quitOnDisconnect", "Quit game from pause menu", "bool", None,
     '1 (default): "Quit" in the pause menu (Esc, Start) closes the game; 0: back to BO1\'s main menu. '
     "A game over never closes the game."),
]
BY_NAME = {s[0]: s for s in SETTINGS}
PICMIP_FAMILY = ("r_picmip", "r_picmip_bump", "r_picmip_spec")


def validate(name, text):
    """(value to write, None) or (None, why not)."""
    setting = BY_NAME.get(name)
    text = text.strip()
    if '"' in text or "\n" in text:
        return None, tr("no quote")
    if not setting:
        return text, None
    kind, opts = setting[2], setting[3]
    if kind == "bool":
        if text not in ("0", "1"):
            return None, tr("0 or 1")
    elif kind in ("int", "float"):
        try:
            v = int(text) if kind == "int" else float(text)
        except ValueError:
            return None, tr("a whole number") if kind == "int" else tr("a number")
        if not opts[0] <= v <= opts[1]:
            return None, tr("between {low} and {high}").format(low=f"{opts[0]:g}", high=f"{opts[1]:g}")
    elif kind in ("choice", "picmip"):
        if text not in opts:
            return None, tr("one of: {choices}").format(choices=", ".join(opts))
    elif kind == "fov":
        try:
            v = float(text)
        except ValueError:
            return None, tr("a number")
        if v != 0 and not 65 <= v <= 120:
            return None, tr("0, or between 65 and 120")
    return text, None


class GameConfig:
    def __init__(self, dist_root):
        self.players = os.path.join(dist_root, "players")
        self.path = os.path.join(self.players, "config.cfg")
        self.shared_path = os.path.join(self.players, "bo1_shared.cfg")
        self.lines = []
        self.values = {}            # dvar -> value, as the file has it
        self.binds = {}             # key -> command
        self.exists = False
        self.newline = "\r\n"
        self.shared_fov = None

    def load(self):
        self.lines, self.values, self.binds = [], {}, {}
        try:
            with open(self.path, encoding="latin-1", newline="") as f:
                text = f.read()
            self.lines = text.splitlines()
            self.newline = "\r\n" if "\r\n" in text or "\n" not in text else "\n"
            self.exists = True
        except FileNotFoundError:
            self.exists = False
        for line in self.lines:
            m = _SETA.match(line)
            if m:
                self.values[m.group(1)] = m.group(2)
                continue
            m = _BIND.match(line)
            if m:
                self.binds[m.group(1)] = m.group(2)
        self.shared_fov = None
        try:
            with open(self.shared_path, encoding="latin-1") as f:
                m = re.search(r'bo1_mod_fov[ "]*([-0-9.]+)', f.read())
            if m:
                self.shared_fov = m.group(1)
        except OSError:
            pass

    def value(self, name):
        if name == "bo1_mod_fov" and self.shared_fov is not None:
            return self.shared_fov        # read after config.cfg: the one that counts
        if name == "r_picmip" and self.values.get("r_picmip_manual", "0") == "0":
            return "auto"
        return self.values.get(name, "")

    def changes(self, edits):
        """The dvar -> value writes an edit dict {setting: value} makes (picmip's family expanded)."""
        out = {}
        for name, value in edits.items():
            if BY_NAME.get(name, (None, None, None))[2] == "picmip":
                if value == "auto":
                    out["r_picmip_manual"] = "0"
                else:
                    out["r_picmip_manual"] = "1"
                    for d in PICMIP_FAMILY:
                        out[d] = value
            else:
                out[name] = value
        return out

    def render(self, values, binds=None, unbound=()):
        """config.cfg's text with these seta values and binds set (in place when a line exists, else after the last
        line of their kind) and the keys of `unbound` without a bind. Keeps the file's line ends."""
        binds = binds or {}
        out, seen_vars, seen_binds = [], set(), set()
        for line in self.lines:
            m = _SETA.match(line)
            if m and m.group(1) in values:
                out.append(f'seta {m.group(1)} "{values[m.group(1)]}"')
                seen_vars.add(m.group(1))
                continue
            m = _BIND.match(line)
            if m and m.group(1) in unbound:
                continue
            if m and m.group(1) in binds:
                out.append(f'bind {m.group(1)} "{binds[m.group(1)]}"')
                seen_binds.add(m.group(1))
                continue
            out.append(line)
        new_binds = [f'bind {k} "{v}"' for k, v in binds.items() if k not in seen_binds]
        new_vars = [f'seta {k} "{v}"' for k, v in sorted(values.items()) if k not in seen_vars]
        if not self.lines:
            out = ["// generated by Call of Duty, do not modify"]
        # binds go after the last bind line (unbindall clears them first), setas after the last seta
        last_bind = max((i for i, l in enumerate(out) if _BIND.match(l) or l.strip() == "unbindall"), default=None)
        if new_binds:
            at = len(out) if last_bind is None else last_bind + 1
            out[at:at] = new_binds
        last_seta = max((i for i, l in enumerate(out) if _SETA.match(l)), default=None)
        if new_vars:
            at = len(out) if last_seta is None else last_seta + 1
            out[at:at] = new_vars
        return self.newline.join(out) + self.newline

    def save(self, values, binds=None, unbound=()):
        """Writes config.cfg (and bo1_shared.cfg when bo1_mod_fov changes). Raises OSError."""
        os.makedirs(self.players, exist_ok=True)
        text = self.render(values, binds, unbound)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="latin-1", newline="") as f:
            f.write(text)
        os.replace(tmp, self.path)
        if "bo1_mod_fov" in values:
            with open(self.shared_path, "w", encoding="latin-1", newline="") as f:
                f.write("// mod: shared by every mode (fs_game), written by the engine\r\n"
                        f'seta bo1_mod_fov "{values["bo1_mod_fov"]}"\r\n')
        self.load()


def valid_bind_key(key):
    return bool(_BIND_KEY.match(key))
