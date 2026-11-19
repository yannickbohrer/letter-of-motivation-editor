# Recipes

Touch-point checklists per change type. One `## change` per entry. Do every step or say why skipped.

## add-letter-field
New key in letter.toml shown in the editor and printed.
1. `template/letter.toml`: key with comment (seeds new letters).
2. `example/letter.toml`: realistic value (must use every field).
3. `core.load_context`: default (StrictUndefined fails otherwise); strip/convert as needed.
4. `letter_file.FIELDS`: (table, key) in page order; special default in `read_letter` if not `""`.
5. `editor.GROUPS` (entry row) or a custom widget in `Editor.__init__` + `load`/`values`.
6. `template/letter.html.j2` (+ `template/style.css`); wrap optional output in `{% if %}`.
7. New page region? → add-block.
8. Docs: data.md letter.toml table, glossary if a new term.

## add-block
Make a printed region clickable/outlined.
1. Give its element a unique CSS class in `letter.html.j2` (must be a block-level box).
2. Add the class to `core.BLOCKS`.
3. Map editor rows to it via `editor.GROUPS` 3rd item or `_watch_focus(widget, block)`.
4. If it lives in the page margin (like enclosures), exclude it from bottoms in `core.layout_info`.
5. Docs: glossary block list.

## add-sender-field
1. `template/sender.toml` with comment. 2. Use in template/`core`. 3. `preferences.Preferences.__init__` row tuple list. 4. Docs: data.md sender.toml. Existing users' config copies won't have it: use `sender.get(key, default)`.

## add-app-setting
1. `settings.DEFAULTS` (only listed keys persist). 2. Read/write via `MainWindow.settings` + `app_settings.save`. 3. Docs: data.md settings.toml.

## add-shortcut
1. Action: app-level in `app.py:LetterApp.do_startup` loop, window-level in `window.py:MainWindow._build_actions`.
2. Accel: `set_accels_for_action` in `do_startup` (both app.* and win.*).
3. `app.SHORTCUTS` for the shortcuts dialog. 4. Tooltip text mentioning it, if a button exists.

## change-print-layout
Edit `template/style.css` (mm/pt units, `@page`). Rebuild `example/` via CLI and check page count stays 1. If block geometry assumptions change, check `core.layout_info` (line height default `font_size*96/72*1.45` mirrors `--line`).

## change-pdf-name
`core.pdf_name` only; sidebar glob `letter-of-motivation_*.pdf` (`sidebar.pdf_state`), Preferences hint `_update_suffix_hint`, CLI docstring, README must match.

## add-content-page
New full-pane state in the window: `Adw.StatusPage` → `content_stack.add_named(widget, name)` in `MainWindow._build_ui`; show with `self._show(name)` (handles header actions, banner, bottom bar).

## add-dependency
pip: pin in `requirements.txt` (install.sh installs it). apt/system: add to `requirements.txt` header, the check block in `install.sh`, README setup line.

## release-or-rename
`lomgen/__init__.py` (APP_ID/APP_NAME/VERSION); APP_ID also in install.sh, uninstall.sh, `data/` filenames + desktop Icon. Config dir name in `core.CONFIG_DIR`, both shell scripts, README.
