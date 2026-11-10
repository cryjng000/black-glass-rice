"""Small reusable GTK widgets for the audio panel."""
import hashlib
import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

import icons

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "audio-panel"


# ---------------------------------------------------------------- helpers ---
def label(text="", css=None, xalign=0.0, max_chars=None):
    """Ellipsizing label.  By default it takes whatever width its container
    gives it (and never forces the panel wider); pass max_chars for labels
    that sit in a non-expanding container."""
    lbl = Gtk.Label(label=text)
    lbl.set_xalign(xalign)
    lbl.set_ellipsize(Pango.EllipsizeMode.END)
    if max_chars:
        lbl.set_max_width_chars(max_chars)
    else:
        lbl.set_width_chars(1)
        lbl.set_max_width_chars(1)
    if css:
        lbl.get_style_context().add_class(css)
    return lbl


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def plain_button(css, child=None):
    btn = Gtk.Button()
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.set_can_focus(False)
    btn.set_focus_on_click(False)
    for c in css.split():
        btn.get_style_context().add_class(c)
    if child is not None:
        btn.add(child)
    return btn


def icon_button(icon, css, size=18, tip=None):
    ico = Icon(icon, size)
    btn = plain_button(css, ico)
    btn.ico = ico
    if tip:
        btn.set_tooltip_text(tip)
    return btn


def slider(css=""):
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
    scale.set_draw_value(False)
    scale.set_hexpand(True)
    scale.set_size_request(-1, 22)
    scale.set_increments(2, 5)
    scale.set_can_focus(False)
    for c in css.split():
        scale.get_style_context().add_class(c)
    return scale


def set_class(widget, name, on):
    ctx = widget.get_style_context()
    (ctx.add_class if on else ctx.remove_class)(name)


# ------------------------------------------------------------------- icon ---
class Icon(Gtk.DrawingArea):
    """Cairo-drawn symbolic icon, coloured through CSS (`color`)."""

    TONES = ("dim", "accent")

    def __init__(self, glyph, size=18, tone=None):
        super().__init__()
        self.glyph = glyph
        self.size = size
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.get_style_context().add_class("ico")
        self.set_tone(tone)
        self.connect("draw", self._draw)
        self.connect("style-updated", lambda *_: self.queue_draw())

    def set_icon(self, glyph):
        if glyph != self.glyph:
            self.glyph = glyph
            self.queue_draw()

    def set_tone(self, tone):
        ctx = self.get_style_context()
        for t in self.TONES:
            ctx.remove_class(t)
        if tone:
            ctx.add_class(tone)
        self.queue_draw()

    def _draw(self, _w, cr):
        ctx = self.get_style_context()
        c = ctx.get_color(ctx.get_state())
        cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        alloc = self.get_allocation()
        cr.translate((alloc.width - self.size) / 2, (alloc.height - self.size) / 2)
        icons.draw(cr, self.glyph, self.size)
        return False


# -------------------------------------------------------------- album art ---
class Art(Gtk.DrawingArea):
    SCALE = 2  # render the pixbuf at 2x so it stays sharp on HiDPI

    def __init__(self, size=56):
        super().__init__()
        self.size = size
        self.pixbuf = None
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)
        self.get_style_context().add_class("art")
        self.connect("draw", self._draw)

    def set_pixbuf(self, pixbuf):
        self.pixbuf = pixbuf
        self.queue_draw()

    def _draw(self, _w, cr):
        s = self.size
        icons.rrect(cr, 0.5, 0.5, s - 1, s - 1, 10)
        if self.pixbuf:
            cr.save()
            cr.clip_preserve()
            cr.scale(1 / self.SCALE, 1 / self.SCALE)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
            cr.restore()
        else:
            ctx = self.get_style_context()
            c = ctx.get_color(ctx.get_state())
            cr.set_source_rgba(c.red, c.green, c.blue, 0.08)
            cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.10)  # thin glass edge, same as the bar
        cr.set_line_width(1)
        cr.stroke()
        if not self.pixbuf:
            ctx = self.get_style_context()
            c = ctx.get_color(ctx.get_state())
            cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
            cr.translate((s - 24) / 2, (s - 24) / 2)
            icons.draw(cr, "note", 24)
        return False


def _cover(pixbuf, size):
    k = Art.SCALE * size
    w, h = pixbuf.get_width(), pixbuf.get_height()
    ratio = max(k / w, k / h)
    scaled = pixbuf.scale_simple(max(k, int(w * ratio)), max(k, int(h * ratio)),
                                 GdkPixbuf.InterpType.BILINEAR)
    x, y = (scaled.get_width() - k) // 2, (scaled.get_height() - k) // 2
    return scaled.new_subpixbuf(x, y, k, k)


