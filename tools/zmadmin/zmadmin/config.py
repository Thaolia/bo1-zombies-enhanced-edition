"""ZmAdmin's own files: saved servers, the local servers' profiles, the console history.

A game folder (a make_dist.sh folder) can run several servers at once, one per profile: each has its port, rcon
password, game and the settings the Settings view applied. The profile "default" stays where older ZmAdmins (and
ZmClient's local server) keep it, flat in local[<folder>]; the others go under local[<folder>]["profiles"].
"""
import json
import os
import re
import secrets
import string

DEFAULT_PROFILE = "default"
DEFAULT_PORT = 3074
_PROFILE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "zmadmin")


def new_password(length=16):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Config:
    def __init__(self, directory=None):
        self.dir = directory or config_dir()
        self.path = os.path.join(self.dir, "servers.json")
        self.history_path = os.path.join(self.dir, "history.txt")
        self.servers = []           # dicts: name, host, port, password
        self.local = {}             # dist folder -> dict: password, port, map
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        self.servers = [s for s in data.get("servers", []) if isinstance(s, dict) and s.get("host")]
        self.local = data.get("local", {}) if isinstance(data.get("local"), dict) else {}

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.path + ".tmp"
        # passwords inside: readable by the user only
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"servers": self.servers, "local": self.local}, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def _folder(self, dist_root):
        return self.local.setdefault(os.path.normcase(os.path.abspath(dist_root)), {})

    @staticmethod
    def _defaults(entry, port):
        entry.setdefault("password", new_password())
        entry.setdefault("port", port)
        entry.setdefault("map", "zombie_theater")
        entry.setdefault("settings", {})
        return entry

    def local_settings(self, dist_root):
        """The default profile (the one ZmClient's local server uses)."""
        return self._defaults(self._folder(dist_root), DEFAULT_PORT)

    def _others(self, dist_root):
        folder = self._folder(dist_root)
        if not isinstance(folder.get("profiles"), dict):
            folder["profiles"] = {}
        return folder["profiles"]

    def local_profiles(self, dist_root):
        """[(name, entry)]: the default profile first, then the others by name."""
        default = self.local_settings(dist_root)
        others = self._others(dist_root)
        return [(DEFAULT_PROFILE, default)] + [(n, self._defaults(others[n], DEFAULT_PORT))
                                               for n in sorted(others, key=str.lower) if isinstance(others[n], dict)]

    def local_profile(self, dist_root, name):
        """The profile's entry, or None."""
        if name == DEFAULT_PROFILE:
            return self.local_settings(dist_root)
        entry = self._others(dist_root).get(name)
        return self._defaults(entry, DEFAULT_PORT) if isinstance(entry, dict) else None

    def next_port(self, dist_root):
        """The first of 3074, 3076, ... that no profile of the folder uses: a server also listens on port + 1 (the
        clients' logs), so two servers keep two ports apart."""
        used = [int(e["port"]) for _, e in self.local_profiles(dist_root)]
        port = DEFAULT_PORT
        while any(abs(port - u) < 2 for u in used):
            port += 2
        return port

    def check_profile_name(self, dist_root, name):
        """None when `name` can be a new profile's name, else why not."""
        if not _PROFILE_NAME.match(name):
            return "lettres, chiffres, - et _ seulement (32 au plus)"
        # case-insensitive: the profile's folder servers/<name> would be the same one on Windows
        taken = {n.lower() for n, _ in self.local_profiles(dist_root)}
        if name.lower() in taken:
            return f"le profil « {name} » existe déjà"
        return None

    def add_profile(self, dist_root, name):
        why = self.check_profile_name(dist_root, name)
        if why:
            raise ValueError(why)
        entry = self._defaults({}, self.next_port(dist_root))
        self._others(dist_root)[name] = entry
        return entry

    def remove_profile(self, dist_root, name):
        if name == DEFAULT_PROFILE:
            raise ValueError("le profil default ne se supprime pas")
        self._others(dist_root).pop(name, None)

    def load_history(self):
        try:
            with open(self.history_path, encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f if line.strip()][-100:]
        except OSError:
            return []

    def save_history(self, history):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.history_path, "w", encoding="utf-8") as f:
            f.write("".join(h + "\n" for h in history[-100:]))
