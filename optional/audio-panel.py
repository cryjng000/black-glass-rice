#!/usr/bin/env python3
"""audio-panel: a glass audio control centre for Waybar (Hyprland / Wayland).

A single long-lived instance owns the popup.  `toggle.sh` (or
`audio-panel.py toggle|show|hide`) talks to it over D-Bus, so there is only
ever one panel.  While hidden it uses no CPU: the audio and MPRIS listeners
are attached when the panel opens and detached when it closes.
"""
import ctypes.util
import os
import sys


def _preload_layer_shell():
    """gtk-layer-shell has to be loaded before libwayland-client, which
    Python cannot guarantee - so re-exec once with LD_PRELOAD."""
    if os.environ.get("AUDIO_PANEL_PRELOADED"):
        return
    lib = ctypes.util.find_library("gtk-layer-shell")
    if not lib:
        return
    os.environ["AUDIO_PANEL_PRELOADED"] = "1"
    os.environ["LD_PRELOAD"] = (lib + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable] + sys.argv)


_preload_layer_shell()

import json
import signal
import subprocess
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell as LS
except (ValueError, ImportError):
    LS = None
from gi.repository import Gdk, Gio, GLib, Gtk

os.environ.pop("LD_PRELOAD", None)  # don't leak the preload into pactl/hyprctl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import widgets as W
from audio import Audio, run
from mpris import Media

APP_ID = "dev.local.AudioPanel"

# ---- geometry (logical px) -------------------------------------------------
WIDTH = 340                 # visible panel width
PAD = 14                    # transparent room around the panel for its shadow
BAR_BOTTOM = 8 + 40 + 6     # Waybar margin-top + height (config.jsonc) + gap
EDGE_GAP = 12               # keep this far from the screen edge (bar margin)

DEFAULT_COLORS = """
@define-color ap_panel  rgba(18, 18, 20, 0.68);
@define-color ap_edge   rgba(255, 255, 255, 0.10);
@define-color ap_text   #f2f2f2;
@define-color ap_dim    #9a9a9a;
@define-color ap_muted  #8a8a8a;
@define-color ap_hover  rgba(255, 255, 255, 0.08);
@define-color ap_trough rgba(255, 255, 255, 0.12);
@define-color ap_accent #e6e6e6;
"""


# ----------------------------------------------------------------- hyprland --
def hypr_context(callback):
    """Where is the cursor and on which monitor?  Used to open the panel right
    under the Waybar module that was clicked.  callback(dict | None)."""
    def got_cursor(ok, out):
        try:
            c = json.loads(out)
            cx, cy = float(c["x"]), float(c["y"])
        except (ValueError, KeyError, TypeError):
            callback(None)
            return

        def got_monitors(ok2, out2):
            try:
                monitors = json.loads(out2)
            except ValueError:
                callback(None)
                return
            for m in monitors:
                w, h = m["width"] / m["scale"], m["height"] / m["scale"]
                if m.get("transform", 0) in (1, 3, 5, 7):
                    w, h = h, w
                if m["x"] <= cx < m["x"] + w and m["y"] <= cy < m["y"] + h:
                    callback({"cx": cx, "cy": cy, "mx": m["x"], "my": m["y"], "mw": w, "mh": h})
                    return
            callback(None)

        run(["hyprctl", "-j", "monitors"], got_monitors)

    run(["hyprctl", "cursorpos", "-j"], got_cursor)


