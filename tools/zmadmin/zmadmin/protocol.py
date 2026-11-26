"""UDP side of a BO1 zombies dedicated server: the getstatus query and rcon (docs/SERVER.md).

The server runs at most one rcon command every 500 ms, all senders together (SVC_RemoteCommand,
src/server_mp/sv_main_pc_mp.cpp): a command sent sooner is dropped without a reply. RconClient therefore spaces its
commands and retries once on silence.
"""
import re
import select
import socket
import threading
import time

from .i18n import tr

OOB = b"\xff\xff\xff\xff"
DEFAULT_PORT = 3074
CLIENT_STATES = {3: "connected", 4: "loading", 5: "active"}
_COLOR = re.compile(r"\^[0-9]")


class ProtocolError(Exception):
    pass


class RconTimeout(ProtocolError):
    pass


class RconAuthError(ProtocolError):
    pass


def strip_colors(text):
    return _COLOR.sub("", text)


def parse_target(text, default_port=DEFAULT_PORT):
    text = text.strip()
    host, sep, port = text.rpartition(":")
    if not sep:
        return text, default_port
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError(tr("invalid port: {port}").format(port=repr(port)))
    return host, int(port)


class Status:
    def __init__(self, info, players):
        self.info = info
        self.players = players

    def get(self, key, default=""):
        return self.info.get(key, default)

    @property
    def max_clients(self):
        try:
            return int(self.info.get("sv_maxclients", "0"))
        except ValueError:
            return 0


class StatusPlayer:
    def __init__(self, slot, score, ping, state, name):
        self.slot = slot
        self.score = score
        self.ping = ping
        self.state = state
        self.name = name

    @property
    def state_name(self):
        return CLIENT_STATES.get(self.state, str(self.state))


def parse_status(data):
    """statusResponse: the serverinfo string, then one '<slot> <score> <ping> <state> "<name>"' line per client."""
    head = OOB + b"statusResponse\n"
    if not data.startswith(head):
        raise ProtocolError(tr("unexpected answer: {data}").format(data=repr(data[:32])))
    lines = data[len(head):].decode("latin-1").rstrip("\x00").split("\n")
    fields = lines[0].split("\\")[1:] if lines else []
    info = {k: strip_colors(v) for k, v in zip(fields[0::2], fields[1::2])}
    players = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(" ", 4)
        if len(parts) != 5:
            raise ProtocolError(tr("unreadable player line: {line}").format(line=repr(line)))
        slot, score, ping, state, name = parts
        players.append(StatusPlayer(int(slot), int(score), int(ping), int(state), strip_colors(name.strip('"'))))
    return Status(info, players)


def _recv(sock):
    """One datagram, or None for the ICMP port-unreachable of an earlier send: Windows reports it on the next receive
    of a UDP socket (WSAECONNRESET) while the server is down or still loading; Linux drops it."""
    try:
        return sock.recvfrom(65536)
    except ConnectionResetError:
        return None


def _drain(sock):
    while select.select([sock], [], [], 0)[0]:
        try:
            _recv(sock)
        except OSError:
            return


def query_status(addr, timeout=1.0, sock=None):
    own = sock is None
    if own:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _drain(sock)
        sock.sendto(OOB + b"getstatus", addr)
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0 or not select.select([sock], [], [], left)[0]:
                raise RconTimeout(tr("no answer from {host}:{port}").format(host=addr[0], port=addr[1]))
            packet = _recv(sock)
            if packet is None:
                continue
            data, src = packet
            if src[1] == addr[1] and data.startswith(OOB + b"statusResponse"):
                return parse_status(data)
    finally:
        if own:
            sock.close()


class ModInfo:
    """modinfoResponse (SV_ModInfoRequest, getmodinfo): what a client must load to play on the server. refused: the
    server has a player password and it was not the one sent."""
    DVARS = ("fs_game", "fs_mods", "bo1_mod_zones", "bo1_bspworld", "bo1_mod_mapkit")

    def __init__(self, values=None, refused=False):
        self.values = dict(values or {})
        self.refused = refused

    def get(self, key, default=""):
        return self.values.get(key, default)

    def args(self):
        """The client's command line for them, in DVARS' order (fs_game first)."""
        out = []
        for dvar in self.DVARS:
            if self.values.get(dvar):
                out += ["+set", dvar, self.values[dvar]]
        return out


