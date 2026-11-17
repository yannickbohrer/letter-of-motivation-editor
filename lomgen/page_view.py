"""The page: rendered A4 pages on a desk, a page-fill gauge on the right edge, outlines of letter blocks."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Graphene, Gsk, Gtk, Pango  # noqa: E402

GUTTER = 32          # space around the page on the desk
GAUGE_GAP = 10       # page edge to gauge
GAUGE_W = 4
PAGE_GAP = 40        # between page 1 and an overflow page


def _rgba(spec: str, alpha: float = 1.0) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(spec)
    c.alpha *= alpha
    return c


# Keep a reference to each struct and init it in place: Graphene.Rect().init(...) would return a
# pointer into a temporary that Python may already have freed.
def _rect(x, y, w, h) -> Graphene.Rect:
    rect = Graphene.Rect()
    rect.init(x, y, w, h)
    return rect


def _rounded(x, y, w, h, r) -> Gsk.RoundedRect:
    size = Graphene.Size()
    size.init(r, r)
    rounded = Gsk.RoundedRect()
    rounded.init(_rect(x, y, w, h), size, size, size, size)
    return rounded


class PageCanvas(Gtk.Widget):
    """Draws the pages. Lives in a ScrolledWindow; height follows width (A4 ratio)."""

    __gtype_name__ = "LomPageCanvas"
    __gsignals__ = {"block-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self):
        super().__init__()
        self.set_css_name("page-canvas")
        self.textures: list[Gdk.Texture] = []
        self.layout: dict | None = None
        self.focused: str | None = None
        self.hovered: str | None = None
        self.stale = False           # last render failed: dim the old page
        self.zoom: float | None = None   # None = fit width, else CSS px scale (1.0 = 100 %)

        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", lambda *_: self._set_hover(None))
        self.add_controller(motion)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self.queue_draw())

    # ------------------------------------------------------------------ data --

    def show_render(self, textures: list[Gdk.Texture], layout: dict) -> None:
        self.textures, self.layout, self.stale = textures, layout, False
        self.queue_resize()

    def mark_stale(self, stale: bool = True) -> None:
        self.stale = stale
        self.queue_draw()

    def set_focused(self, block: str | None) -> None:
        if block != self.focused:
            self.focused = block
            self.queue_draw()

    def set_zoom(self, zoom: float | None) -> None:
        self.zoom = zoom
        self.queue_resize()

    # --------------------------------------------------------------- geometry --

    def _page_px(self) -> tuple[float, float]:
        if self.layout:
            return self.layout["page_size"]
        return (793.7, 1122.5)     # A4 in CSS px

    def _scale(self, width: float) -> float:
        page_w, _ = self._page_px()
        if self.zoom is not None:
            return self.zoom
        room = width - 2 * GUTTER - GAUGE_GAP - GAUGE_W
        return max(room, 120) / page_w

    def _page_origin(self, index: int, scale: float, width: float) -> tuple[float, float]:
        page_w, page_h = self._page_px()
        drawn_w = page_w * scale
        x = max(GUTTER, (width - drawn_w - GAUGE_GAP - GAUGE_W) / 2)
        y = GUTTER + index * (page_h * scale + PAGE_GAP)
        return x, y

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        page_w, page_h = self._page_px()
        pages = max(1, len(self.textures))
        if orientation == Gtk.Orientation.HORIZONTAL:
            if self.zoom is not None:
                w = int(page_w * self.zoom + 2 * GUTTER + GAUGE_GAP + GAUGE_W)
                return w, w, -1, -1
            return 200, 600, -1, -1
        width = for_size if for_size > 0 else 600
        scale = self._scale(width)
        h = int(2 * GUTTER + pages * page_h * scale + (pages - 1) * PAGE_GAP)
        return h, h, -1, -1

    def _block_at(self, px: float, py: float) -> str | None:
        if not self.layout:
            return None
        width = self.get_width()
        scale = self._scale(width)
        best = None
        for name, rects in self.layout["blocks"].items():
            for page, x, y, w, h in rects:
                ox, oy = self._page_origin(page, scale, width)
                if ox + x * scale - 4 <= px <= ox + (x + w) * scale + 4 and \
                        oy + y * scale - 4 <= py <= oy + (y + h) * scale + 4:
                    if best is None or h < best[1]:
                        best = (name, h)
        return best[0] if best else None

    # ------------------------------------------------------------- input -----

    def _set_hover(self, block):
        if block != self.hovered:
            self.hovered = block
            self.set_cursor_from_name("pointer" if block else None)
            self.queue_draw()

    def _on_motion(self, _ctrl, x, y):
        self._set_hover(self._block_at(x, y))

    def _on_click(self, _gesture, _n, x, y):
        block = self._block_at(x, y)
        if block:
            self.emit("block-activated", block)

    # ---------------------------------------------------------------- draw ----

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        dark = Adw.StyleManager.get_default().get_dark()
        ink = _rgba("#7E9BEA" if dark else "#24418F")
        warn = _rgba("#F8E45C" if dark else "#C88800")
        error = _rgba("#FF7B63" if dark else "#E01B24")
        track = _rgba("#FFFFFF" if dark else "#000000", 0.12)
        shadow = _rgba("#000000", 0.45 if dark else 0.18)

        width = self.get_width()
        scale = self._scale(width)
        page_w, page_h = self._page_px()
        pw, ph = page_w * scale, page_h * scale
        pages = self.textures or [None]

        for index, texture in enumerate(pages):
            x, y = self._page_origin(index, scale, width)
            snapshot.append_outset_shadow(_rounded(x, y, pw, ph, 1), shadow, 0, 1, 0, 6)
            snapshot.append_color(_rgba("#FFFFFF"), _rect(x, y, pw, ph))
            if texture is not None:
                if self.stale:
                    snapshot.push_opacity(0.45)
                snapshot.append_scaled_texture(texture, Gsk.ScalingFilter.TRILINEAR, _rect(x, y, pw, ph))
                if self.stale:
                    snapshot.pop()
            if index == 1:
                # Page break: a red line across the gap, labelled.
                line_y = y - PAGE_GAP / 2
                snapshot.append_color(error, _rect(x - 12, line_y - 1, pw + 24, 2))
                self._text(snapshot, "Page 2", x, line_y - 20, error, 9)

        if not self.layout:
            return

        # Outlines: focused block (ink), hovered block (faint).
        for name, color, thickness in ((self.hovered, _rgba(ink.to_string(), 0.35), 1.0),
                                       (self.focused, ink, 1.5)):
            for page, bx, by, bw, bh in self.layout["blocks"].get(name or "", ()):
                ox, oy = self._page_origin(page, scale, width)
                r = _rounded(ox + bx * scale - 5, oy + by * scale - 4, bw * scale + 10, bh * scale + 8, 4)
                snapshot.append_border(r, [thickness] * 4, [color] * 4)

        # Gauge along the right edge of page 1, spanning its content area.
        cx, cy, cw, ch = self.layout["content"]
        ox, oy = self._page_origin(0, scale, width)
        gx = ox + pw + GAUGE_GAP
        top, height = oy + cy * scale, ch * scale
        fill = self.layout["fill"]
        snapshot.append_color(track, _rect(gx, top, GAUGE_W, height))
        color = error if fill > 1 else warn if fill > 0.95 else ink
        snapshot.append_color(color, _rect(gx, top, GAUGE_W, min(fill, 1) * height))
        if fill > 1:
            # The overflow keeps going past the end of page 1, onto the desk.
            snapshot.append_color(error, _rect(gx, top + height, GAUGE_W, (fill - 1) * height))
        snapshot.append_color(_rgba(track.to_string(), 2.5), _rect(gx - 3, top + height - 0.5, GAUGE_W + 6, 1))

    def _text(self, snapshot, text, x, y, color, size_pt):
        layout = self.create_pango_layout(text)
        desc = Pango.FontDescription.from_string(f"Sans Bold {size_pt}")
        layout.set_font_description(desc)
        snapshot.save()
        point = Graphene.Point()
        point.init(x, y)
        snapshot.translate(point)
        snapshot.append_layout(layout, color)
        snapshot.restore()


class PageView(Gtk.Box):
    """Canvas in a scroller plus a bottom bar with the fill caption and zoom controls."""

    __gtype_name__ = "LomPageView"

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("desk")
        self.canvas = PageCanvas()
        self.scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=self.canvas)
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.append(self.scroller)

        bar = Gtk.Box(spacing=6, margin_start=12, margin_end=8, margin_top=6, margin_bottom=6)
        bar.add_css_class("page-bar")
        self.caption = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self.caption.add_css_class("page-caption")
        self.spinner = Adw.Spinner(visible=False)
        bar.append(self.caption)
        bar.append(self.spinner)

        zoom = Gtk.Box(css_classes=["linked"])
        out_btn = Gtk.Button(icon_name="zoom-out-symbolic", tooltip_text="Zoom out")
        self.zoom_label = Gtk.Button(label="Fit", tooltip_text="Fit page to width")
        in_btn = Gtk.Button(icon_name="zoom-in-symbolic", tooltip_text="Zoom in")
        for b in (out_btn, self.zoom_label, in_btn):
            b.add_css_class("flat")
            zoom.append(b)
        out_btn.connect("clicked", lambda *_: self._zoom_step(1 / 1.25))
        in_btn.connect("clicked", lambda *_: self._zoom_step(1.25))
        self.zoom_label.connect("clicked", lambda *_: self._set_zoom(None))
        bar.append(zoom)
        self.append(bar)

    def _zoom_step(self, factor):
        current = self.canvas.zoom if self.canvas.zoom is not None else \
            self.canvas._scale(self.scroller.get_width())
        self._set_zoom(min(3.0, max(0.3, current * factor)))

    def _set_zoom(self, zoom):
        self.canvas.set_zoom(zoom)
        self.zoom_label.set_label("Fit" if zoom is None else f"{round(zoom * 100)}%")

    def set_caption(self, text: str, state: str = "") -> None:
        self.caption.set_label(text)
        for cls in ("warning", "error"):
            self.caption.remove_css_class(cls)
        if state:
            self.caption.add_css_class(state)

    def set_busy(self, busy: bool) -> None:
        self.spinner.set_visible(busy)

    def show_block(self, block: str) -> None:
        """Scroll so that block is visible (used when an editor field gets focus)."""
        layout = self.canvas.layout
        if not layout or block not in layout["blocks"]:
            return
        page, _x, y, _w, h = layout["blocks"][block][0]
        width = self.canvas.get_width()
        scale = self.canvas._scale(width)
        _ox, oy = self.canvas._page_origin(page, scale, width)
        top, bottom = oy + y * scale - 24, oy + (y + h) * scale + 24
        adj = self.scroller.get_vadjustment()
        if top < adj.get_value():
            adj.set_value(top)
        elif bottom > adj.get_value() + adj.get_page_size():
            adj.set_value(min(top, bottom - adj.get_page_size()))


def texture_from_file(path) -> Gdk.Texture | None:
    try:
        return Gdk.Texture.new_from_filename(str(path))
    except GLib.Error:
        return None
