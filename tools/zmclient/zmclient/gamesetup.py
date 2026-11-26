"""Puts the player's own game files in a package folder, as setup.ps1 does for the development tree.

From the player's Call of Duty: Black Ops install (Steam), it copies localization.txt, main/*.iwd and main/video/,
converts the zombies zones with the package's ffconv (the converter built with this game: its zones match the
program; it also writes shaders.pack, the GLSL the GL and Vulkan renderers read), and compiles shaders.pack to
shaders.spv for Vulkan with glslang (spirvpack.py: the Windows package's glslang.exe, the system's glslang on Linux).
A package made by `tools/make_dist.sh --no-game-data` then holds no file of the game.

The install is only read, never changed. The new zones go to a temporary folder and replace zone/ only once ffconv
succeeded, as make_dist.sh's convert_zones does, so a failed run leaves the old ones in place.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time

from zmadmin.i18n import tr
from zmadmin.launcher import IS_OPENBSD, IS_WINDOWS

from . import spirvpack

GAME_FOLDER = "Call of Duty Black Ops"
MARKER = "zmclient_setup.json"
ZONES_BYTES = 1 << 30           # the converted zones take ~770 MB: room for them and the temporary copy's growth
FFCONV_NAME = "ffconv.exe"
_PROGRESS = re.compile(r"^\[(\d+)/(\d+)\]")


# ------------------------------------------------------------------------------------------------- finding the game
def steam_roots():
    roots = []
    if IS_WINDOWS:
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for name in ("SteamPath", "InstallPath"):
                            try:
                                roots.append(os.path.normpath(winreg.QueryValueEx(k, name)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
        roots.append(r"C:\Program Files (x86)\Steam")
    else:
        home = os.path.expanduser("~")
        roots += [os.path.join(home, ".steam", "steam"), os.path.join(home, ".local", "share", "Steam"),
                  os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam")]
    return list(dict.fromkeys(roots))


def library_folders(steam_root):
    """The library paths steamapps/libraryfolders.vdf lists, the Steam folder itself first."""
    out = [steam_root]
    try:
        with open(os.path.join(steam_root, "steamapps", "libraryfolders.vdf"), encoding="utf-8",
                  errors="replace") as f:
            text = f.read()
    except OSError:
        return out
    for m in re.finditer(r'"path"\s+"([^"]+)"', text):
        out.append(os.path.normpath(m.group(1).replace("\\\\", "\\")))
    return list(dict.fromkeys(out))


def is_install(path):
    """zone/ with its common folder, localization.txt and main/*.iwd. Steam names the folder "Common": compared
    without regard to case, for a case-sensitive file system (a Linux Steam library)."""
    if not path:
        return False
    try:
        common = any(n.lower() == "common" and os.path.isdir(os.path.join(path, "zone", n))
                     for n in os.listdir(os.path.join(path, "zone")))
    except OSError:
        return False
    return common and os.path.isfile(os.path.join(path, "localization.txt")) \
        and bool(glob.glob(os.path.join(path, "main", "*.iwd")))


def find_installs():
    found = []
    for root in steam_roots():
        for lib in library_folders(root):
            p = os.path.join(lib, "steamapps", "common", GAME_FOLDER)
            if is_install(p):
                found.append(os.path.normpath(p))
    return list(dict.fromkeys(found))


# ------------------------------------------------------------------------------------------------------------ state
_md5_cache = {}


def file_md5(path):
    """The file's md5, computed again only when its size or date changed (the views ask every few seconds)."""
    st = os.stat(path)
    key = (st.st_size, st.st_mtime_ns)
    hit = _md5_cache.get(path)
    if hit and hit[0] == key:
        return hit[1]
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    _md5_cache[path] = (key, h.hexdigest())
    return h.hexdigest()


class Layout:
    """Where the package keeps each part."""

    def __init__(self, dist_root):
        self.root = dist_root
        self.localization = os.path.join(dist_root, "localization.txt")
        self.main = os.path.join(dist_root, "main")
        self.video = os.path.join(dist_root, "main", "video")
        self.zone = os.path.join(dist_root, "zone")
        self.shaders_pack = os.path.join(dist_root, "shaders.pack")
        self.shaders_spv = os.path.join(dist_root, "shaders.spv")
        self.ffconv = os.path.join(dist_root, FFCONV_NAME)
        self.marker = os.path.join(dist_root, "zone", MARKER)
        self.log = os.path.join(dist_root, "main", "zmclient_setup.log")
        # The GL renderer cannot start without shaders.pack; on Windows only Vulkan reads it (the system's Direct3D 9,
        # the default, takes the zones' own shaders), and Vulkan falls back to it without shaders.spv.
        self.needs_pack = not IS_WINDOWS


def spirv_state(lay):
    """(ok, text) of shaders.spv: there and at least as new as shaders.pack, which it is compiled from."""
    try:
        spv = os.stat(lay.shaders_spv).st_mtime
    except OSError:
        return False, tr("missing: no Vulkan (the game takes its usual renderer)")
    try:
        if os.stat(lay.shaders_pack).st_mtime > spv:
            return False, tr("older than shaders.pack: to redo (Install)")
    except OSError:
        pass
    return True, tr("present (Vulkan)")


def state(dist_root):
    """{part: (ok, text)} for localization, iwd, video, zones, pack."""
    lay = Layout(dist_root)
    out = {}
    out["localization"] = (os.path.isfile(lay.localization), tr("present") if os.path.isfile(lay.localization)
                           else tr("missing"))
    iwds = glob.glob(os.path.join(lay.main, "*.iwd"))
    out["iwd"] = (bool(iwds), tr("{n} .iwd files").format(n=len(iwds)) if iwds else tr("no .iwd"))
    videos = glob.glob(os.path.join(lay.video, "*"))
    out["video"] = (bool(videos), tr("{n} files").format(n=len(videos)) if videos
                    else tr("missing (the cinematics do not play)"))
    zones = glob.glob(os.path.join(lay.zone, "*", "*.ff"))
    marker = None
    try:
        with open(lay.marker, encoding="utf-8") as f:
            marker = json.load(f)
    except (OSError, ValueError):
        pass
    if not zones:
        out["zones"] = (False, tr("not converted"))
    elif marker and os.path.isfile(lay.ffconv) and marker.get("ffconv_md5") != file_md5(lay.ffconv):
        out["zones"] = (False, tr("{n} zones from another ffconv: to convert again").format(n=len(zones)))
    elif marker:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(marker.get("time", 0)))
        out["zones"] = (True, tr("{n} zones converted on {when}").format(n=len(zones), when=when))
    else:
        out["zones"] = (True, tr("{n} zones (shipped with the package)").format(n=len(zones)))
    ok = os.path.isfile(lay.shaders_pack)
    out["pack"] = (ok, tr("present") if ok else tr("missing (comes with the zones)") if lay.needs_pack
                   else tr("missing (comes with the zones); Vulkan only"))
    out["spirv"] = spirv_state(lay)
    return out


OPTIONAL = ("video", "spirv")   # the game starts without them: no cinematics, no Vulkan


def ready(dist_root):
    """None when the game can start, else what is missing."""
    lay = Layout(dist_root)
    missing = [k for k, (ok, _) in state(dist_root).items()
               if not ok and k not in OPTIONAL and (k != "pack" or lay.needs_pack)]
    names = {"localization": "localization.txt", "iwd": tr("the .iwd files"), "zones": tr("the converted zones"),
             "pack": "shaders.pack"}
    return None if not missing else tr("missing {parts}").format(parts=", ".join(names[k] for k in missing))


def _windows_paths(tool, paths):
    """The paths as the Windows program sees them (wslpath -w, winepath -w), or the error text."""
    try:
        return [subprocess.run([tool, "-w", p], capture_output=True, text=True, check=True).stdout.strip()
                for p in paths]
    except (OSError, subprocess.CalledProcessError) as e:
        return tr("{tool}: {error}").format(tool=os.path.basename(tool), error=e)


def converter_command(lay, install, out_dir):
    """ffconv's command line, or a text saying why there is none. ffconv is a Windows program: Linux runs it through
    WSL's interop when it can (a WSL distribution runs .exe files itself), else under wine. OpenBSD cannot run it:
    ffconv is a 32-bit program and OpenBSD's wine runs 64-bit ones only."""
    if IS_OPENBSD:
        return tr("no conversion on OpenBSD (ffconv is a 32-bit Windows program): convert on a Windows or Linux "
                  "PC (ZmClient, Setup view), copy zone/ and shaders.pack here, then untick the conversion (z)")
    if not os.path.isfile(lay.ffconv):
        return tr("no {ffconv} in the folder: this package cannot convert the zones").format(ffconv=FFCONV_NAME)
    if IS_WINDOWS:
        return [lay.ffconv, "--verify", "--game", install, "--out", out_dir]
    wslpath = shutil.which("wslpath")
    if wslpath and os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        runner, tool = [], wslpath
    else:
        wine, winepath = shutil.which("wine"), shutil.which("winepath")
        if not wine or not winepath:
            return tr("ffconv is a Windows program: install wine, or convert on a Windows PC (ZmClient, Setup "
                      "view) and copy zone/ and shaders.pack here")
        runner, tool = [wine], winepath
    win = _windows_paths(tool, [install, out_dir])
    if isinstance(win, str):
        return win
    return runner + [lay.ffconv, "--verify", "--game", win[0], "--out", win[1]]


# ------------------------------------------------------------------------------------------------------------- copy
def _plan_copies(install, lay, video):
    """(source, destination, size) of every file to copy (the ones whose size or date differ)."""
    pairs = [(os.path.join(install, "localization.txt"), lay.localization)]
    pairs += [(p, os.path.join(lay.main, os.path.basename(p))) for p in sorted(glob.glob(os.path.join(install, "main",
                                                                                                      "*.iwd")))]
    if video:
        src = os.path.join(install, "main", "video")
        for dirpath, _, files in os.walk(src):
            for n in sorted(files):
                p = os.path.join(dirpath, n)
                pairs.append((p, os.path.join(lay.video, os.path.relpath(p, src))))
    plan = []
    for s, d in pairs:
        st = os.stat(s)
        try:
            dt = os.stat(d)
            if dt.st_size == st.st_size and int(dt.st_mtime) == int(st.st_mtime):
                continue
        except OSError:
            pass
        plan.append((s, d, st.st_size))
    return plan


class Setup(threading.Thread):
    """Runs the copy, the conversion and the SPIR-V compilation; the view reads `phase`, `done_bytes`/`total_bytes`,
    `zone_at`/`zone_count`, `shader_at`/`shader_count`, `lines` (the last output lines, `line_count` in all) and, at
    the end, `error` (None on success) and `warning` (Vulkan left out, the rest done)."""

    def __init__(self, dist_root, install, video=True, convert=True, spirv=True):
        super().__init__(daemon=True)
        self.lay = Layout(dist_root)
        # absolute: ffconv runs from the package folder, where a relative path would point elsewhere
        self.install = os.path.abspath(install)
        self.video = video
        self.convert = convert
        self.spirv = spirv
        # shown through tr(); the Setup view also compares it to these English values
        self.phase = "preparing"
        self.done_bytes = self.total_bytes = 0
        self.zone_at = self.zone_count = 0
        self.shader_at = self.shader_count = 0
        self.warning = None
        self.lines = []             # the last 200 lines
        self.line_count = 0         # every line noted so far
        self._lines_lock = threading.Lock()
        self.error = None
        self.finished = False
        self.ended = 0.0            # monotonic time it finished
        self.cancelled = False
        self._proc = None

    def note(self, line):
        with self._lines_lock:
            self.lines.append(line)
            self.line_count += 1
            del self.lines[:-200]
        try:
            with open(self.lay.log, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def since(self, count):
        """(the lines noted after the first `count`, as many as are kept; the new total)."""
        with self._lines_lock:
            new = min(self.line_count - count, len(self.lines))
            return (self.lines[-new:] if new > 0 else []), self.line_count

    def cancel(self):
        self.cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def run(self):
        try:
            self._run()
        except OSError as e:
            self.error = str(e)
        if self.error:
            self.note(tr("failed: {error}").format(error=self.error))
        self.ended = time.monotonic()
        self.finished = True

    def _run(self):
        lay = self.lay
        if not is_install(self.install):
            self.error = tr("{path} is not a Black Ops install (zone/, main/*.iwd, localization.txt)").format(
                path=self.install)
            return
        if os.path.normcase(os.path.abspath(self.install)) == os.path.normcase(os.path.abspath(lay.root)):
            self.error = tr("the game's folder and the package's are the same")
            return
        os.makedirs(lay.main, exist_ok=True)
        self.note(tr("--- setup from {path} ({time}) ---").format(path=self.install,
                                                                 time=time.strftime("%Y-%m-%d %H:%M:%S")))
        plan = _plan_copies(self.install, lay, self.video)
        self.total_bytes = sum(p[2] for p in plan)
        need = self.total_bytes + (ZONES_BYTES if self.convert else 0)
        free = shutil.disk_usage(lay.root).free
        if free < need:
            self.error = tr("not enough room: {need} MB needed, {free} MB free").format(need=need >> 20,
                                                                                        free=free >> 20)
            return
        if self.convert:
            # before the long copy: a package that cannot convert should say so at once
            probe = converter_command(lay, self.install, lay.root)
            if isinstance(probe, str):
                self.error = probe
                return
        self.phase = "copying"
        self.note(tr("{n} files to copy ({size} MB), the others are up to date").format(
            n=len(plan), size=self.total_bytes >> 20))
        for src, dst, size in plan:
            if self.cancelled:
                self.error = tr("cancelled")
                return
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + ".zmclient-part"
            with open(src, "rb") as fi, open(tmp, "wb") as fo:
                while True:
                    chunk = fi.read(4 << 20)
                    if not chunk:
                        break
                    fo.write(chunk)
                    self.done_bytes += len(chunk)
                    if self.cancelled:
                        break
            if self.cancelled:
                os.remove(tmp)
                self.error = tr("cancelled")
                return
            shutil.copystat(src, tmp)
            os.replace(tmp, dst)
            self.note(tr("copied {path}").format(path=os.path.relpath(dst, lay.root)))
        if self.convert:
            self._convert()
            if self.error:
                return
        if self.spirv and not spirv_state(lay)[0]:
            self._compile_spirv()
        self.phase = "done"

    def _compile_spirv(self):
        """shaders.spv from shaders.pack. A missing glslang or a failure leaves the rest installed: `warning`."""
        lay = self.lay
        if not os.path.isfile(lay.shaders_pack):
            self.warning = tr("no shaders.pack (converting the zones makes it): no Vulkan")
            self.note(self.warning)
            return
        glslang = spirvpack.find_glslang(lay.root)
        if not glslang:
            self.warning = tr("no glslang: no Vulkan (Linux: install glslang-tools, OpenBSD: doas pkg_add "
                              "glslang, then Install again)")
            self.note(self.warning)
            return
        # shaders.spv is ~3.6 times shaders.pack (478 MB from 133 MB), plus a copy while it replaces the old one
        need = 8 * os.path.getsize(lay.shaders_pack)
        free = shutil.disk_usage(lay.root).free
        if free < need:
            self.warning = tr("not enough room for shaders.spv ({need} MB, {free} free): no Vulkan").format(
                need=need >> 20, free=free >> 20)
            self.note(self.warning)
            return
        self.phase = "Vulkan shaders"
        self.note(tr("shaders.spv: {glslang}, {n} at a time").format(glslang=glslang, n=os.cpu_count() or 1))

        def progress(at, total):
            self.shader_at, self.shader_count = at, total
        try:
            result = spirvpack.build(lay.shaders_pack, lay.shaders_spv, glslang, progress=progress,
                                     cancelled=lambda: self.cancelled)
        except (spirvpack.PackError, OSError) as e:
            self.warning = tr("shaders.spv not compiled ({error}): no Vulkan").format(error=e)
            self.note(self.warning)
            return
        if result is None:
            self.error = tr("cancelled")
            return
        good, size, failures = result
        self.note(tr("shaders.spv: {good} shaders, {size} MB, {refused} refused").format(
            good=good, size=size >> 20, refused=len(failures)))
        for h, stage, err in failures[:20]:
            self.note(tr("  {shader}: {error}").format(shader=f"{h:016x}.{spirvpack.STAGES[stage]}", error=err))
        if failures:
            self.warning = tr("{n} shaders refused by glslang: some objects will be missing under Vulkan").format(
                n=len(failures))

    def _convert(self):
        lay = self.lay
        self.phase = "converting zones"
        new = os.path.join(lay.root, "zone.zmclient-new")
        shutil.rmtree(new, ignore_errors=True)
        os.makedirs(new)
        cmd = converter_command(lay, self.install, new)
        if isinstance(cmd, str):
            self.error = cmd
            return
        self.note(tr("ffconv: {command}").format(command=" ".join(cmd)))
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}
        self._proc = subprocess.Popen(cmd, cwd=lay.root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, **kwargs)
        with self._proc.stdout:
            for raw in self._proc.stdout:
                line = raw.decode("latin-1").rstrip("\r\n")
                m = _PROGRESS.match(line)
                if m:
                    self.zone_at, self.zone_count = int(m.group(1)), int(m.group(2))
                self.note(line)
        code = self._proc.wait()
        if self.cancelled:
            shutil.rmtree(new, ignore_errors=True)
            self.error = tr("cancelled")
            return
        produced = glob.glob(os.path.join(new, "zone", "*", "*.ff"))
        if code != 0 or not produced:
            shutil.rmtree(new, ignore_errors=True)
            self.error = tr("ffconv failed (code {code}): the previous zones are kept; details in {log}").format(
                code=code, log=lay.log)
            return
        self.phase = "putting in place"
        old = os.path.join(lay.root, "zone.zmclient-old")
        shutil.rmtree(old, ignore_errors=True)
        if os.path.isdir(lay.zone):
            os.replace(lay.zone, old)
        os.replace(os.path.join(new, "zone"), lay.zone)
        pack = os.path.join(new, "shaders.pack")
        if os.path.isfile(pack):
            os.replace(pack, lay.shaders_pack)
        shutil.rmtree(new, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
        with open(lay.marker, "w", encoding="utf-8") as f:
            json.dump({"ffconv_md5": file_md5(lay.ffconv), "time": time.time(), "install": self.install,
                       "zones": len(produced)}, f)
        self.note(tr("{n} zones in place").format(n=len(produced)))