def read_text(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


# -------------------------------------------------------------------- panel --
class Panel:
    def __init__(self):
        self.visible = self.opening = False
        self.catchers = []
        self.state = None
        self.info = None
        self.art_url = None
        self.hold = {"sink": 0.0, "source": 0.0, "seek": 0.0}
        self._seek_id = 0
        self.provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), self.provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self._build()
        self.audio = Audio(self.on_audio)
        self.media = Media(self.on_media)

    # ------------------------------------------------------------- building
    def _layer_window(self, namespace, layer):
        win = Gtk.Window()
        win.set_decorated(False)
        win.set_skip_taskbar_hint(True)
        win.set_app_paintable(True)
        visual = Gdk.Screen.get_default().get_rgba_visual()
        if visual:
            win.set_visual(visual)
        LS.init_for_window(win)
        LS.set_namespace(win, namespace)
        LS.set_layer(win, layer)
        return win

    @staticmethod
    def _keyboard(win, exclusive):
        try:
            LS.set_keyboard_mode(win, LS.KeyboardMode.EXCLUSIVE if exclusive else LS.KeyboardMode.NONE)
        except AttributeError:  # gtk-layer-shell < 0.6
            LS.set_keyboard_interactivity(win, exclusive)

    def _build(self):
        win = self.win = self._layer_window("audio-panel", LS.Layer.OVERLAY)
        win.get_style_context().add_class("ap-window")
        self._keyboard(win, True)
        win.connect("key-press-event", self._on_key)
        win.connect("delete-event", lambda *_: (self.hide(), True)[1])

        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.panel.get_style_context().add_class("panel")
        self.panel.set_size_request(WIDTH, -1)
        self.panel.set_margin_bottom(PAD)
        win.add(self.panel)

        self.panel.pack_start(self._build_media(), False, False, 0)
        self.panel.pack_start(self._sep(), False, False, 0)
        out_box, self.sec_sink = self._build_section("sink")
        self.panel.pack_start(out_box, False, False, 0)
        self.panel.pack_start(self._sep(), False, False, 0)
        in_box, self.sec_source = self._build_section("source")
        self.panel.pack_start(in_box, False, False, 0)

    @staticmethod
    def _sep():
        sep = Gtk.Box()
        sep.set_size_request(-1, 1)
        sep.get_style_context().add_class("sep")
        return sep

    def _build_media(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.stack.set_vhomogeneous(False)

        idle = Gtk.Box(spacing=10)
        idle.get_style_context().add_class("idle")
        idle.set_halign(Gtk.Align.CENTER)
        idle.pack_start(W.Icon("note", 18, "dim"), False, False, 0)
        idle.pack_start(W.label("Nothing playing", "sub", max_chars=30), False, False, 0)
        self.stack.add_named(idle, "idle")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        top = Gtk.Box(spacing=12)
        self.art = W.Art(56)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_valign(Gtk.Align.CENTER)
        self.title = W.label("", "title")
        self.artist = W.label("", "sub")
        chip_row = Gtk.Box(spacing=6)
        self.dot = Gtk.Box()
        self.dot.set_size_request(6, 6)
        self.dot.set_valign(Gtk.Align.CENTER)
        self.dot.get_style_context().add_class("dot")
        self.chip_label = W.label("", "chip-label", max_chars=26)
        chip_row.pack_start(self.dot, False, False, 0)
        chip_row.pack_start(self.chip_label, True, True, 0)
        self.chip = W.plain_button("chip", chip_row)
        self.chip.set_halign(Gtk.Align.START)
        self.chip.connect("clicked", lambda *_: self.media.cycle())
        for w in (self.title, self.artist, self.chip):
            text.pack_start(w, False, False, 0)
        top.pack_start(self.art, False, False, 0)
        top.pack_start(text, True, True, 0)

        self.prog = W.slider("progress")
        self.prog.connect("change-value", self._on_seek)
        times = Gtk.Box()
        self.t_cur = W.label("0:00", "time")
        self.t_tot = W.label("", "time", xalign=1.0)
        times.pack_start(self.t_cur, True, True, 0)
        times.pack_start(self.t_tot, True, True, 0)

        ctl = Gtk.Box(spacing=8)
        ctl.set_halign(Gtk.Align.CENTER)
        self.btn_prev = W.icon_button("prev", "ctl", 18, "Previous")
        self.btn_play = W.icon_button("play", "ctl main", 20, "Play / Pause")
        self.btn_next = W.icon_button("next", "ctl", 18, "Next")
        self.btn_prev.connect("clicked", lambda *_: self.media.control("Previous"))
        self.btn_play.connect("clicked", lambda *_: self.media.control("PlayPause"))
        self.btn_next.connect("clicked", lambda *_: self.media.control("Next"))
        for b in (self.btn_prev, self.btn_play, self.btn_next):
            ctl.pack_start(b, False, False, 0)

        for w in (top, self.prog, times, ctl):
            box.pack_start(w, False, False, 0)
        self.stack.add_named(box, "player")
        self.stack.set_visible_child_name("idle")

        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrap.get_style_context().add_class("media")
        wrap.pack_start(self.stack, False, False, 0)
        return wrap

    def _build_section(self, kind):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("section")
        row = Gtk.Box(spacing=8)
        btn = W.icon_button("volume-2" if kind == "sink" else "mic", "iconbtn", 18)
        scale = W.slider("vol")
        pct = W.label("", "pct", xalign=1.0)
        pct.set_width_chars(5)
        pct.set_max_width_chars(5)
        pct.set_hexpand(False)
        btn.connect("clicked", lambda *_: self._toggle_mute(kind))
        scale.connect("change-value", self._on_volume, kind)
        row.pack_start(btn, False, False, 0)
        row.pack_start(scale, True, True, 0)
        row.pack_start(pct, False, False, 0)
        dd = W.Dropdown(kind, self._select_device, self._toggle_dropdown)
        box.pack_start(row, False, False, 0)
        box.pack_start(dd, False, False, 0)
        return box, {"btn": btn, "scale": scale, "pct": pct, "dd": dd}

    # ------------------------------------------------------------ show/hide
    def toggle(self):
        self.hide() if (self.visible or self.opening) else self.show()

    def show(self):
        if self.visible or self.opening:
            return
        self.opening = True
        hypr_context(self._show_at)

    def hide(self):
        self.opening = False
        if not self.visible:
            return
        self.visible = False
        self.audio.stop()
        self.media.stop()
        if self._seek_id:
            GLib.source_remove(self._seek_id)
            self._seek_id = 0
        self.win.hide()
        for c in self.catchers:
            c.destroy()
        self.catchers = []
        for sec in (self.sec_sink, self.sec_source):
            sec["dd"].set_open(False, animate=False)

    def _show_at(self, ctx):
        if not self.opening:
            return
        self.opening = False
        self.visible = True
        self._reload_css()
        self._place(ctx)
        self._make_catchers()
        self.win.show_all()
        self.info = None
        self.state = None
        self.apply_media(None)
        self.audio.start()
        self.media.start()

    def _place(self, ctx):
        """Centre under the clicked bar module (cursor), else right-align."""
        from_bar = ctx is not None and ctx["cy"] - ctx["my"] <= 90
        left = None
        if ctx:
            left = ctx["cx"] - ctx["mx"] - WIDTH / 2 if from_bar else ctx["mw"] - WIDTH - EDGE_GAP
            left = int(max(EDGE_GAP, min(left, ctx["mw"] - WIDTH - EDGE_GAP)))
        LS.set_anchor(self.win, LS.Edge.TOP, True)
        LS.set_anchor(self.win, LS.Edge.LEFT, left is not None)
        LS.set_anchor(self.win, LS.Edge.RIGHT, left is None)
        top = max(0, BAR_BOTTOM - PAD)
        LS.set_margin(self.win, LS.Edge.TOP, top)
        self.panel.set_margin_top(BAR_BOTTOM - top)
        side = left if left is not None else EDGE_GAP
        outer = max(0, side - PAD)
        LS.set_margin(self.win, LS.Edge.LEFT, outer if left is not None else 0)
        LS.set_margin(self.win, LS.Edge.RIGHT, outer if left is None else 0)
        self.panel.set_margin_start(side - outer if left is not None else PAD)
        self.panel.set_margin_end(side - outer if left is None else PAD)
        LS.set_monitor(self.win, self._gdk_monitor(ctx))

    @staticmethod
    def _gdk_monitor(ctx):
        if not ctx:
            return None
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            mon = display.get_monitor(i)
            geo = mon.get_geometry()
            if abs(geo.x - ctx["mx"]) < 2 and abs(geo.y - ctx["my"]) < 2:
                return mon
        return None

    def _make_catchers(self):
        """Invisible full-screen layers: a click anywhere outside the panel
        (including on the bar, so clicking the icon again) dismisses it."""
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            win = self._layer_window("audio-panel-catcher", LS.Layer.TOP)
            win.get_style_context().add_class("ap-catcher")
            LS.set_monitor(win, display.get_monitor(i))
            for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
                LS.set_anchor(win, edge, True)
            LS.set_exclusive_zone(win, -1)
            self._keyboard(win, False)
            win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            win.connect("button-press-event", lambda *_: GLib.idle_add(self.hide) and False)
            win.show_all()
            self.catchers.append(win)

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _reload_css(self):
        """Re-read on every open, so edits and new Matugen colours apply live."""
        colors = os.environ.get("AUDIO_PANEL_COLORS", str(HERE / "colors.css"))
        main = read_text(HERE / "audio-panel.css")
        for parts in ((DEFAULT_COLORS, read_text(colors), main), (DEFAULT_COLORS, main)):
            try:
                self.provider.load_from_data("\n".join(parts).encode())
                return
            except GLib.Error as err:
                print("audio-panel: CSS error:", err.message, file=sys.stderr)

    def _shrink_later(self):
        def shrink():
            if self.visible:
                self.win.resize(WIDTH + 2 * PAD, 1)
            return False

        GLib.timeout_add(240, shrink)

    # ------------------------------------------------------------ media UI
    def on_media(self, info):
        if self.visible:
            self.apply_media(info)

    def apply_media(self, info):
        self.info = info
        if not info:
            self.stack.set_visible_child_name("idle")
            return
        self.stack.set_visible_child_name("player")
        playing = info["status"] == "Playing"
        self.title.set_text(info["title"] or "Unknown track")
        self.title.set_tooltip_text(info["title"])
        self.artist.set_text(info["artist"] or " ")
        self.chip_label.set_text(info["player"] + ("  \u00b7  switch" if info["count"] > 1 else ""))
        self.chip.set_sensitive(info["count"] > 1)
        W.set_class(self.dot, "on", playing)
        self.btn_play.ico.set_icon("pause" if playing else "play")
        W.set_class(self.btn_play, "playing", playing)
        self.btn_prev.set_sensitive(info["can_prev"])
        self.btn_next.set_sensitive(info["can_next"])

        length = info["length"]
        self.prog.set_sensitive(length > 0 and info["can_seek"])
        self.t_tot.set_text(W.fmt_time(length) if length > 0 else "")
        if time.monotonic() > self.hold["seek"]:
            self.prog.set_range(0, max(length, 1))
            self.prog.set_value(min(info["position"], max(length, 1)))
            self.t_cur.set_text(W.fmt_time(info["position"]))

        if info["art"] != self.art_url:
            self.art_url = info["art"]
            self.art.set_pixbuf(None)
            url = self.art_url
            W.load_art(url, 56, lambda pb, u=url: self.art.set_pixbuf(pb) if u == self.art_url else None)

    def _on_seek(self, _scale, _scroll, value):
        value = max(0.0, value)
        self.hold["seek"] = time.monotonic() + 0.6
        self.t_cur.set_text(W.fmt_time(value))
        if not self._seek_id:
            def send():
                self._seek_id = 0
                self.media.seek(self.prog.get_value())
                return False

            self._seek_id = GLib.timeout_add(120, send)
        return False

    # ------------------------------------------------------------ audio UI
    def on_audio(self, state):
        self.state = state
        if self.visible:
            self.apply_audio()

    def _current(self, kind):
        st = self.state
        if not st or not st.get("ok"):
            return None
        name = st["default"][kind]
        return next((d for d in st["devices"][kind] if d["name"] == name), None)

    def apply_audio(self):
        st = self.state
        ok = bool(st and st.get("ok"))
        for kind, sec in (("sink", self.sec_sink), ("source", self.sec_source)):
            dev = self._current(kind)
            usable = ok and dev is not None
            sec["btn"].set_sensitive(usable)
            sec["scale"].set_sensitive(usable)
            dd = sec["dd"]
            if not ok:
                dd.set_current((st or {}).get("error", "Connecting\u2026"), "speaker" if kind == "sink" else "mic", enabled=False)
                sec["pct"].set_text("")
                continue
            dd.set_items(st["devices"][kind], st["default"][kind])
            if dev is None:
                dd.set_current("No device", "speaker" if kind == "sink" else "mic", enabled=bool(st["devices"][kind]))
                sec["pct"].set_text("")
                continue
            dd.set_current(dev["desc"], dev["icon"], dev["port"])
            muted = dev["mute"]
            if kind == "sink":
                glyph = "volume-x" if muted else "volume-0" if dev["vol"] == 0 else "volume-1" if dev["vol"] < 34 else "volume-2"
                sec["btn"].ico.set_tone("dim" if muted else None)
            else:
                glyph = "mic-off" if muted else "mic"
                sec["btn"].ico.set_tone("accent" if muted else None)  # muted mic stays noticeable
            sec["btn"].ico.set_icon(glyph)
            sec["btn"].set_tooltip_text("Unmute" if muted else "Mute")
            sec["pct"].set_text("muted" if muted else "%d%%" % dev["vol"])
            W.set_class(sec["scale"], "muted", muted)
            if time.monotonic() > self.hold[kind]:
                sec["scale"].set_value(min(dev["vol"], 100))

    def _on_volume(self, _scale, _scroll, value, kind):
        pct = int(round(max(0, min(100, value))))
        self.hold[kind] = time.monotonic() + 0.45
        sec = self.sec_sink if kind == "sink" else self.sec_source
        dev = self._current(kind)
        if dev:
            dev["vol"] = pct
            sec["pct"].set_text("muted" if dev["mute"] else "%d%%" % pct)
        self.audio.set_volume(kind, pct)
        return False

    def _toggle_mute(self, kind):
        dev = self._current(kind)
        if dev:
            dev["mute"] = not dev["mute"]  # optimistic; the server event confirms
            self.hold[kind] = 0.0
            self.apply_audio()
        self.audio.toggle_mute(kind)

    def _toggle_dropdown(self, dd):
        opening = not dd.is_open
        for sec in (self.sec_sink, self.sec_source):
            if sec["dd"] is not dd:
                sec["dd"].set_open(False)
        dd.set_open(opening)
        self._shrink_later()

    def _select_device(self, kind, name):
        self.audio.set_default(kind, name)
        sec = self.sec_sink if kind == "sink" else self.sec_source
        sec["dd"].set_open(False)
        self._shrink_later()


# ---------------------------------------------------------------------- app --
class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.panel = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # stay alive while the popup is hidden
        self.panel = Panel()
        for name in ("toggle", "show", "hide"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, n=name: self.dispatch(n))
            self.add_action(action)

    def dispatch(self, cmd):
        if cmd == "toggle":
            self.panel.toggle()
        elif cmd == "show":
            self.panel.show()
        elif cmd == "hide":
            self.panel.hide()
        # "daemon" / anything else: just make sure the instance is running

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        self.dispatch(args[0] if args else "toggle")
        return 0


def main():
    if LS is None:
        msg = "audio-panel: gtk-layer-shell (GtkLayerShell typelib) is not installed"
        print(msg, file=sys.stderr)
        subprocess.run(["notify-send", "-u", "critical", "Audio panel", msg], check=False)
        return 1
    app = App()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (app.quit(), False)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (app.quit(), False)[1])
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
