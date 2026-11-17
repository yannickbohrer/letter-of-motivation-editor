"""Applications sidebar: one row per subfolder of the applications folder."""

from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk  # noqa: E402

from .core import LETTER_FILE  # noqa: E402


def pdf_state(folder: Path) -> tuple[str, str]:
    """(label, css state) for a folder: its newest exported letter and how many pages it has."""
    if not (folder / LETTER_FILE).exists():
        return "Not started", "dim"
    pdfs = sorted(folder.glob("letter-of-motivation_*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pdfs:
        return "No PDF yet", "dim"
    try:
        info = subprocess.run(["pdfinfo", str(pdfs[0])], capture_output=True, text=True, timeout=5).stdout
        pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    except (OSError, subprocess.SubprocessError, AttributeError):
        return "PDF", ""
    return ("1 page", "ok") if pages == 1 else (f"{pages} pages", "warning")


class AppRow(Gtk.ListBoxRow):
    def __init__(self, folder: Path):
        super().__init__()
        self.folder = folder
        box = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8, margin_start=6, margin_end=6)
        self.title = Gtk.Label(label=folder.name, xalign=0, hexpand=True, ellipsize=3)
        self.state = Gtk.Label(css_classes=["caption", "dim-label"])
        box.append(self.title)
        box.append(self.state)
        self.set_child(box)

    def set_state(self, label: str, state: str):
        self.state.set_label(label)
        for cls in ("dim-label", "success", "warning"):
            self.state.remove_css_class(cls)
        self.state.add_css_class({"ok": "success", "warning": "warning"}.get(state, "dim-label"))
        self.update_property([Gtk.AccessibleProperty.DESCRIPTION], [label])


class Sidebar(Adw.Bin):
    __gtype_name__ = "LomSidebar"
    __gsignals__ = {"selected": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self):
        super().__init__()
        self.root: Path | None = None
        self.rows: dict[str, AppRow] = {}
        view = Adw.ToolbarView()     # final type, so it's wrapped rather than subclassed
        self.set_child(view)

        header = Adw.HeaderBar(show_title=True)
        header.set_title_widget(Adw.WindowTitle(title="Applications"))
        new_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New application (Ctrl+N)",
                             action_name="win.new-application")
        self.search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic",
                                           tooltip_text="Search applications (Ctrl+F)")
        header.pack_start(new_btn)
        header.pack_end(self.search_btn)
        view.add_top_bar(header)

        self.search = Gtk.SearchEntry(placeholder_text="Search applications", hexpand=True)
        self.search_bar = Gtk.SearchBar(child=self.search)
        self.search_bar.connect_entry(self.search)
        self.search_btn.bind_property("active", self.search_bar, "search-mode-enabled",
                                      GObject.BindingFlags.BIDIRECTIONAL)
        self.search.connect("search-changed", lambda *_: self.list.invalidate_filter())
        view.add_top_bar(self.search_bar)

        self.list = Gtk.ListBox(css_classes=["navigation-sidebar"])
        self.list.set_filter_func(self._filter)
        self.list.connect("row-selected", self._on_selected)
        self.empty = Adw.StatusPage(title="No applications yet", icon_name="folder-new-symbolic",
                                    description="Each application gets its own folder.")
        self.empty.add_css_class("compact")
        new_app = Gtk.Button(label="New application", action_name="win.new-application",
                             halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
        self.empty.set_child(new_app)
        self.stack = Gtk.Stack()
        self.stack.add_named(Gtk.ScrolledWindow(child=self.list, vexpand=True), "list")
        self.stack.add_named(self.empty, "empty")
        view.set_content(self.stack)

    def _filter(self, row: AppRow) -> bool:
        query = self.search.get_text().strip().casefold()
        return not query or query in row.folder.name.casefold()

    def _on_selected(self, _list, row):
        if row is not None:
            self.emit("selected", str(row.folder))

    def load(self, root: Path, select: str | None = None) -> None:
        self.root = root
        while (child := self.list.get_first_child()) is not None:
            self.list.remove(child)
        self.rows.clear()
        try:
            folders = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        except OSError:
            folders = []
        # Most recently touched first: you usually work on the newest applications.
        def touched(p: Path) -> float:
            letter = p / LETTER_FILE
            return letter.stat().st_mtime if letter.exists() else p.stat().st_mtime
        folders.sort(key=touched, reverse=True)
        for folder in folders:
            row = AppRow(folder)
            self.rows[str(folder)] = row
            self.list.append(row)
        self.stack.set_visible_child_name("list" if folders else "empty")
        threading.Thread(target=self._load_states, args=(folders,), daemon=True).start()
        if select and select in self.rows:
            self.list.select_row(self.rows[select])

    def _load_states(self, folders):
        for folder in folders:
            label, state = pdf_state(folder)
            GLib.idle_add(self._apply_state, str(folder), label, state)

    def _apply_state(self, key, label, state):
        if key in self.rows:
            self.rows[key].set_state(label, state)
        return False

    def refresh(self, folder: Path) -> None:
        key = str(folder)
        if key in self.rows:
            threading.Thread(target=lambda: GLib.idle_add(self._apply_state, key, *pdf_state(folder)),
                             daemon=True).start()

    def selected_folder(self) -> Path | None:
        row = self.list.get_selected_row()
        return row.folder if row else None
