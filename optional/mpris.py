"""MPRIS client: talks to media players (Firefox, Spotify, VLC, ...) over D-Bus.

No playerctl dependency: players are discovered through the session bus and
tracked with Gio.DBusProxy, so updates are signal driven.  The only timer is a
1 s position tick that runs while something is playing and the panel is open.
"""
from gi.repository import Gio, GLib

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
IFACE_PLAYER = PREFIX + "Player"
IFACE_ROOT = PREFIX.rstrip(".")
PROPS = "org.freedesktop.DBus.Properties"


def _noop(*_a):
    pass


class _Player:
    def __init__(self, media, name):
        self.media = media
        self.name = name
        self.proxy = None
        self.identity = ""
        self.position = 0.0
        Gio.DBusProxy.new(
            media.bus, Gio.DBusProxyFlags.NONE, None,
            name, PATH, IFACE_PLAYER, None, self._ready,
        )

    def _ready(self, _src, res):
        try:
            self.proxy = Gio.DBusProxy.new_finish(res)
        except GLib.Error:
            self.media.drop(self.name)
            return
        self.proxy.connect("g-properties-changed", lambda *_: self.media.changed(poll=True))
        self.proxy.connect("g-signal", self._on_signal)
        self.media.bus.call(
            self.name, PATH, PROPS, "Get",
            GLib.Variant("(ss)", (IFACE_ROOT, "Identity")), GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE, 1000, None, self._identity,
        )
        self.media.changed(poll=True)

    def _identity(self, conn, res):
        try:
            self.identity = conn.call_finish(res).unpack()[0]
        except GLib.Error:
            self.identity = self.name[len(PREFIX):].split(".")[0].title()
        self.media.changed()

    def _on_signal(self, _proxy, _sender, signal, _params):
        if signal == "Seeked":
            self.media.poll_position()

    def prop(self, key, default=None):
        value = self.proxy.get_cached_property(key) if self.proxy else None
        return default if value is None else value.unpack()

    @property
    def status(self):
        return self.prop("PlaybackStatus", "Stopped")

    @property
    def metadata(self):
        return self.prop("Metadata", {}) or {}

    @property
    def title(self):
        return str(self.metadata.get("xesam:title") or "")

    @property
    def is_candidate(self):
        return self.proxy is not None and (self.status in ("Playing", "Paused") or bool(self.title))

    def call(self, method, params=None):
        if self.proxy:
            self.proxy.call(method, params, Gio.DBusCallFlags.NONE, 2000, None, _noop)


