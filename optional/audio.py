"""Audio backend for the panel: talks to PipeWire/PulseAudio through `pactl`.

`pactl` works on both native PulseAudio and PipeWire (pipewire-pulse), so a
single code path covers whatever is running.  Everything is asynchronous
(Gio.Subprocess), so the GTK main loop is never blocked, and state is kept in
sync by listening to `pactl subscribe` instead of polling.  The subscription
is only alive while the panel is open, so an idle panel costs nothing.

Requires `pactl -f json` (PulseAudio >= 16, or any recent pipewire-pulse).
"""
import json
import re
import shutil
import time

from gi.repository import Gio, GLib


def run(argv, callback=None):
    """Run a command without blocking.  callback(ok: bool, stdout: str)."""
    try:
        proc = Gio.Subprocess.new(
            argv, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
        )
    except GLib.Error:
        if callback:
            callback(False, "")
        return

    def done(p, res):
        try:
            _, out, _ = p.communicate_utf8_finish(res)
            ok = p.get_successful()
        except GLib.Error:
            out, ok = "", False
        if callback:
            callback(ok, out or "")

    proc.communicate_utf8_async(None, None, done)


def _guess_icon(kind, dev, port):
    """Pick a device icon from PulseAudio/PipeWire device properties."""
    if kind == "source":
        return "mic"
    props = dev.get("properties") or {}
    text = " ".join(
        str(x or "")
        for x in (dev.get("name"), dev.get("description"),
                  (port or {}).get("name"), (port or {}).get("description"))
    ).lower()
    form = (props.get("device.form_factor") or "").lower()
    if any(k in text for k in ("hdmi", "displayport", "display port")):
        return "monitor"
    if form in ("headphone", "headset", "hands-free", "handsfree") or any(
        k in text for k in ("headphone", "headset", "earbud", "airpods", "buds")
    ):
        return "headphones"
    if (props.get("device.bus") or "").lower() == "bluetooth" and form != "speaker":
        return "headphones"
    return "speaker"


def _parse_device(kind, dev):
    vols = [c.get("value", 0) for c in (dev.get("volume") or {}).values()]
    vol = round(max(vols) / 65536 * 100) if vols else 0
    ports = dev.get("ports") or []
    active = next((p for p in ports if p.get("name") == dev.get("active_port")), None)
    return {
        "name": dev.get("name", ""),
        "desc": dev.get("description") or dev.get("name", ""),
        "vol": vol,
        "mute": bool(dev.get("mute")),
        "icon": _guess_icon(kind, dev, active),
        # only worth showing when the card exposes several ports (jack vs speaker, ...)
        "port": (active or {}).get("description", "") if len(ports) > 1 else "",
        # a device whose every port is unplugged is effectively disconnected
        "gone": bool(ports) and all(p.get("availability") == "not available" for p in ports),
    }


def _visible(kind, devices, default):
    out = []
    for d in devices:
        if kind == "source" and d.get("monitor"):
            continue
        if d["gone"] and d["name"] != default:
            continue
        out.append(d)
    return out


