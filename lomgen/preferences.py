"""Preferences: your details (sender.toml), signature, applications folder."""

from __future__ import annotations

import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

from . import core  # noqa: E402
from .letter_file import TomlFile  # noqa: E402


def user_sender_file() -> TomlFile:
    """~/.config/.../sender.toml, created from the current one (with its comments) the first time."""
    target = core.CONFIG_DIR / core.SENDER_FILE
    if not target.exists():
        core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(core.sender_path(), target)
    return TomlFile(target)


class Preferences(Adw.PreferencesDialog):
    __gtype_name__ = "LomPreferences"
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, window):
        super().__init__(title="Preferences", search_enabled=False)
        self.window = window
        page = Adw.PreferencesPage()
        self.add(page)

        sender = core.load_sender()
        you = Adw.PreferencesGroup(title="Your details", description="Used in every letter.")
        self.rows = {}
        for key, title in (("name", "Your name"), ("place", "Default place"),
                           ("file_name_suffix", "File name suffix")):
            row = Adw.EntryRow(title=title, text=sender.get(key, ""), show_apply_button=True)
            row.connect("apply", self._on_apply, key)
            you.add(row)
            self.rows[key] = row
        self.suffix_hint = Gtk.Label(xalign=0, wrap=True, margin_top=8, css_classes=["dim-label", "caption"])
        you.add(self.suffix_hint)
        self._update_suffix_hint()
        page.add(you)

        sig = Adw.PreferencesGroup(
            title="Signature",
            description="An SVG or a PNG with a transparent background. "
                        "It is added when “Include signature” is on.")
        self.sig_picture = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN,
                                       height_request=90, margin_top=12, margin_bottom=12)
        self.sig_row = Adw.ActionRow(title="Signature file")
        choose = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_signature)
        self.remove_btn = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                     tooltip_text="Remove signature", css_classes=["flat"])
        self.remove_btn.connect("clicked", self._remove_signature)
        self.sig_row.add_suffix(self.remove_btn)
        self.sig_row.add_suffix(choose)
        sig.add(self.sig_row)
        sig.add(self.sig_picture)
        page.add(sig)
        self._update_signature()

        folder = Adw.PreferencesGroup(title="Applications folder",
                                      description="Holds one folder per application.")
        self.root_row = Adw.ActionRow(title="Folder", subtitle=self._pretty(window.settings.get("root", "")))
        change = Gtk.Button(label="Change…", valign=Gtk.Align.CENTER, action_name="win.choose-root")
        self.root_row.add_suffix(change)
        folder.add(self.root_row)
        page.add(folder)

    @staticmethod
    def _pretty(path: str) -> str:
        if not path:
            return "Not chosen yet"
        home = str(Path.home())
        return "~" + path[len(home):] if path.startswith(home) else path

    def refresh_root(self):
        self.root_row.set_subtitle(self._pretty(self.window.settings.get("root", "")))

    # ------------------------------------------------------------- details ---

    def _on_apply(self, row, key):
        f = user_sender_file()
        f.set(None, key, row.get_text().strip())
        f.save()
        self._update_suffix_hint()
        self.add_toast(Adw.Toast(title="Saved", timeout=2))
        self.emit("changed")

    def _update_suffix_hint(self):
        suffix = self.rows["file_name_suffix"].get_text().strip() or "…"
        self.suffix_hint.set_label(f"Files are named letter-of-motivation_<Company>_{suffix}.pdf")

    # ----------------------------------------------------------- signature ---

    def _update_signature(self):
        path = core.find_signature(required=False)
        if path:
            self.sig_row.set_subtitle(self._pretty(str(path)))
            self.sig_picture.set_filename(str(path))
            self.sig_picture.set_visible(True)
        else:
            self.sig_row.set_subtitle("None. Letters can only be exported without a signature.")
            self.sig_picture.set_visible(False)
        # Only a signature in your config folder can be removed from here.
        self.remove_btn.set_visible(bool(path) and path.parent == core.CONFIG_DIR)

    def _choose_signature(self, _button):
        dialog = Gtk.FileDialog(title="Choose your signature")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        images = Gtk.FileFilter(name="SVG or PNG")
        images.add_suffix("svg")
        images.add_suffix("png")
        filters.append(images)
        dialog.set_filters(filters)
        dialog.open(self.window, None, self._on_signature_chosen)

    def _on_signature_chosen(self, dialog, result):
        try:
            source = Path(dialog.open_finish(result).get_path())
        except GLib.Error:
            return  # cancelled
        ext = source.suffix.lower().lstrip(".")
        if ext not in ("svg", "png"):
            self.add_toast(Adw.Toast(title="Choose an SVG or a PNG file"))
            return
        core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        for name in core.SIGNATURE_FILES:
            (core.CONFIG_DIR / name).unlink(missing_ok=True)
        shutil.copyfile(source, core.CONFIG_DIR / f"signature.{ext}")
        self._update_signature()
        self.emit("changed")

    def _remove_signature(self, _button):
        for name in core.SIGNATURE_FILES:
            (core.CONFIG_DIR / name).unlink(missing_ok=True)
        self._update_signature()
        self.emit("changed")
