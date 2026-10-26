"""A tiny D-Bus client: connect, call methods, send signals, answer calls.

D-Bus wire format: values are aligned to their size; structs/dict entries to 8.
"""

import os
import socket
import struct
import threading

# D-Bus wire format: values are aligned to their size; structs/dict entries to 8.
DB_ALIGN = dict(y=1, b=4, n=2, q=2, i=4, u=4, x=8, t=8, d=8, s=4, o=4, g=1, v=1, a=4)
DB_ALIGN.update({"(": 8, "{": 8})
DB_FMT = dict(y="B", n="h", q="H", i="i", u="I", x="q", t="Q", d="d")


def db_end(sig: str, i: int = 0) -> int:
    """Index just past the complete type starting at sig[i]."""
    if sig[i] == "a":
        return db_end(sig, i + 1)
    if sig[i] in "({":
        depth = 0
        for j in range(i, len(sig)):
            depth += sig[j] in "({"
            depth -= sig[j] in ")}"
            if depth == 0:
                return j + 1
    return i + 1


def db_types(sig: str) -> list:
    out, i = [], 0
    while i < len(sig):
        j = db_end(sig, i)
        out.append(sig[i:j])
        i = j
    return out


def db_pad(buf: bytearray, n: int) -> None:
    buf.extend(b"\0" * (-len(buf) % n))


def db_put(buf: bytearray, sig: str, val) -> None:
    c = sig[0]
    db_pad(buf, DB_ALIGN[c])
    if c in DB_FMT:
        buf += struct.pack("<" + DB_FMT[c], val)
    elif c == "b":
        buf += struct.pack("<I", int(val))
    elif c in "so":
        raw = val.encode()
        buf += struct.pack("<I", len(raw)) + raw + b"\0"
    elif c == "g":
        raw = val.encode()
        buf += bytes([len(raw)]) + raw + b"\0"
    elif c == "v":
        inner, value = val
        db_put(buf, "g", inner)
        db_put(buf, inner, value)
    elif c == "a":
        elem = sig[1:db_end(sig, 1)]
        db_pad(buf, 4)
        len_at = len(buf)
        buf += b"\0\0\0\0"
        db_pad(buf, DB_ALIGN[elem[0]])      # padding exists even if empty
        start = len(buf)
        if elem == "y":
            buf += bytes(val)
        else:
            for item in (val.items() if isinstance(val, dict) else val):
                db_put(buf, elem, item)
        struct.pack_into("<I", buf, len_at, len(buf) - start)
    else:  # "(" struct or "{" dict entry
        for sub, item in zip(db_types(sig[1:-1]), val):
            db_put(buf, sub, item)


def db_get(data: bytes, off: int, sig: str):
    """Read one value; returns (value, new_offset)."""
    c = sig[0]
    off += -off % DB_ALIGN[c]
    if c in DB_FMT:
        size = struct.calcsize(DB_FMT[c])
        return struct.unpack_from("<" + DB_FMT[c], data, off)[0], off + size
    if c == "b":
        return bool(struct.unpack_from("<I", data, off)[0]), off + 4
    if c in "so":
        n = struct.unpack_from("<I", data, off)[0]
        return data[off + 4:off + 4 + n].decode(), off + 5 + n
    if c == "g":
        n = data[off]
        return data[off + 1:off + 1 + n].decode(), off + 2 + n
    if c == "v":
        inner, off = db_get(data, off, "g")
        return db_get(data, off, inner)
    if c == "a":
        elem = sig[1:db_end(sig, 1)]
        n = struct.unpack_from("<I", data, off)[0]
        off += 4
        off += -off % DB_ALIGN[elem[0]]
        end, items = off + n, []
        while off < end:
            item, off = db_get(data, off, elem)
            items.append(item)
        return items, off
    items = []                                  # struct or dict entry
    for sub in db_types(sig[1:-1]):
        item, off = db_get(data, off, sub)
        items.append(item)
    return tuple(items), off


CALL, RETURN, ERROR, SIGNAL = 1, 2, 3, 4
F_PATH, F_IFACE, F_MEMBER, F_ERRNAME, F_REPLY, F_DEST, F_SENDER, F_SIG = range(1, 9)