class Audio:
    EVENT = re.compile(r"on (sink|source|server) ")

    def __init__(self, on_state):
        self.on_state = on_state
        self.running = False
        self.pipewire = None      # unknown until `pactl info` answers
        self._gen = 0
        self._refresh_id = 0
        self._vol_pending = {}
        self._vol_timer = {}
        self._proc = None
        self._cancel = None
        self._resub_id = 0

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self.running = True
        self.refresh()
        self._subscribe()
        if self.pipewire is None and shutil.which("pactl"):
            run(["pactl", "info"], self._on_info)

    def stop(self):
        self.running = False
        for source in (self._refresh_id, self._resub_id, *self._vol_timer.values()):
            if source:
                GLib.source_remove(source)
        self._refresh_id = self._resub_id = 0
        self._vol_timer.clear()
        self._vol_pending.clear()
        if self._cancel:
            self._cancel.cancel()
            self._cancel = None
        if self._proc:
            self._proc.force_exit()
            self._proc = None

    def _on_info(self, ok, out):
        m = re.search(r"^Server Name:\s*(.+)$", out, re.M)
        self.pipewire = bool(m and "pipewire" in m.group(1).lower())

    # ---------------------------------------------------------------- state
    def refresh(self):
        if not self.running:
            return
        if not shutil.which("pactl"):
            self.on_state({"ok": False, "error": "pactl not found"})
            return
        self._gen += 1
        gen = self._gen
        results = {}
        commands = {
            "sinks": ["pactl", "-f", "json", "list", "sinks"],
            "sources": ["pactl", "-f", "json", "list", "sources"],
            "dsink": ["pactl", "get-default-sink"],
            "dsource": ["pactl", "get-default-source"],
        }
        pending = [len(commands)]

        def make(key):
            def cb(ok, out):
                results[key] = (ok, out)
                pending[0] -= 1
                if pending[0] == 0 and gen == self._gen and self.running:
                    self._assemble(results)
            return cb

        for key, argv in commands.items():
            run(argv, make(key))

    def _assemble(self, results):
        try:
            if not (results["sinks"][0] and results["sources"][0]):
                raise ValueError("audio server unavailable")
            raw_sinks = json.loads(results["sinks"][1])
            raw_sources = json.loads(results["sources"][1])
        except (ValueError, KeyError):
            self.on_state({"ok": False, "error": "Audio server unavailable"})
            return
        default_sink = results["dsink"][1].strip()
        default_source = results["dsource"][1].strip()
        sinks = [_parse_device("sink", d) for d in raw_sinks]
        sources = []
        for raw in raw_sources:
            d = _parse_device("source", raw)
            props = raw.get("properties") or {}
            d["monitor"] = props.get("device.class") == "monitor" or d["name"].endswith(".monitor")
            sources.append(d)
        self.on_state({
            "ok": True,
            "default": {"sink": default_sink, "source": default_source},
            "devices": {
                "sink": _visible("sink", sinks, default_sink),
                "source": _visible("source", sources, default_source),
            },
        })

    def _queue_refresh(self):
        if self._refresh_id:
            return

        def fire():
            self._refresh_id = 0
            self.refresh()
            return False

        self._refresh_id = GLib.timeout_add(80, fire)

    # --------------------------------------------------------- subscription
    def _subscribe(self):
        if not shutil.which("pactl"):
            return
        try:
            self._proc = Gio.Subprocess.new(
                ["pactl", "subscribe"],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE,
            )
        except GLib.Error:
            return
        self._cancel = Gio.Cancellable()
        self._stream = Gio.DataInputStream.new(self._proc.get_stdout_pipe())
        self._read_line()

    def _read_line(self):
        self._stream.read_line_async(GLib.PRIORITY_DEFAULT, self._cancel, self._on_line)

    def _on_line(self, stream, res):
        try:
            line, _ = stream.read_line_finish_utf8(res)
        except GLib.Error:
            return  # cancelled
        if line is None:
            # pactl exited (audio server restart?) - try to reattach shortly
            self._proc = None
            if self.running:
                self._resub_id = GLib.timeout_add_seconds(2, self._resubscribe)
            return
        if self.EVENT.search(line):
            self._queue_refresh()
        self._read_line()

    def _resubscribe(self):
        self._resub_id = 0
        if self.running:
            self._subscribe()
            self.refresh()
        return False

    # -------------------------------------------------------------- actions
    @staticmethod
    def _default(kind):
        return "@DEFAULT_%s@" % kind.upper()

    def set_volume(self, kind, pct):
        """Throttled: dragging a slider sends at most ~25 updates a second."""
        self._vol_pending[kind] = pct
        if kind in self._vol_timer:
            return

        def flush():
            self._vol_timer.pop(kind, None)
            value = self._vol_pending.pop(kind, None)
            if value is not None:
                run(["pactl", "set-%s-volume" % kind, self._default(kind), "%d%%" % value])
            return False

        self._vol_timer[kind] = GLib.timeout_add(40, flush)

    def toggle_mute(self, kind):
        run(["pactl", "set-%s-mute" % kind, self._default(kind), "toggle"])

    def set_default(self, kind, name):
        def after(ok, _out):
            if ok and kind == "sink" and self.pipewire is False:
                self._move_streams(name)
            self.refresh()

        run(["pactl", "set-default-%s" % kind, name], after)

    def _move_streams(self, sink):
        """Native PulseAudio does not move running streams when the default
        changes (PipeWire/WirePlumber does), so do it by hand there."""
        def moved(ok, out):
            for line in out.splitlines():
                sid = line.split("\t", 1)[0]
                if sid.isdigit():
                    run(["pactl", "move-sink-input", sid, sink])

        run(["pactl", "list", "short", "sink-inputs"], moved)
