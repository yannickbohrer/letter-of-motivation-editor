# Gotchas

Traps and invariants. One `## topic` per entry.

## gtk-threads
Only the main thread touches widgets. Pattern: `threading.Thread(daemon=True)` for build/pdfinfo/pdftoppm, results via `GLib.idle_add(fn, …)`; idle/timeout callbacks `return False` to run once.

## graphene-structs
In `page_view.py` create `Graphene.Rect()`/`Size()`/`Point()` then `.init(...)` on a kept reference. `Graphene.Rect().init(...)` returns a pointer into a freed temporary → garbage/crash. Use `_rect`/`_rounded` helpers.

## gi-require-version
Every GTK module calls `gi.require_version("Gtk","4.0")`/`("Adw","1")` before `from gi.repository import …` (hence `# noqa: E402`). Keep this in new modules. PyGObject comes from the system (venv uses `--system-site-packages`); it is not pip-installable here.

## libadwaita-version
Uses recent Adw widgets (`Adw.ToggleGroup`, `Adw.Spinner`, `Adw.ShortcutsDialog`, `Adw.AlertDialog`, `Adw.Banner`). Check availability before using newer API; no fallback code exists.

## toml-writing
Read for rendering: `tomllib` (strict). Read/write for editing: tomlkit via `TomlFile` (preserves comments/order). `TomlFile.set` is a no-op when unchanged and `save` returns False when text identical — reload logic relies on `file.text` equalling disk content after own saves. Writes are atomic (`.letter.toml.tmp` → replace) because of cloud-sync/file watchers.

## body-newlines
TOML drops the first newline after `"""`; `TomlFile.set` writes `"""\n{text}\n"""` and escapes `\` and `"""`. Comparisons strip surrounding `\n` (`read_letter`, `write_letter`) to avoid rewrite loops.

## weasyprint-import
Slow import: only inside `core.build`; app pre-imports in a thread. Don't import it at module top level.

## weasyprint-internals
`core.layout_info` walks private box trees (`page._page_box`, `BlockBox`, `LineBox`, `element_tag`). Pinned `weasyprint==70.0`; upgrading may break it — re-verify fill/blocks after any bump.

## strict-undefined
Jinja env uses `StrictUndefined`: a template variable missing from the context is a build error (shown in banner/CLI), not empty output.

## poppler-optional
`render_pages` returns [] without `pdftoppm`; app then shows a warning caption, CLI preview shows no images. `pdfinfo` missing → sidebar shows "PDF". Builds themselves don't need poppler.

## font-size-default-not-written
`write_letter` skips `font_size` when the file never had it and value == default, so opening old letters doesn't modify them. Preserve this "don't touch untouched files" behaviour for new fields with defaults.

## installed-copy
The menu-launched app runs from `~/.local/share/letter-of-motivation-editor`, not the repo. Test from the repo with `.venv/bin/python -m lomgen`; users update via `git pull && ./install.sh`.

## personal-data
`template/signature.*` is git-ignored; install.sh strips it from the installed template. Never commit real names, addresses or signatures; placeholders are "Jane Doe", "City", "Company Name" (the latter is replaced literally by `init_letter`).

## dark-mode
Window gets `.dark-style` class synced from `Adw.StyleManager` (`MainWindow._sync_dark`) for `lomgen/style.css`; canvas colours are chosen per mode in `PageCanvas.do_snapshot`. The printed page is always white.
