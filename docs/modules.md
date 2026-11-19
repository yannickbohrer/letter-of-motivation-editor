# Modules

One `## path` per source file. Format: purpose · key symbols · imports (→) · imported by (←).

## lomgen/core.py
Rendering core, no GTK. Paths, data loading, PDF build, layout measurement, rasterising.
Symbols: `ROOT TEMPLATE_DIR CONFIG_DIR LETTER_FILE SENDER_FILE SIGNATURE_FILES DEFAULT_FONT_SIZE FONT_SIZE_RANGE BLOCKS`, `sender_path find_signature format_paragraphs today load_sender load_context pdf_name output_path init_letter layout_info build safe_build render_pages`.
→ jinja2, markupsafe, weasyprint (lazy, inside `build`), `pdftoppm` subprocess. ← everything.

## lomgen/letter_file.py
Comment-preserving TOML read/write via tomlkit.
Symbols: `FIELDS` (ordered (table, key) list of editor fields), `TomlFile` (get/set/save, atomic, no-op if unchanged), `read_letter(folder)→(TomlFile, values)`, `write_letter(f, values)→bool`. Values keyed `"table.key"` or `"key"`.
→ core. ← window, preferences.

## lomgen/settings.py
App UI state in `CONFIG_DIR/settings.toml`. `DEFAULTS`, `load()`, `save(data)` (only DEFAULTS keys are written).
→ core. ← window.

## lomgen/app.py
`LetterApp(Adw.Application)`: startup (CSS, Roboto fonts into Pango, app actions, accels, weasyprint pre-import thread), `do_open` (folder or letter.toml args), Preferences/Shortcuts/About dialogs. `SHORTCUTS` = list shown in shortcuts dialog. `main()`.
→ core, preferences, window. ← `__main__`.

## lomgen/window.py
`MainWindow`: composes sidebar | editor | page; owns state (folder, file, monitor, preview_dir), win actions, content stack pages (`no-root pick missing bad work`), breakpoints (≤900sp collapse sidebar, ≤560sp edit/page toggle), autosave, file monitor reload, threaded render & export, signature switch, persisting window size.
→ core, settings, editor, letter_file, page_view, preferences, sidebar.

## lomgen/editor.py
`Editor(Gtk.ScrolledWindow)`: form in page order. `GROUPS` = (name, label, block, optional) for entry rows; body TextView, closing/enclosures, font_size SpinRow, file_label + live file-name hint. Signals `changed`, `block-focused(str)`. `load(folder, values)`, `values()`, `focus_block(block)`, `_update_hints()` (default placeholders from sender/today/folder).
→ core. ← window.

## lomgen/page_view.py
`PageCanvas(Gtk.Widget)`: custom snapshot drawing of page textures, page-2 break line, hover/focus outlines, fill gauge; hit-testing `_block_at`; zoom (None = fit width). Signal `block-activated(str)`. `PageView(Gtk.Box)`: scroller + caption/spinner/zoom bar, `set_caption(text, state)`, `set_busy`, `show_block`. `texture_from_file`.
← window.

## lomgen/sidebar.py
`Sidebar(Adw.Bin)`: list of application folders (non-hidden subdirs of root, newest letter.toml mtime first), search filter, empty state. Signal `selected(str path)`. `load(root, select)`, `refresh(folder)`. `AppRow.set_state(label, state)`. `pdf_state(folder)` reads newest export's page count via `pdfinfo` in a thread.
→ core. ← window.

## lomgen/preferences.py
`Preferences(Adw.PreferencesDialog)`: sender fields (apply-button rows → `user_sender_file()` copies sender.toml into config dir on first write), signature choose/remove (config dir only), root folder row. Signal `changed`.
→ core, letter_file. ← app, window.

## lomgen/style.css
App chrome CSS only (desk, page bar, body editor frame/font, `.dark-style` overrides). Not the letter's look.

## lomgen/__init__.py
`APP_ID APP_NAME VERSION`. `__main__.py` runs `app.main`.

## create_letter-of-motivation.py
CLI. Re-execs into `./.venv` if present. Args: `folder`, `--signed`, `--watch`, `--port` (8765, tries +19). Creates letter.toml if missing. `--watch` polls mtimes of letter.toml + template/ + config dir every 0.4 s, rebuilds, serves `PREVIEW_PAGE` polling `status.json`.
→ core.

## template/letter.html.j2
Jinja2 (StrictUndefined, autoescape). Context = `core.load_context` + `signature`. CSS classes = blocks.

## template/style.css
Print CSS for WeasyPrint: `@page` A4 margins 28/20/20/20 mm, Roboto `@font-face`, `--text-size`/`--line` vars, block spacing, signature placement, footer enclosures.

## template/letter.toml, template/sender.toml
Defaults copied by `init_letter` (replaces literal `Company Name` with folder name) / install.sh / `user_sender_file`. Comments here end up in users' files.

## example/letter.toml
Reference letter using every field; verification target for CLI builds.

## install.sh, uninstall.sh
Per-user install to `~/.local/share/letter-of-motivation-editor` (+ venv), launcher `~/.local/bin/letter-of-motivation`, desktop file (`@BINDIR@` substituted) and icon; seeds config dir once; migrates old `letter-of-motivation-generator` config. Uninstall keeps config.

## data/
`io.github.yannickbohrer.LetterOfMotivation.desktop` (template, `@BINDIR@`), `icons/…svg`.

## requirements.txt
Pinned pip deps: weasyprint, Jinja2, tomlkit. System deps (apt) listed in its header and checked by install.sh.
