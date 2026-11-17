"""Letter of Motivation: GTK4 / libadwaita desktop app."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gio, Gtk, PangoCairo  # noqa: E402

from . import APP_ID, APP_NAME, VERSION, core  # noqa: E402
from .preferences import Preferences  # noqa: E402
from .window import MainWindow  # noqa: E402

SHORTCUTS = (
    ("Choose applications folder", "<Control>o"),
    ("New application", "<Control>n"),
    ("Search applications", "<Control>f"),
    ("Export PDF", "<Control>e"),
    ("Preferences", "<Control>comma"),
    ("Keyboard shortcuts", "<Control>question"),
    ("Quit", "<Control>q"),
)


class LetterApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(APP_ID)

        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name("style.css")))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # The letter's own font, for the body editor.
        fontmap = PangoCairo.FontMap.get_default()
        for font in sorted((core.TEMPLATE_DIR / "fonts").glob("*.ttf")):
            try:
                fontmap.add_font_file(str(font))
            except Exception:
                pass

        for name, callback, accel in (
            ("preferences", self._preferences, "<Control>comma"),
            ("shortcuts", self._shortcuts, "<Control>question"),
            ("about", self._about, None),
            ("quit", lambda: self.quit(), "<Control>q"),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            self.add_action(action)
            if accel:
                self.set_accels_for_action(f"app.{name}", [accel])
        for action, accel in (("win.choose-root", "<Control>o"), ("win.new-application", "<Control>n"),
                              ("win.export", "<Control>e"), ("win.search", "<Control>f")):
            self.set_accels_for_action(action, [accel])

        # WeasyPrint takes a second to import; do it now so the first page appears sooner.
        threading.Thread(target=lambda: __import__("weasyprint"), daemon=True).start()

    def _window(self) -> MainWindow:
        window = self.get_active_window()
        if window is None:
            window = MainWindow(self)
        return window

    def do_activate(self):
        self._window().present()

    def do_open(self, files, _n, _hint):
        window = self._window()
        window.present()
        for f in files:
            path = Path(f.get_path() or "")
            if path.is_dir():
                window.open_folder(path)
            elif path.name == core.LETTER_FILE:
                window.open_folder(path.parent)

    def _preferences(self):
        window = self._window()
        dialog = Preferences(window)
        dialog.connect("changed", lambda *_: window.preferences_changed())
        dialog.connect("closed", lambda *_: setattr(window, "preferences", None))
        window.preferences = dialog
        dialog.present(window)

    def _shortcuts(self):
        dialog = Adw.ShortcutsDialog()
        section = Adw.ShortcutsSection()
        for title, accel in SHORTCUTS:
            section.add(Adw.ShortcutsItem.new(title, accel))
        dialog.add(section)
        dialog.present(self._window())

    def _about(self):
        about = Adw.AboutDialog(
            application_name=APP_NAME, application_icon=APP_ID, version=VERSION,
            developer_name="Yannick Bohrer",
            comments="Write one-page application letters and export them as PDF.",
            website="https://github.com/yannickbohrer/letter-of-motivation-generator")
        about.present(self._window())


def main(argv=None) -> int:
    return LetterApp().run(argv if argv is not None else sys.argv)