def load_art(url, size, done):
    """Load album art (file:// or http(s)://) and call done(pixbuf|None)
    on the main loop.  Remote art is cached in ~/.cache/audio-panel."""
    def finish(path):
        pixbuf = None
        if path:
            try:
                pixbuf = _cover(GdkPixbuf.Pixbuf.new_from_file(str(path)), size)
            except (GLib.Error, TypeError):
                pixbuf = None
        done(pixbuf)
        return False

    if url.startswith("file://"):
        GLib.idle_add(finish, urllib.parse.unquote(urllib.parse.urlparse(url).path))
    elif url.startswith(("http://", "https://")):
        def worker():
            path = CACHE / hashlib.sha1(url.encode()).hexdigest()
            if not path.exists():
                try:
                    CACHE.mkdir(parents=True, exist_ok=True)
                    with urllib.request.urlopen(url, timeout=6) as r:
                        data = r.read(4 * 1024 * 1024)
                    path.write_bytes(data)
                    _prune_cache()
                except (OSError, ValueError):
                    path = None
            GLib.idle_add(finish, path)

        threading.Thread(target=worker, daemon=True).start()
    else:
        GLib.idle_add(finish, None)


def _prune_cache(keep=60):
    try:
        files = sorted(CACHE.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[keep:]:
            old.unlink()
    except OSError:
        pass


# --------------------------------------------------------------- dropdown ---
class Dropdown(Gtk.Box):
    """Compact selector: a header showing the current device that expands
    inline into a list with an accent check next to the selected one."""

    def __init__(self, kind, on_select, on_toggle):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.kind, self.on_select, self.on_toggle = kind, on_select, on_toggle
        self._sig = None

        row = Gtk.Box(spacing=10)
        self.ico = Icon("speaker", 16, "dim")
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text.set_valign(Gtk.Align.CENTER)
        self.name = label("", "dd-name")
        self.sub = label("", "dd-sub")
        self.sub.set_no_show_all(True)
        text.pack_start(self.name, False, False, 0)
        text.pack_start(self.sub, False, False, 0)
        self.chev = Icon("chevron-down", 14, "dim")
        row.pack_start(self.ico, False, False, 0)
        row.pack_start(text, True, True, 0)
        row.pack_end(self.chev, False, False, 0)

        self.head = plain_button("dd", row)
        self.head.connect("clicked", lambda *_: self.on_toggle(self))

        self.rev = Gtk.Revealer()
        self.rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.rev.set_transition_duration(180)
        self.items = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.items.get_style_context().add_class("ddlist")
        self.rev.add(self.items)

        self.pack_start(self.head, False, False, 0)
        self.pack_start(self.rev, False, False, 0)

    @property
    def is_open(self):
        return self.rev.get_reveal_child()

    def set_open(self, opened, animate=True):
        if not animate:
            self.rev.set_transition_duration(0)
        self.rev.set_reveal_child(opened)
        if not animate:
            self.rev.set_transition_duration(180)
        self.chev.set_icon("chevron-up" if opened else "chevron-down")
        set_class(self.head, "open", opened)

    def set_current(self, text, icon="speaker", port="", enabled=True):
        self.name.set_text(text)
        self.name.set_tooltip_text(text)
        self.ico.set_icon(icon)
        self.sub.set_text(port)
        self.sub.set_visible(bool(port))
        self.head.set_sensitive(enabled)

    def set_items(self, devices, selected):
        sig = tuple((d["name"], d["desc"], d["icon"], d["name"] == selected) for d in devices)
        if sig == self._sig:
            return
        self._sig = sig
        for child in self.items.get_children():
            self.items.remove(child)
        if not devices:
            empty = label("No devices found", "item-name")
            empty.set_margin_start(10)
            empty.set_margin_top(6)
            self.items.pack_start(empty, False, False, 0)
        for dev in devices:
            chosen = dev["name"] == selected
            row = Gtk.Box(spacing=10)
            check = Icon("check", 14, "accent")
            check.set_opacity(1 if chosen else 0)
            row.pack_start(Icon(dev["icon"], 16, "dim"), False, False, 0)
            row.pack_start(label(dev["desc"], "item-name"), True, True, 0)
            row.pack_end(check, False, False, 0)
            btn = plain_button("item selected" if chosen else "item", row)
            btn.set_tooltip_text(dev["desc"])
            btn.connect("clicked", lambda _b, n=dev["name"]: self.on_select(self.kind, n))
            self.items.pack_start(btn, False, False, 0)
        self.items.show_all()
