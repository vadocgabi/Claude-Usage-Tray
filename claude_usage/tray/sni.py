"""A tray icon over D-Bus: org.kde.StatusNotifierItem + com.canonical.dbusmenu (pure Python, jeepney).

This is the protocol that GNOME (AppIndicator extension), KDE Plasma, XFCE, Cinnamon, MATE, LXQt,
Budgie, Deepin and Wayland bars such as waybar use for tray icons, so one implementation covers
them all, on X11 and on Wayland, and it works from a frozen binary (no GTK / PyGObject needed).

Everything that touches the bus runs in the single thread that calls `run()`; other threads only
post work to `_outbox`.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Callable, Optional

from . import BaseTray, Item, find_default

log = logging.getLogger("claude_usage")

SNI_INTERFACE = "org.kde.StatusNotifierItem"
MENU_INTERFACE = "com.canonical.dbusmenu"
WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
ICON_SIZES = (16, 22, 24, 32, 48, 64)
NO_TRAY_GRACE_SECONDS = 4.0

NODE_SIGNATURE = "(ia{sv}av)"


# ---------------------------------------------------------------- pure helpers (unit-testable)
def pixmaps_from_image(image, sizes=ICON_SIZES) -> list:
    """StatusNotifierItem IconPixmap value: [(width, height, ARGB32 bytes in network order)]."""
    from PIL import Image
    result = []
    for size in sizes:
        scaled = image.convert("RGBA").resize((size, size), Image.LANCZOS)
        red, green, blue, alpha = scaled.split()
        result.append((size, size, Image.merge("RGBA", (alpha, red, green, blue)).tobytes()))
    return result


class MenuModel:
    """The menu tree as com.canonical.dbusmenu sees it: stable integer ids, properties on demand."""

    def __init__(self, items: list):
        self.root = Item(children=items)
        self.revision = 1
        self._by_id: dict = {0: self.root}
        self._ids: dict = {id(self.root): 0}
        self._counter = 0
        self._assign(self.root)

    def _assign(self, item: Item) -> None:
        for child in item.children or []:
            self._counter += 1
            self._by_id[self._counter] = child
            self._ids[id(child)] = self._counter
            self._assign(child)

    def item(self, item_id: int) -> Optional[Item]:
        return self._by_id.get(item_id)

    def properties(self, item: Item) -> dict:
        """dbusmenu properties as {name: (signature, value)}."""
        if item.separator:
            return {"type": ("s", "separator"), "visible": ("b", True)}
        props = {"label": ("s", item.label().replace("_", "__")),   # '_' marks a mnemonic in dbusmenu
                 "enabled": ("b", bool(item.action) or item.children is not None),
                 "visible": ("b", item.is_visible())}
        if item.children is not None:
            props["children-display"] = ("s", "submenu")
        if item.checked is not None:
            props["toggle-type"] = ("s", "radio" if item.radio else "checkmark")
            props["toggle-state"] = ("i", 1 if item.is_checked() else 0)
        return props

    def node(self, item: Item, depth: int) -> tuple:
        """(id, properties, children) with children as variants; depth < 0 means the whole subtree."""
        children = []
        if item.children and depth != 0:
            for child in item.children:
                children.append((NODE_SIGNATURE, self.node(child, depth - 1)))
        props = self.properties(item) if item is not self.root else {"children-display": ("s", "submenu")}
        return self._ids[id(item)], props, children

    def layout(self, parent_id: int, depth: int) -> tuple:
        parent = self.item(parent_id) or self.root
        return self.revision, self.node(parent, depth)

    def group_properties(self, ids: list) -> list:
        wanted = ids or list(self._by_id)
        return [(i, self.properties(self._by_id[i])) for i in wanted if i in self._by_id and i != 0]


INTROSPECTION_ITEM = f"""<node>
 <interface name="{SNI_INTERFACE}">
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
  <property name="WindowId" type="u" access="read"/><property name="IconName" type="s" access="read"/>
  <property name="IconThemePath" type="s" access="read"/><property name="IconPixmap" type="a(iiay)" access="read"/><property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/><property name="Menu" type="o" access="read"/>
  <signal name="NewIcon"/><signal name="NewTitle"/><signal name="NewToolTip"/><signal name="NewStatus"><arg type="s"/></signal>
 </interface>