def modinfo_request(password=""):
    return OOB + b'getmodinfo "' + password.encode("latin-1") + b'"'


def parse_modinfo(data):
    head = OOB + b"modinfoResponse\n"
    if not data.startswith(head):
        raise ProtocolError(tr("unexpected answer: {data}").format(data=repr(data[:32])))
    body = data[len(head):].decode("latin-1").rstrip("\x00\n")
    if body == "refused":
        return ModInfo(refused=True)
    fields = body.split("\\")[1:]
    return ModInfo({k: v for k, v in zip(fields[0::2], fields[1::2]) if k in ModInfo.DVARS})


def query_modinfo(addr, password="", timeout=1.0):
    """The server's mods, or RconTimeout when it does not answer (an older server ignores getmodinfo). It answers one
    such request every 50 ms: the request goes twice, half the wait apart."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        end = time.monotonic() + timeout
        for attempt in range(2):
            _drain(sock)
            sock.sendto(modinfo_request(password), addr)
            until = end - timeout / 2 if attempt == 0 else end
            while True:
                left = until - time.monotonic()
                if left <= 0 or not select.select([sock], [], [], left)[0]:
                    break
                packet = _recv(sock)
                if packet is None:
                    continue
                data, src = packet
                if src[1] == addr[1] and data.startswith(OOB + b"modinfoResponse"):
                    return parse_modinfo(data)
        raise RconTimeout(tr("no answer from {host}:{port}").format(host=addr[0], port=addr[1]))
    finally:
        sock.close()


def _print_text(data):
    text = data[len(OOB):].decode("latin-1")
    # BO1 puts a 0x01 byte between the out-of-band header and "print"
    text = text.lstrip("\x01")
    if not text.startswith("print"):
        return None
    return text[len("print"):].lstrip("\r\n").rstrip("\x00")


class RconClient:
    """Thread-safe: commands from several threads run one at a time, spaced by `spacing` seconds."""

    def __init__(self, addr, password, spacing=0.55, quiet=0.3, timeout=1.5):
        self.addr = addr
        self.password = password
        self.spacing = spacing
        self.quiet = quiet
        self.timeout = timeout
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._lock = threading.Lock()
        self._last_send = 0.0

    def close(self):
        self._sock.close()

    def _send_once(self, command):
        wait = self._last_send + self.spacing - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _drain(self._sock)
        self._sock.sendto(OOB + b"rcon " + self.password.encode("latin-1") + b" " + command.encode("latin-1"),
                          self.addr)
        self._last_send = time.monotonic()
        chunks = []
        end = self._last_send + self.timeout
        while True:
            limit = end if not chunks else time.monotonic() + self.quiet
            left = limit - time.monotonic()
            if left <= 0 or not select.select([self._sock], [], [], left)[0]:
                break
            packet = _recv(self._sock)
            if packet is None:
                continue
            data, src = packet
            if src[1] != self.addr[1] or not data.startswith(OOB):
                continue
            text = _print_text(data)
            if text is not None:
                chunks.append(text)
        return None if not chunks else "".join(chunks)

    def command(self, command):
        """The command's console output, colour codes kept (parse_dvars needs the '^7' that ends each value).
        Raises RconTimeout or RconAuthError."""
        if not self.password:
            raise RconAuthError(tr("no rcon password"))
        with self._lock:
            text = self._send_once(command)
            if text is None:
                # another admin's command may have taken the server's 500 ms slot
                text = self._send_once(command)
        if text is None:
            raise RconTimeout(tr("no rcon answer from {host}:{port}").format(host=self.addr[0], port=self.addr[1]))
        plain = strip_colors(text).strip()
        first = plain.splitlines()[0] if plain else ""
        if first == "Invalid password.":
            raise RconAuthError(tr("rcon password refused"))
        if first.startswith("The server must set 'rcon_password'"):
            raise RconAuthError(tr("the server has no rcon_password: rcon disabled"))
        return text