class Media:
    def __init__(self, on_change):
        self.on_change = on_change
        self.bus = None
        self.players = {}
        self.current = None
        self.pinned = False
        self._sub = 0
        self._emit_id = 0
        self._tick_id = 0
        self.running = False

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self.running = True
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            self.on_change(None)
            return
        self._sub = self.bus.signal_subscribe(
            "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
            "/org/freedesktop/DBus", None, Gio.DBusSignalFlags.NONE, self._owner_changed,
        )
        self.bus.call(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "ListNames", None, GLib.VariantType("(as)"),
            Gio.DBusCallFlags.NONE, 2000, None, self._names,
        )

    def stop(self):
        self.running = False
        for source in (self._emit_id, self._tick_id):
            if source:
                GLib.source_remove(source)
        self._emit_id = self._tick_id = 0
        if self.bus and self._sub:
            self.bus.signal_unsubscribe(self._sub)
        self._sub = 0
        self.players.clear()
        self.current = None
        self.pinned = False

    # ------------------------------------------------------------ discovery
    def _names(self, conn, res):
        try:
            names = conn.call_finish(res).unpack()[0]
        except GLib.Error:
            names = []
        for name in names:
            self.add(name)
        self.changed()

    def _owner_changed(self, _c, _s, _p, _i, _sig, params, *_):
        name, old, new = params.unpack()
        if not name.startswith(PREFIX):
            return
        if new:
            self.add(name)
        else:
            self.drop(name)

    def add(self, name):
        if self.running and name.startswith(PREFIX) and name not in self.players:
            self.players[name] = _Player(self, name)

    def drop(self, name):
        self.players.pop(name, None)
        if self.current == name:
            self.current, self.pinned = None, False
        self.changed()

    # ---------------------------------------------------------------- state
    def _candidates(self):
        return sorted((p for p in self.players.values() if p.is_candidate), key=lambda p: p.name)

    def _pick(self):
        cands = self._candidates()
        cur = self.players.get(self.current)
        playing = [p for p in cands if p.status == "Playing"]
        if cur in cands and (self.pinned or cur.status == "Playing"):
            return cur, len(cands)
        if playing:
            return playing[0], len(cands)
        if cur in cands:
            return cur, len(cands)
        return (cands[0] if cands else None), len(cands)

    def changed(self, poll=False):
        if not self.running:
            return
        if poll:
            self.poll_position()
        if not self._emit_id:
            self._emit_id = GLib.timeout_add(40, self._emit)

    def _emit(self):
        self._emit_id = 0
        if not self.running:
            return False
        player, count = self._pick()
        self.current = player.name if player else None
        if player is None:
            self.on_change(None)
        else:
            md = player.metadata
            artist = md.get("xesam:artist") or ""
            if isinstance(artist, (list, tuple)):
                artist = ", ".join(str(a) for a in artist)
            try:
                length = float(md.get("mpris:length") or 0) / 1e6
            except (TypeError, ValueError):
                length = 0.0
            self.on_change({
                "player": player.identity or player.name[len(PREFIX):],
                "count": count,
                "status": player.status,
                "title": player.title,
                "artist": str(artist),
                "art": str(md.get("mpris:artUrl") or ""),
                "length": length,
                "position": player.position,
                "can_prev": bool(player.prop("CanGoPrevious", True)),
                "can_next": bool(player.prop("CanGoNext", True)),
                "can_seek": bool(player.prop("CanSeek", False)),
            })
        self._sync_tick(player is not None and player.status == "Playing")
        return False

    # ------------------------------------------------------------- position
    def _sync_tick(self, playing):
        if playing and not self._tick_id:
            self._tick_id = GLib.timeout_add_seconds(1, self._tick)
        elif not playing and self._tick_id:
            GLib.source_remove(self._tick_id)
            self._tick_id = 0

    def _tick(self):
        if not self.running:
            self._tick_id = 0
            return False
        self.poll_position()
        return True

    def poll_position(self):
        player = self.players.get(self.current)
        if not (self.bus and player and player.proxy):
            return

        def got(conn, res, name=player.name):
            try:
                pos = conn.call_finish(res).unpack()[0]
            except GLib.Error:
                return
            p = self.players.get(name)
            if p and self.running:
                p.position = float(pos) / 1e6
                self.changed()

        self.bus.call(
            player.name, PATH, PROPS, "Get",
            GLib.Variant("(ss)", (IFACE_PLAYER, "Position")), GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE, 1000, None, got,
        )

    # -------------------------------------------------------------- actions
    def control(self, method):
        player = self.players.get(self.current)
        if player:
            player.call(method)

    def seek(self, seconds):
        player = self.players.get(self.current)
        if not player:
            return
        previous, player.position = player.position, seconds
        target = int(seconds * 1e6)
        track = player.metadata.get("mpris:trackid")
        try:
            if track:
                player.call("SetPosition", GLib.Variant("(ox)", (str(track), target)))
                return
        except (TypeError, ValueError):
            pass
        player.call("Seek", GLib.Variant("(x)", (target - int(previous * 1e6),)))

    def cycle(self):
        """Switch to the next available player (when several are open)."""
        cands = self._candidates()
        if len(cands) < 2:
            return
        names = [p.name for p in cands]
        idx = names.index(self.current) if self.current in names else -1
        self.current = names[(idx + 1) % len(names)]
        self.pinned = True
        self.poll_position()
        self.changed()
