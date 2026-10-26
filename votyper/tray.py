"""Status icon via the StatusNotifierItem D-Bus protocol (KDE and most Linux desktops).

If there is no StatusNotifier host, the tray quietly stays off; dictation is
unaffected.
"""

import os
import threading

from .icon import icons
from .logs import log
from .dbus import F_IFACE, F_MEMBER, Bus

PATH, IFACE = "/StatusNotifierItem", "org.kde.StatusNotifierItem"
INTROSPECT = ('<node><interface name="org.kde.StatusNotifierItem">'
              '<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>'
              '<signal name="NewIcon"/><signal name="NewToolTip"/></interface></node>')


class Tray:
    def __init__(self):
        self._bus = None
        self._on_click = lambda: None
        self._state, self._tooltip = "loading", "votyper"

    def start(self, on_click) -> None:
        self._on_click = on_click
        ready = threading.Event()
        threading.Thread(target=self._run, args=(ready,), daemon=True).start()
        ready.wait(5)

    def _run(self, ready) -> None:
        try:
            bus = Bus(self._handle)
            name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
            bus.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                     "RequestName", "su", (name, 0))
            bus.call("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                     "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem", "s", (name,))
            self._bus = bus
        except Exception as e:
            log.warning("tray disabled (%s)", e)
            return
        finally:
            ready.set()
        try:
            while True:
                bus.dispatch(bus.read_message())
        except Exception:
            pass                                 # socket closed on shutdown

    def _props(self) -> dict:
        return {
            "Category": ("s", "ApplicationStatus"), "Id": ("s", "votyper"),
            "Title": ("s", "votyper"), "Status": ("s", "Active"), "WindowId": ("u", 0),
            "IconName": ("s", ""), "IconPixmap": ("a(iiay)", icons(self._state)),
            "OverlayIconName": ("s", ""), "OverlayIconPixmap": ("a(iiay)", []),
            "AttentionIconName": ("s", ""), "AttentionIconPixmap": ("a(iiay)", []),
            "AttentionMovieName": ("s", ""),
            "ToolTip": ("(sa(iiay)ss)", ("", [], "votyper", self._tooltip)),
            "ItemIsMenu": ("b", False), "Menu": ("o", "/NO_DBUSMENU"),
        }

    def _handle(self, msg):
        iface, member, body = msg["fields"].get(F_IFACE), msg["fields"].get(F_MEMBER), msg["body"]
        if member == "Introspect":
            return "s", (INTROSPECT,)
        if member in ("Ping", "ContextMenu", "SecondaryActivate", "Scroll"):
            return "", ()
        if member == "Activate":
            threading.Thread(target=self._on_click, daemon=True).start()
            return "", ()
        if iface == "org.freedesktop.DBus.Properties":
            props = self._props()
            if member == "GetAll":
                return "a{sv}", (list(props.items()),)
            if member == "Get":
                return "v", (props[body[1]],)
        raise RuntimeError(f"unknown method {iface}.{member}")

    def update(self, state: str, tooltip: str) -> None:
        tooltip_changed = tooltip != self._tooltip
        self._state, self._tooltip = state, tooltip
        if self._bus:
            try:
                self._bus.signal(PATH, IFACE, "NewIcon")
                if tooltip_changed:             # the blink changes only the icon
                    self._bus.signal(PATH, IFACE, "NewToolTip")
            except OSError:
                pass

    def close(self) -> None:
        if self._bus:
            self._bus.close()
