"""Symbolic icon set for the audio panel, drawn with cairo.

Every icon lives on a 24x24 grid, uses the same stroke weight, round caps and
round joins, so the whole set stays visually consistent.  The icons are
recoloured by CSS (the colour is taken from the widget's `color` property), so
they follow the Matugen palette automatically.

This module has no GTK dependency: `draw(cr, name, size)` only needs a cairo
context, which makes it easy to test or reuse.
"""
import math

STROKE = 1.8  # in 24-unit grid coordinates


def _poly(cr, pts, close=False):
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    if close:
        cr.close_path()


def rrect(cr, x, y, w, h, r):
    """Rounded-rectangle path (also used by the album-art widget)."""
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _fill_stroke(cr):
    cr.fill_preserve()
    cr.stroke()


# ---------------------------------------------------------------- volume ----
_SPEAKER = [(3, 9.5), (7, 9.5), (11.5, 5.5), (11.5, 18.5), (7, 14.5), (3, 14.5)]


def _speaker(cr, waves=0, muted=False):
    _poly(cr, _SPEAKER, True)
    cr.stroke()
    for radius in (4.5, 8.0)[:waves]:
        cr.new_sub_path()
        cr.arc(11.5, 12, radius, -0.72, 0.72)
        cr.stroke()
    if muted:
        _poly(cr, [(15.5, 9.5), (21, 15)])
        cr.stroke()
        _poly(cr, [(21, 9.5), (15.5, 15)])
        cr.stroke()


# ------------------------------------------------------------ microphone ----
def _mic(cr, muted=False):
    cr.new_sub_path()
    cr.arc(12, 6.5, 3, math.pi, 0)
    cr.arc(12, 11, 3, 0, math.pi)
    cr.close_path()
    cr.stroke()
    cr.new_sub_path()
    cr.arc(12, 11, 6.5, 0, math.pi)
    cr.stroke()
    _poly(cr, [(12, 17.5), (12, 21)])
    cr.stroke()
    _poly(cr, [(8.5, 21), (15.5, 21)])
    cr.stroke()
    if muted:
        _poly(cr, [(4.5, 3.5), (19.5, 20.5)])
        cr.stroke()


# ----------------------------------------------------------------- media ----
def _play(cr):
    _poly(cr, [(8, 5.5), (18.5, 12), (8, 18.5)], True)
    _fill_stroke(cr)


def _pause(cr):
    cr.set_line_width(3.4)
    _poly(cr, [(8.75, 7), (8.75, 17)])
    cr.stroke()
    _poly(cr, [(15.25, 7), (15.25, 17)])
    cr.stroke()


def _prev(cr):
    _poly(cr, [(6.5, 6), (6.5, 18)])
    cr.stroke()
    _poly(cr, [(18, 5.5), (18, 18.5), (9.5, 12)], True)
    _fill_stroke(cr)


def _next(cr):
    _poly(cr, [(17.5, 6), (17.5, 18)])
    cr.stroke()
    _poly(cr, [(6, 5.5), (6, 18.5), (14.5, 12)], True)
    _fill_stroke(cr)


def _note(cr):
    cr.new_sub_path()
    cr.arc(8, 17.5, 2.8, 0, 2 * math.pi)
    cr.stroke()
    _poly(cr, [(10.8, 17.5), (10.8, 5)])
    cr.stroke()
    cr.move_to(10.8, 5)
    cr.curve_to(13.5, 5.5, 17, 6.5, 17.5, 10.5)
    cr.stroke()


# --------------------------------------------------------------- devices ----
def _headphones(cr):
    cr.new_sub_path()
    cr.arc(12, 13, 7.5, math.pi, 2 * math.pi)
    cr.stroke()
    rrect(cr, 3.5, 13, 4, 6.5, 1.6)
    cr.stroke()
    rrect(cr, 16.5, 13, 4, 6.5, 1.6)
    cr.stroke()


def _monitor(cr):
    rrect(cr, 3, 4.5, 18, 12, 2)
    cr.stroke()
    _poly(cr, [(12, 16.5), (12, 19.5)])
    cr.stroke()
    _poly(cr, [(8, 19.5), (16, 19.5)])
    cr.stroke()


# ---------------------------------------------------------------- status ----
def _check(cr):
    _poly(cr, [(5, 12.5), (10, 17.5), (19, 7)])
    cr.stroke()


def _chevron_down(cr):
    _poly(cr, [(6.5, 9.5), (12, 15), (17.5, 9.5)])
    cr.stroke()


def _chevron_up(cr):
    _poly(cr, [(6.5, 14.5), (12, 9), (17.5, 14.5)])
    cr.stroke()


ICONS = {
    "volume-0": lambda cr: _speaker(cr, 0),
    "volume-1": lambda cr: _speaker(cr, 1),
    "volume-2": lambda cr: _speaker(cr, 2),
    "volume-x": lambda cr: _speaker(cr, 0, muted=True),
    "mic": lambda cr: _mic(cr),
    "mic-off": lambda cr: _mic(cr, muted=True),
    "play": _play,
    "pause": _pause,
    "prev": _prev,
    "next": _next,
    "note": _note,
    "speaker": lambda cr: _speaker(cr, 2),
    "headphones": _headphones,
    "monitor": _monitor,
    "check": _check,
    "chevron-down": _chevron_down,
    "chevron-up": _chevron_up,
}


def draw(cr, name, size):
    """Draw icon `name` into a size x size square at the context origin,
    using the context's current source colour."""
    fn = ICONS.get(name)
    if fn is None:
        return
    cr.save()
    cr.scale(size / 24.0, size / 24.0)
    cr.set_line_width(STROKE)
    cr.set_line_cap(1)   # cairo.LINE_CAP_ROUND
    cr.set_line_join(1)  # cairo.LINE_JOIN_ROUND
    fn(cr)
    cr.restore()
