"""Main window: applications sidebar | editor | page."""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402
from tomlkit.exceptions import ParseError  # noqa: E402

from . import core, settings as app_settings  # noqa: E402
from .editor import Editor  # noqa: E402
from .letter_file import read_letter, write_letter  # noqa: E402
from .page_view import PageView, texture_from_file  # noqa: E402
from .preferences import Preferences  # noqa: E402
from .sidebar import Sidebar  # noqa: E402

SAVE_DELAY_MS = 400


def pretty_path(path: Path) -> str:
    home = str(Path.home())
    s = str(path)
    return "~" + s[len(home):] if s.startswith(home) else s


class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = "LomMainWindow"

    def __init__(self, app):
        super().__init__(application=app, title="Letter of Motivation")
        self.settings = app_settings.load()
        self.set_default_size(self.settings["width"], self.settings["height"])
        if self.settings["maximized"]:
            self.maximize()
        self.set_size_request(440, 480)

        self.folder: Path | None = None
        self.file = None
        self.monitor = None
        self._save_source = 0
        self._reload_source = 0
        self._rendering = False
        self._pending = False
        self._narrow = False
        self.preview_dir = Path(tempfile.mkdtemp(prefix="letter-preview-"))
        self.preferences: Preferences | None = None

        self._build_ui()
        self._build_actions()
        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", lambda *_: self._sync_dark())
        self._sync_dark()
        self.connect("close-request", self._on_close)

        root = self.settings.get("root")
        if root and Path(root).is_dir():
            self.sidebar.load(Path(root), select=self.settings.get("last") or None)
            if not self.folder:
                self.content_stack.set_visible_child_name("pick")
        else:
            self.split.set_show_sidebar(False)
            self.content_stack.set_visible_child_name("no-root")

    # ===================================================================== UI ==

    def _build_ui(self):
        self.toasts = Adw.ToastOverlay()
        self.split = Adw.OverlaySplitView(min_sidebar_width=220, max_sidebar_width=300,
                                          sidebar_width_fraction=0.2)
        self.toasts.set_child(self.split)
        self.set_content(self.toasts)

        self.sidebar = Sidebar()
        self.sidebar.connect("selected", lambda _s, path: self.open_application(Path(path)))
        self.split.set_sidebar(self.sidebar)

        # ---- content header
        content = Adw.ToolbarView(top_bar_style=Adw.ToolbarStyle.FLAT)
        header = Adw.HeaderBar()
        self.sidebar_btn = Gtk.ToggleButton(icon_name="sidebar-show-symbolic", tooltip_text="Show applications")
        self.split.bind_property("show-sidebar", self.sidebar_btn, "active",
                                 GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        header.pack_start(self.sidebar_btn)
        self.title = Adw.WindowTitle(title="Letter of Motivation")
        header.set_title_widget(self.title)

        menu = Gio.Menu()
        menu.append("Choose applications folder…", "win.choose-root")
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard shortcuts", "app.shortcuts")
        menu.append("About Letter of Motivation", "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text="Main menu", primary=True))
        self.export_btn = Gtk.Button(label="Export PDF", action_name="win.export",
                                     css_classes=["suggested-action"], tooltip_text="Export PDF (Ctrl+E)")
        header.pack_end(self.export_btn)

        sig_box = Gtk.Box(spacing=8, margin_end=6)
        self.sig_label = Gtk.Label(label="Include signature")
        self.sig_switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=bool(self.settings["signed"]))
        self.sig_switch.update_property([Gtk.AccessibleProperty.LABEL], ["Include signature"])
        self.sig_switch.connect("notify::active", self._on_signed_toggled)
        sig_box.append(self.sig_label)
        sig_box.append(self.sig_switch)
        self.sig_box = sig_box
        header.pack_end(sig_box)
        self.header_actions = (self.export_btn, sig_box)
        content.add_top_bar(header)

        self.banner = Adw.Banner(button_label="Open letter.toml")
        self.banner.connect("button-clicked", lambda *_: self._open_letter_file())
        content.add_top_bar(self.banner)

        # ---- content stack: empty states + the work area
        self.content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)

        no_root = Adw.StatusPage(
            icon_name="folder-open-symbolic", title="Choose your applications folder",
            description="Pick the folder that holds one folder per application, "
                        "for example ~/GoogleDrive/Bewerbungen.")
        no_root.set_child(Gtk.Button(label="Choose folder", action_name="win.choose-root",
                                     halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"]))
        self.content_stack.add_named(no_root, "no-root")

        pick = Adw.StatusPage(icon_name="document-edit-symbolic", title="Pick an application",
                              description="Choose one from the list, or start a new one.")
        pick.set_child(Gtk.Button(label="New application", action_name="win.new-application",
                                  halign=Gtk.Align.CENTER, css_classes=["pill"]))
        self.content_stack.add_named(pick, "pick")

        self.missing = Adw.StatusPage(icon_name="document-new-symbolic", title="No letter here yet",
                                      description="This folder has no letter.toml.")
        create = Gtk.Button(label="Create letter", halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
        create.connect("clicked", self._create_letter)
        self.missing.set_child(create)
        self.content_stack.add_named(self.missing, "missing")

        self.bad = Adw.StatusPage(icon_name="dialog-warning-symbolic", title="letter.toml can't be read")
        open_btn = Gtk.Button(label="Open in text editor", halign=Gtk.Align.CENTER, css_classes=["pill"])
        open_btn.connect("clicked", lambda *_: self._open_letter_file())
        self.bad.set_child(open_btn)
        self.content_stack.add_named(self.bad, "bad")

        self.editor = Editor()
        self.editor.connect("changed", self._on_edited)
        self.editor.connect("block-focused", self._on_block_focused)
        self.page = PageView()
        self.page.canvas.connect("block-activated", self._on_block_activated)
        self.paned = Gtk.Paned(start_child=self.editor, end_child=self.page, position=540,
                               shrink_start_child=False, shrink_end_child=False, resize_start_child=False)
        self.editor.set_size_request(340, -1)
        self.page.set_size_request(300, -1)
        self.content_stack.add_named(self.paned, "work")
        content.set_content(self.content_stack)

        # ---- narrow windows: switch between the editor and the page
        self.view_toggle = Adw.ToggleGroup(halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6)
        self.view_toggle.add(Adw.Toggle(name="edit", label="Edit", icon_name="document-edit-symbolic"))
        self.view_toggle.add(Adw.Toggle(name="page", label="Page", icon_name="x-office-document-symbolic"))
        self.view_toggle.set_active_name("edit")
        self.view_toggle.connect("notify::active-name", lambda *_: self._apply_narrow())
        self.bottom_bar = Gtk.CenterBox(center_widget=self.view_toggle, visible=False)
        content.add_bottom_bar(self.bottom_bar)

        self.split.set_content(content)

        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 900sp"))
        bp.add_setter(self.split, "collapsed", True)
        bp.connect("apply", lambda *_: self._set_narrow(True))
        bp.connect("unapply", lambda *_: self._set_narrow(False))
        self.add_breakpoint(bp)

        bp_small = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 560sp"))
        bp_small.add_setter(self.split, "collapsed", True)
        bp_small.add_setter(self.sig_label, "visible", False)
        bp_small.connect("apply", lambda *_: self._set_narrow(True))
        bp_small.connect("unapply", lambda *_: self._set_narrow(self.get_width() <= 900))
        self.add_breakpoint(bp_small)

        self._update_signature_state()
        self._set_work_actions(False)

    def _sync_dark(self):
        if Adw.StyleManager.get_default().get_dark():
            self.add_css_class("dark-style")
        else:
            self.remove_css_class("dark-style")

    def _build_actions(self):
        for name, callback in (("choose-root", self._choose_root), ("new-application", self._new_application),
                               ("export", self._export), ("search", self._search)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            self.add_action(action)

    def _set_work_actions(self, enabled: bool):
        action = self.lookup_action("export")
        if action:
            action.set_enabled(enabled)
        for widget in self.header_actions:
            widget.set_visible(enabled)

    def _set_narrow(self, narrow: bool):
        self._narrow = narrow
        self.bottom_bar.set_visible(narrow and self.content_stack.get_visible_child_name() == "work")
        self._apply_narrow()

    def _apply_narrow(self):
        mode = self.view_toggle.get_active_name()
        self.editor.set_visible(not self._narrow or mode == "edit")
        self.page.set_visible(not self._narrow or mode == "page")

    def _show(self, name: str):
        self.content_stack.set_visible_child_name(name)
        self._set_work_actions(name == "work")
        self.bottom_bar.set_visible(self._narrow and name == "work")
        if name != "work":
            self.banner.set_revealed(False)

    # ============================================================ folders ====

    def set_root(self, root: Path, select: Path | None = None):
        self.settings["root"] = str(root)
        app_settings.save(self.settings)
        self.sidebar.load(root, select=str(select) if select else None)
        self.split.set_show_sidebar(True)
        if self.preferences:
            self.preferences.refresh_root()
        if not select:
            self._close_application()
            self._show("pick")

    def open_folder(self, folder: Path):
        """From the command line: an application folder (has or will get a letter.toml)."""
        folder = folder.resolve()
        root = Path(self.settings.get("root") or "")
        if folder.parent != root:
            self.set_root(folder.parent, select=folder)
        else:
            self.sidebar.load(root, select=str(folder))

    def _choose_root(self):
        dialog = Gtk.FileDialog(title="Choose your applications folder")
        if self.settings.get("root"):
            dialog.set_initial_folder(Gio.File.new_for_path(self.settings["root"]))
        dialog.select_folder(self, None, self._on_root_chosen)

    def _on_root_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        self.set_root(Path(folder.get_path()))

    def _new_application(self):
        root = self.settings.get("root")
        if not root or not Path(root).is_dir():
            self._choose_root()
            return
        dialog = Adw.AlertDialog(heading="New application",
                                 body="Creates a folder with a letter for you to fill in.")
        entry = Adw.EntryRow(title="Company name")
        group = Adw.PreferencesGroup()
        group.add(entry)
        dialog.set_extra_child(group)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")
        dialog.set_response_enabled("create", False)

        def valid(text):
            return bool(text.strip()) and "/" not in text and text.strip() not in (".", "..")
        entry.connect("changed", lambda e: dialog.set_response_enabled("create", valid(e.get_text())))

        def on_activate(e):
            if valid(e.get_text()):
                dialog.close()
                self._create_application(e.get_text())
        entry.connect("entry-activated", on_activate)

        def on_response(_d, response):
            if response == "create" and valid(entry.get_text()):
                self._create_application(entry.get_text())
        dialog.connect("response", on_response)
        dialog.present(self)
        entry.grab_focus()

    def _create_application(self, name: str):
        folder = Path(self.settings["root"]) / name.strip()
        try:
            folder.mkdir(exist_ok=True)
            if not (folder / core.LETTER_FILE).exists():
                core.init_letter(folder)
        except OSError as e:
            self.toasts.add_toast(Adw.Toast(title=f"Couldn't create the folder: {e.strerror}"))
            return
        self.sidebar.load(Path(self.settings["root"]), select=str(folder))

    def _search(self):
        if self.settings.get("root"):
            self.split.set_show_sidebar(True)
            self.sidebar.search_btn.set_active(True)
            self.sidebar.search.grab_focus()

    # ======================================================== application ====

    def _close_application(self):
        self._flush_save()
        if self.monitor:
            self.monitor.cancel()
            self.monitor = None
        self.folder, self.file = None, None
        self.title.set_title("Letter of Motivation")
        self.title.set_subtitle("")

    def open_application(self, folder: Path):
        if folder == self.folder:
            return
        self._close_application()
        self.folder = folder
        self.title.set_title(folder.name)
        self.title.set_subtitle(pretty_path(folder.parent))
        self.settings["last"] = str(folder)
        app_settings.save(self.settings)
        self.monitor = Gio.File.new_for_path(str(folder / core.LETTER_FILE)).monitor_file(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self.monitor.connect("changed", self._on_file_changed)
        self._load_letter()

    def _load_letter(self):
        if not (self.folder / core.LETTER_FILE).exists():
            self._show("missing")
            return
        try:
            self.file, values = read_letter(self.folder)
        except (ParseError, ValueError) as e:
            self.file = None
            where = f"Line {e.line}, column {e.col}: " if isinstance(e, ParseError) else ""
            reason = str(e).split(" at line ")[0]
            if type(e).__name__ == "InvalidControlChar":   # the usual cause: a missing closing quote
                reason = "A quote is not closed, so the text runs into the next line"
            self.bad.set_description(f"{where}{reason}.\n\nFix it in a text editor. "
                                     "The app reloads the letter when you save the file.")
            self._show("bad")
            return
        self.editor.signed = self._signed()
        self.editor.load(self.folder, values)
        self._show("work")
        self.page.canvas.set_focused(None)
        self.page.set_caption("Rendering…")
        self._render()

    def _create_letter(self, _button):
        if self.folder:
            core.init_letter(self.folder)
            self._load_letter()
            self.sidebar.refresh(self.folder)

    def _open_letter_file(self):
        if self.folder:
            launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(self.folder / core.LETTER_FILE)))
            launcher.launch(self, None, None)

    def _on_file_changed(self, _monitor, _file, _other, event):
        if event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                         Gio.FileMonitorEvent.RENAMED, Gio.FileMonitorEvent.MOVED_IN,
                         Gio.FileMonitorEvent.DELETED, Gio.FileMonitorEvent.CHANGED):
            return
        if self._reload_source:
            GLib.source_remove(self._reload_source)
        self._reload_source = GLib.timeout_add(300, self._reload_from_disk)

    def _reload_from_disk(self):
        self._reload_source = 0
        if not self.folder:
            return False
        path = self.folder / core.LETTER_FILE
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = None
        if self.file is not None and text == self.file.text:
            return False      # our own save
        if self._save_source:
            return False      # you are typing; your version wins and is saved next
        self._load_letter()
        return False

    # ============================================================== editing ===

    def _on_edited(self, _editor):
        self.title.set_subtitle("Saving…")
        if self._save_source:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add(SAVE_DELAY_MS, self._save_and_render)

    def _save_and_render(self):
        self._save_source = 0
        if self.file is None:
            return False
        try:
            write_letter(self.file, self.editor.values())
            self.title.set_subtitle("Saved")
        except OSError as e:
            self.title.set_subtitle("Not saved")
            self.toasts.add_toast(Adw.Toast(title=f"Couldn't save letter.toml: {e.strerror}"))
        self._render()
        return False

    def _flush_save(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save_source = 0
            if self.file is not None:
                write_letter(self.file, self.editor.values())

    def _on_block_focused(self, _editor, block):
        self.page.canvas.set_focused(block)
        self.page.show_block(block)

    def _on_block_activated(self, _canvas, block):
        if self._narrow:
            self.view_toggle.set_active_name("edit")
        self.editor.focus_block(block)

    # ======================================================= signature =======

    def _signed(self) -> bool:
        return self.sig_switch.get_active() and core.find_signature(required=False) is not None

    def _update_signature_state(self):
        has = core.find_signature(required=False) is not None
        self.sig_switch.set_sensitive(has)
        self.sig_label.set_sensitive(has)
        tip = None if has else "Add a signature in Preferences"
        self.sig_box.set_tooltip_text(tip)

    def _on_signed_toggled(self, *_):
        self.settings["signed"] = self.sig_switch.get_active()
        self.editor.signed = self._signed()
        self.editor._update_hints()
        app_settings.save(self.settings)
        if self.file is not None:
            self._render()

    def preferences_changed(self):
        self._update_signature_state()
        if self.file is not None:
            self.editor._update_hints()
            self._render()

    # =========================================================== render ======

    def _render(self):
        if self.folder is None or self.file is None:
            return
        if self._rendering:
            self._pending = True
            return
        self._rendering = True
        self.page.set_busy(True)
        args = (self.folder, self._signed())
        threading.Thread(target=self._render_worker, args=args, daemon=True).start()

    def _render_worker(self, folder, signed):
        status = core.safe_build(folder, signed, pdf_path=self.preview_dir / "preview.pdf")
        textures = []
        if status["ok"]:
            textures = [t for t in (texture_from_file(p) for p in
                                    core.render_pages(status["pdf"], self.preview_dir, dpi=150)) if t]
        GLib.idle_add(self._render_done, folder, status, textures)

    def _render_done(self, folder, status, textures):
        self._rendering = False
        if self._pending:
            self._pending = False
            self._render()
        else:
            self.page.set_busy(False)
        if folder != self.folder:
            return False
        if not status["ok"]:
            self.banner.set_title(status["message"])
            self.banner.set_revealed(True)
            self.page.canvas.mark_stale()
            self.page.set_caption("The page shows the last version that worked.", "error")
            return False
        self.banner.set_revealed(False)
        layout = status["layout"]
        if not textures:
            self.page.set_caption("Install poppler-utils to see the page here.", "warning")
        self.page.canvas.show_render(textures, layout)
        fill, over = layout["fill"], layout["lines_over"]
        if fill > 1:
            lines = "line" if over == 1 else "lines"
            self.page.set_caption(f"About {over} {lines} too long for one page", "error")
            row = self.sidebar.rows.get(str(folder))
            if row:
                row.set_state(f"{status['pages']} pages", "warning")
        elif textures:
            percent = min(100, round(fill * 100))
            if fill > 0.95:
                self.page.set_caption(f"{percent}% of the page used. Almost full.", "warning")
            else:
                self.page.set_caption(f"{percent}% of the page used")
        return False

    # =========================================================== export ======

    def _export(self):
        if self.file is None:
            return
        self._flush_save()
        folder, signed = self.folder, self._signed()
        self.export_btn.set_sensitive(False)

        def work():
            status = core.safe_build(folder, signed)
            GLib.idle_add(done, status)

        def done(status):
            self.export_btn.set_sensitive(True)
            if not status["ok"]:
                self.toasts.add_toast(Adw.Toast(title=f"Export failed: {status['message']}", timeout=8))
                return False
            name = Path(status["pdf"]).name
            title = f"Exported {name}"
            if status["pages"] > 1:
                title += f". It has {status['pages']} pages."
            toast = Adw.Toast(title=title, button_label="Open", timeout=6)
            toast.connect("button-clicked", lambda *_: Gtk.FileLauncher(
                file=Gio.File.new_for_path(status["pdf"])).launch(self, None, None))
            self.toasts.add_toast(toast)
            self.sidebar.refresh(folder)
            return False

        threading.Thread(target=work, daemon=True).start()

    # ============================================================ close =====

    def _on_close(self, *_):
        self._flush_save()
        if not self.is_maximized():
            w, h = self.get_default_size()
            self.settings["width"], self.settings["height"] = w, h
        self.settings["maximized"] = self.is_maximized()
        app_settings.save(self.settings)
        shutil.rmtree(self.preview_dir, ignore_errors=True)
        return False
