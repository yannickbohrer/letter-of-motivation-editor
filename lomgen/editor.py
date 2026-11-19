"""The form: fields in the order they appear on the page."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GObject, Gtk  # noqa: E402

from . import core  # noqa: E402

# (field name in letter_file.FIELDS, label, block on the page, optional?)
GROUPS = (
    ("Recipient", None, (
        ("recipient.company", "Company", "recipient", False),
        ("recipient.department", "Department (optional)", "recipient", True),
        ("recipient.contact", "Contact person (optional)", "recipient", True),
        ("recipient.street", "Street", "recipient", False),
        ("recipient.city", "Postcode and city", "recipient", False),
        ("recipient.country", "Country (optional)", "recipient", True),
    )),
    ("Place and date", None, (
        ("place", "Place", "date", False),
        ("date", "Date", "date", False),
    )),
    ("Subject", None, (
        ("letter.subject", "Subject", "subject", False),
        ("letter.reference", "Reference number (optional)", "subject", True),
    )),
    ("Salutation", None, (
        ("letter.salutation", "Dear", "salutation", False),
    )),
)


class Editor(Gtk.ScrolledWindow):
    __gtype_name__ = "LomEditor"
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "block-focused": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, hexpand=True)
        self._loading = False
        self.entries: dict[str, Adw.EntryRow] = {}
        self.block_widgets: dict[str, Gtk.Widget] = {}
        self.defaults: dict[str, Gtk.Label] = {}
        self.folder = None
        self.signed = False      # set by the window; only changes the file name hint

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                      margin_top=24, margin_bottom=32, margin_start=16, margin_end=16)
        clamp = Adw.Clamp(maximum_size=620, tightening_threshold=480, child=box)
        self.set_child(clamp)

        for title, description, fields in GROUPS:
            group = Adw.PreferencesGroup(title=title, description=description)
            for name, label, block, _optional in fields:
                row = Adw.EntryRow(title=label)
                if name == "letter.salutation":
                    row.set_title("Salutation")
                    row.add_prefix(Gtk.Label(label="Dear", css_classes=["dim-label"]))
                self._add_entry(group, name, row, block)
            box.append(group)

        # Body: the letter's own font, so the text you type looks like the print.
        body_group = Adw.PreferencesGroup(
            title="Body",
            description="A blank line starts a new paragraph. Put *asterisks* around words for italics.")
        self.body = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False,
                                 top_margin=14, bottom_margin=14, left_margin=16, right_margin=16)
        self.body.add_css_class("letter-body")
        self.body.update_property([Gtk.AccessibleProperty.LABEL], ["Body"])
        self.body.get_buffer().connect("changed", self._on_changed)
        self._watch_focus(self.body, "body")
        frame = Gtk.Frame(child=self.body, css_classes=["body-frame"])
        body_group.add(frame)
        box.append(body_group)
        self.block_widgets["body"] = self.body

        sign_off = Adw.PreferencesGroup(title="Sign-off")
        self._add_entry(sign_off, "letter.closing", Adw.EntryRow(title="Closing"), "sign-off")
        enclosures = Adw.EntryRow(title="Enclosures, separated by commas")
        self._add_entry(sign_off, "letter.enclosures", enclosures, "enclosures")
        box.append(sign_off)

        layout = Adw.PreferencesGroup(title="Layout")
        low, high = core.FONT_SIZE_RANGE
        self.font_size = Adw.SpinRow(
            title="Font size", subtitle="Points. Smaller fits more on the page.", digits=1,
            adjustment=Gtk.Adjustment(lower=low, upper=high, step_increment=0.5, page_increment=1,
                                      value=core.DEFAULT_FONT_SIZE))
        self.font_size.connect("notify::value", self._on_font_size)
        self._watch_focus(self.font_size, "body")
        layout.add(self.font_size)
        box.append(layout)
        # Keeps the body editor's text at the letter's size.
        self._body_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._body_css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._apply_body_size()

        file_group = Adw.PreferencesGroup(title="File name")
        self._add_entry(file_group, "file_label", Adw.EntryRow(title="Name in the PDF file name"), None)
        self.file_name = Gtk.Label(xalign=0, wrap=True, selectable=True, margin_top=8,
                                   css_classes=["dim-label", "caption"])
        file_group.add(self.file_name)
        box.append(file_group)

    # ---------------------------------------------------------------- build ---

    def _add_entry(self, group, name, row, block):
        default = Gtk.Label(css_classes=["dim-label"], visible=False)
        row.add_suffix(default)
        self.defaults[name] = default
        row.connect("changed", self._on_changed)
        if block:
            self._watch_focus(row, block)
            self.block_widgets.setdefault(block, row)
        group.add(row)
        self.entries[name] = row

    def _watch_focus(self, widget, block):
        ctrl = Gtk.EventControllerFocus()
        ctrl.connect("enter", lambda *_: self.emit("block-focused", block))
        widget.add_controller(ctrl)

    # ----------------------------------------------------------------- data ---

    def load(self, folder, values: dict) -> None:
        self.folder = folder
        self._loading = True
        try:
            for name, row in self.entries.items():
                value = values.get(name, "")
                if isinstance(value, list):
                    value = ", ".join(value)
                if row.get_text() != value:
                    row.set_text(value)
            body = values.get("letter.body", "")
            buffer = self.body.get_buffer()
            if buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) != body:
                buffer.set_text(body)
            size = values.get("font_size", core.DEFAULT_FONT_SIZE)
            if self.font_size.get_value() != size:
                self.font_size.set_value(size)
        finally:
            self._loading = False
        self._update_hints()

    def values(self) -> dict:
        out = {}
        for name, row in self.entries.items():
            text = row.get_text()
            if name == "letter.enclosures":
                out[name] = [part.strip() for part in text.split(",") if part.strip()]
            else:
                out[name] = text
        buffer = self.body.get_buffer()
        out["letter.body"] = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        out["font_size"] = round(self.font_size.get_value() * 2) / 2
        return out

    def _on_font_size(self, *_):
        self._apply_body_size()
        self._on_changed()

    def _apply_body_size(self):
        self._body_css.load_from_string(f"textview.letter-body {{ font-size: {self.font_size.get_value():g}pt; }}")

    def _on_changed(self, *_):
        self._update_hints()
        if not self._loading:
            self.emit("changed")

    def _update_hints(self):
        """Empty fields with a default show the value that will be used."""
        try:
            sender = core.load_sender()
        except Exception:
            sender = {}
        folder_name = self.folder.name if self.folder else ""
        hints = {"date": f"Today: {core.today()}", "place": sender.get("place", ""),
                 "file_label": folder_name}
        for name, label in self.defaults.items():
            hint = hints.get(name, "")
            label.set_label(hint)
            label.set_visible(bool(hint) and not self.entries[name].get_text())
        if self.folder and sender.get("file_name_suffix"):
            label = self.entries["file_label"].get_text().strip()
            self.file_name.set_label(core.pdf_name(self.folder, label, sender, signed=self.signed))

    def focus_block(self, block: str) -> None:
        widget = self.block_widgets.get(block)
        if widget is not None:
            widget.grab_focus()