class Bus:
    """Just enough D-Bus: connect, call methods, send signals, serve a few calls."""

    def __init__(self, on_call):
        self._on_call = on_call                 # (msg) -> (sig, values) or raises
        self._serial = 0
        self._wlock = threading.Lock()
        addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
        path = next((p.split("=", 1)[1] for p in addr.split(",") if p.startswith("unix:path=")),
                    f"/run/user/{os.getuid()}/bus")
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(path)
        uid_hex = str(os.getuid()).encode().hex()
        self.sock.sendall(b"\0AUTH EXTERNAL " + uid_hex.encode() + b"\r\n")
        if not self._readline().startswith(b"OK"):
            raise RuntimeError("D-Bus authentication refused")
        self.sock.sendall(b"BEGIN\r\n")
        self.name = self.call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                              "org.freedesktop.DBus", "Hello")[0]

    def _readline(self) -> bytes:
        line = b""
        while not line.endswith(b"\r\n"):
            line += self.sock.recv(1)
        return line

    def _read(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("D-Bus closed")
            data += chunk
        return data

    def _send(self, mtype, fields, sig="", body=(), flags=0) -> int:
        payload = bytearray()
        for sub, item in zip(db_types(sig), body):
            db_put(payload, sub, item)
        with self._wlock:
            self._serial += 1
            hdr_fields = [(code, (fsig, val)) for code, fsig, val in fields]
            if sig:
                hdr_fields.append((F_SIG, ("g", sig)))
            buf = bytearray(struct.pack("<BBBBII", ord("l"), mtype, flags, 1,
                                        len(payload), self._serial))
            db_put(buf, "a(yv)", hdr_fields)
            db_pad(buf, 8)
            self.sock.sendall(bytes(buf) + bytes(payload))
            return self._serial

    def read_message(self) -> dict:
        fixed = self._read(16)
        body_len, serial, fields_len = struct.unpack_from("<III", fixed, 4)
        rest = self._read(fields_len + (-fields_len % 8) + body_len)
        raw_fields, _ = db_get(fixed + rest, 12, "a(yv)")
        msg = {"type": fixed[1], "serial": serial, "fields": dict(raw_fields), "body": ()}
        sig = msg["fields"].get(F_SIG, "")
        body = (fixed + rest)[16 + fields_len + (-fields_len % 8):]
        off, vals = 0, []
        for sub in db_types(sig):
            val, off = db_get(body, off, sub)
            vals.append(val)
        msg["body"] = tuple(vals)
        return msg

    def call(self, dest, path, iface, member, sig="", body=()):
        """Blocking method call; returns the reply body."""
        serial = self._send(CALL, [(F_PATH, "o", path), (F_DEST, "s", dest),
                                    (F_IFACE, "s", iface), (F_MEMBER, "s", member)],
                            sig, body)
        while True:
            msg = self.read_message()
            if msg["fields"].get(F_REPLY) == serial:
                if msg["type"] == ERROR:
                    raise RuntimeError(f"{msg['fields'].get(F_ERRNAME)}: {msg['body']}")
                return msg["body"]
            self.dispatch(msg)

    def signal(self, path, iface, member, sig="", body=()):
        self._send(SIGNAL, [(F_PATH, "o", path), (F_IFACE, "s", iface),
                             (F_MEMBER, "s", member)], sig, body)

    def dispatch(self, msg) -> None:
        """Answer a method call aimed at us; ignore everything else."""
        if msg["type"] != CALL:
            return
        f = msg["fields"]
        try:
            sig, vals = self._on_call(msg)
            fields = [(F_REPLY, "u", msg["serial"]), (F_DEST, "s", f.get(F_SENDER, ""))]
            self._send(RETURN, fields, sig, vals)
        except Exception as e:
            fields = [(F_REPLY, "u", msg["serial"]), (F_DEST, "s", f.get(F_SENDER, "")),
                      (F_ERRNAME, "s", "org.freedesktop.DBus.Error.UnknownMethod")]
            self._send(ERROR, fields, "s", (str(e),))

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