</node>"""

INTROSPECTION_MENU = f"""<node>
 <interface name="{MENU_INTERFACE}">
  <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
   <arg type="u" direction="out"/><arg type="(ia{{sv}}av)" direction="out"/></method>
  <method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/>
   <arg type="a(ia{{sv}})" direction="out"/></method>
  <method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
  <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/>
   <arg type="u" direction="in"/></method>
  <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
  <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
  <method name="AboutToShowGroup"><arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/></method>
  <property name="Version" type="u" access="read"/><property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/><property name="IconThemePath" type="as" access="read"/>
  <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
  <signal name="ItemsPropertiesUpdated"><arg type="a(ia{{sv}})"/><arg type="a(ia{{sv}})"/></signal>
 </interface>
</node>"""


def watcher_present(timeout: float = 1.5) -> bool:
    """True when a StatusNotifierWatcher owns its name on the session bus right now."""
    try:
        from jeepney import new_method_call
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection
        with open_dbus_connection(bus="SESSION") as connection:
            call = new_method_call(message_bus, "NameHasOwner", "s", (WATCHER_NAME,))
            return bool(connection.send_and_get_reply(call, timeout=timeout).body[0])
    except Exception:
        return False


def session_bus_available() -> bool:
    try:
        from jeepney.io.blocking import open_dbus_connection
        open_dbus_connection(bus="SESSION").close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- the tray
class SniTray(BaseTray):
    def __init__(self, name: str, image, title: str, items: list):
        super().__init__(name, image, title, items)
        self.model = MenuModel(items)
        self._pixmaps = pixmaps_from_image(image)
        self._stop = threading.Event()
        self._outbox: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._conn = None
        self._pending: dict = {}
        self._registered = False
        self._started = 0.0
        self._fallback_fired = False
        self._bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"

    # ---- public API (any thread)
    def set_icon(self, image) -> None:
        self.image = image
        pixmaps = pixmaps_from_image(image)
        self._post(lambda: (setattr(self, "_pixmaps", pixmaps), self._signal(ITEM_PATH, SNI_INTERFACE, "NewIcon")))

    def set_title(self, title: str) -> None:
        self.title = title
        self._post(lambda: (self._signal(ITEM_PATH, SNI_INTERFACE, "NewTitle"),
                            self._signal(ITEM_PATH, SNI_INTERFACE, "NewToolTip")))

    def refresh_menu(self) -> None:
        self._post(self._layout_updated)

    def notify(self, message: str, title: str) -> None:
        from .notifier import Notifier
        Notifier().send(title, message)

    def stop(self) -> None:
        self._stop.set()

    def _post(self, work: Callable[[], None]) -> None:
        self._outbox.put(work)

    # ---- bus plumbing (I/O thread only)
    def _send(self, message, callback: Optional[Callable] = None) -> None:
        serial = next(self._conn.outgoing_serial)
        self._conn.send(message, serial=serial)
        if callback is not None:
            self._pending[serial] = callback

    def _signal(self, path: str, interface: str, member: str, signature: str = "", body: tuple = ()) -> None:
        from jeepney import DBusAddress, new_signal
        self._send(new_signal(DBusAddress(path, interface=interface), member, signature, body))

    def _layout_updated(self) -> None:
        self.model.revision += 1
        self._signal(MENU_PATH, MENU_INTERFACE, "LayoutUpdated", "ui", (self.model.revision, 0))

    def _call_bus(self, member: str, signature: str, body: tuple, callback: Optional[Callable] = None) -> None:
        from jeepney import new_method_call
        from jeepney.bus_messages import message_bus
        self._send(new_method_call(message_bus, member, signature, body), callback)

    def _register(self) -> None:
        from jeepney import DBusAddress, new_method_call
        watcher = DBusAddress(WATCHER_PATH, bus_name=WATCHER_NAME, interface=WATCHER_NAME)

        def done(reply) -> None:
            from jeepney import MessageType
            self._registered = reply.header.message_type == MessageType.method_return
            log.info("tray registered with the StatusNotifierWatcher: %s", self._registered)

        self._send(new_method_call(watcher, "RegisterStatusNotifierItem", "s", (self._bus_name,)), done)

    def _on_name_owner_changed(self, body: tuple) -> None:
        name, _old, new = body
        if name == WATCHER_NAME:
            if new:
                self._register()
            else:
                self._registered = False

    # ---- the loop
    def run(self) -> None:
        from jeepney import MessageType
        from jeepney.bus_messages import MatchRule
        from jeepney.io.blocking import open_dbus_connection

        self._conn = open_dbus_connection(bus="SESSION")
        self._started = time.monotonic()
        self._call_bus("RequestName", "su", (self._bus_name, 4))     # 4 = do not queue
        rule = MatchRule(type="signal", sender="org.freedesktop.DBus", interface="org.freedesktop.DBus",
                         member="NameOwnerChanged", path="/org/freedesktop/DBus")
        rule.add_arg_condition(0, WATCHER_NAME)
        self._call_bus("AddMatch", "s", (rule.serialise(),))
        self._call_bus("NameHasOwner", "s", (WATCHER_NAME,),
                       lambda reply: self._register() if reply.body and reply.body[0] else None)
        try:
            while not self._stop.is_set():
                self._drain_outbox()
                try:
                    message = self._conn.receive(timeout=0.2)
                except TimeoutError:
                    self._check_fallback()
                    continue
                self._dispatch(message, MessageType)
                self._check_fallback()
        finally:
            try:
                self._conn.close()
            except Exception:
                pass

    def _drain_outbox(self) -> None:
        while True:
            try:
                work = self._outbox.get_nowait()
            except queue.Empty:
                return
            try:
                work()
            except Exception:
                log.exception("tray update failed")

    def _check_fallback(self) -> None:
        """No watcher after the grace period: tell the application so it can show a window instead."""
        if (not self._registered and not self._fallback_fired and self.on_unavailable
                and time.monotonic() - self._started > NO_TRAY_GRACE_SECONDS):
            self._fallback_fired = True
            threading.Thread(target=self.on_unavailable, daemon=True).start()

    # ---- incoming messages
    def _dispatch(self, message, MessageType) -> None:
        from jeepney import HeaderFields
        kind = message.header.message_type
        fields = message.header.fields
        if kind in (MessageType.method_return, MessageType.error):
            callback = self._pending.pop(fields.get(HeaderFields.reply_serial, -1), None)
            if callback is not None:
                callback(message)
            return
        if kind == MessageType.signal:
            if fields.get(HeaderFields.member) == "NameOwnerChanged":
                self._on_name_owner_changed(message.body)
            return
        if kind != MessageType.method_call:
            return
        try:
            self._handle_call(message, fields, HeaderFields)
        except Exception:
            log.exception("D-Bus call failed")
            try:   # answer with an error so the caller does not wait for a timeout; never let this kill the loop
                from jeepney import new_error
                self._send(new_error(message, "org.freedesktop.DBus.Error.Failed", "s", ("internal error",)))
            except Exception:
                log.exception("could not send the D-Bus error reply")

    def _reply(self, message, signature: str = "", body: tuple = ()) -> None:
        from jeepney import new_method_return
        self._send(new_method_return(message, signature, body))

    def _handle_call(self, message, fields, HeaderFields) -> None:
        from jeepney import new_error
        path = fields.get(HeaderFields.path)
        interface = fields.get(HeaderFields.interface)
        member = fields.get(HeaderFields.member)
        body = message.body

        if interface == "org.freedesktop.DBus.Introspectable" and member == "Introspect":
            xml = INTROSPECTION_MENU if path == MENU_PATH else INTROSPECTION_ITEM
            return self._reply(message, "s", (xml,))
        if interface == "org.freedesktop.DBus.Peer":
            return self._reply(message, "s", ("",)) if member == "GetMachineId" else self._reply(message)

        if interface == "org.freedesktop.DBus.Properties":
            props = self._properties_for(path, body[0] if body else "")
            if member == "GetAll":
                return self._reply(message, "a{sv}", (props,))
            if member == "Get" and len(body) == 2 and body[1] in props:
                return self._reply(message, "v", (props[body[1]],))
            return self._send(new_error(message, "org.freedesktop.DBus.Error.UnknownProperty", "s", ("unknown",)))

        if path == ITEM_PATH and interface == SNI_INTERFACE:
            if member == "Activate":
                self._run_action(find_default(self.items))
            elif member == "SecondaryActivate":
                pass
            return self._reply(message)          # ContextMenu / Scroll: nothing to do, hosts render the menu

        if path == MENU_PATH and interface == MENU_INTERFACE:
            return self._handle_menu(message, member, body)

        self._send(new_error(message, "org.freedesktop.DBus.Error.UnknownMethod", "s", (f"unknown {member}",)))

    def _properties_for(self, path: str, interface: str) -> dict:
        if path == MENU_PATH:
            return {"Version": ("u", 3), "TextDirection": ("s", "ltr"), "Status": ("s", "normal"),
                    "IconThemePath": ("as", [])}
        return {"Category": ("s", "ApplicationStatus"), "Id": ("s", self.name), "Title": ("s", self.title),
                "Status": ("s", "Active"), "WindowId": ("u", 0), "IconName": ("s", ""), "IconThemePath": ("s", ""),
                "IconPixmap": ("a(iiay)", self._pixmaps), "OverlayIconName": ("s", ""),
                "OverlayIconPixmap": ("a(iiay)", []), "AttentionIconName": ("s", ""),
                "AttentionIconPixmap": ("a(iiay)", []), "AttentionMovieName": ("s", ""),
                "ToolTip": ("(sa(iiay)ss)", ("", [], self.title, "")),
                "ItemIsMenu": ("b", False), "Menu": ("o", MENU_PATH)}

    def _handle_menu(self, message, member: str, body: tuple) -> None:
        if member == "GetLayout":
            parent, depth = body[0], body[1]
            revision, node = self.model.layout(parent, depth)
            return self._reply(message, "u(ia{sv}av)", (revision, node))
        if member == "GetGroupProperties":
            return self._reply(message, "a(ia{sv})", (self.model.group_properties(list(body[0])),))
        if member == "GetProperty":
            item = self.model.item(body[0])
            value = self.model.properties(item).get(body[1]) if item else None
            return self._reply(message, "v", (value or ("s", ""),))
        if member == "AboutToShow":
            return self._reply(message, "b", (False,))
        if member == "AboutToShowGroup":
            return self._reply(message, "aiai", ([], []))
        if member == "Event":
            if body[1] == "clicked":
                self._run_action(self.model.item(body[0]))
            return self._reply(message)
        if member == "EventGroup":
            for item_id, event, _data, _time in body[0]:
                if event == "clicked":
                    self._run_action(self.model.item(item_id))
            return self._reply(message, "ai", ([],))
        from jeepney import new_error
        self._send(new_error(message, "org.freedesktop.DBus.Error.UnknownMethod", "s", (f"unknown {member}",)))

    def _run_action(self, item: Optional[Item]) -> None:
        """Runs a menu action off the bus thread (actions open windows or do network I/O)."""
        if item is None or item.action is None:
            return

        def work() -> None:
            try:
                item.action()
            except Exception:
                log.exception("menu action failed")
            self.refresh_menu()

        threading.Thread(target=work, daemon=True).start()
