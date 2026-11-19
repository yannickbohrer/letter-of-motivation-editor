# Flows

Runtime sequences. One `## name` per entry. Arrows = call order.

## build
`core.build(folder, signed, pdf_path)` → `load_context` (sender.toml + letter.toml + defaults) → `find_signature` if signed → Jinja render `letter.html.j2` → `weasyprint.HTML(base_url=TEMPLATE_DIR).render()` → `write_pdf` → `layout_info` → status dict. `safe_build` wraps and converts every exception to `ok=False`.

## app startup
`LetterApp.do_startup`: load `lomgen/style.css`, register Roboto TTFs with Pango, add app actions + accels, background `import weasyprint`. `do_activate`/`do_open` → `MainWindow` → `settings.load()` → if root valid: `sidebar.load(root, select=last)` else show `no-root`. `do_open` with folder/letter.toml → `MainWindow.open_folder`.

## open application
Sidebar row selected → `selected` signal → `MainWindow.open_application` → `_close_application` (flush save, cancel monitor) → save `last` → `Gio.FileMonitor` on letter.toml → `_load_letter`: missing → `missing` page; parse error → `bad` page with line/col; else `editor.load` → `work` page → `_render`.

## autosave
Editor `changed` → `MainWindow._on_edited` (subtitle "Saving…", restart `SAVE_DELAY_MS`=400 timer) → `_save_and_render` → `write_letter(file, editor.values())` (tomlkit, atomic, skip if unchanged) → `_render`. `_flush_save` forces pending save on close/switch/export.

## external edit reload
FileMonitor event → 300 ms debounce → `_reload_from_disk`: ignore if text == `file.text` (own save) or a save is pending (typing wins) → else `_load_letter`.

## render (app)
`MainWindow._render`: if one is running set `_pending` (coalesce) → thread `_render_worker`: `safe_build(pdf_path=preview_dir/preview.pdf)` → `render_pages(dpi=150)` → textures → `GLib.idle_add(_render_done)`. `_render_done`: re-run if pending; drop if folder changed; failure → banner + `mark_stale`; success → `canvas.show_render`, caption (fill %/overflow), sidebar row warning if >1 page.

## page ↔ editor linking
Editor field focus → `block-focused(block)` → `canvas.set_focused` + `page.show_block` (scroll). Click on page → `PageCanvas._block_at` (smallest containing rect) → `block-activated` → `editor.focus_block` (switches narrow view to edit).

## export (app)
`win.export` → `_flush_save` → thread `safe_build(folder, signed)` (real output path) → idle: toast with Open button or error toast → `sidebar.refresh(folder)`.

## sidebar states
`Sidebar.load` → rows sorted by mtime → thread `pdf_state` per folder (`pdfinfo` on newest `letter-of-motivation_*.pdf`) → idle `AppRow.set_state`. States: Not started / No PDF yet / 1 page (ok) / N pages (warning).

## preferences change
Apply row → write sender.toml in config dir → `changed` → `MainWindow.preferences_changed` → refresh signature switch sensitivity, editor hints, re-render.

## cli
`main` → folder must exist → create letter.toml if missing (exit unless `--watch`) → `--watch` loop or single `safe_build` + `report` (exit 1 on failure; warns, exit 0, if >1 page).

## cli watch
Temp dir with `index.html` (`PREVIEW_PAGE`) → `serve` on 127.0.0.1:port (next free of 20) in daemon thread → loop every 0.4 s: mtime snapshot of letter.toml, all template/ files, config dir files → on change `safe_build` → `report` → `render_preview` (PNGs + status.json with version). Browser polls status.json every 600 ms.

## install
`install.sh`: migrate old config → check apt deps (prints `sudo apt install …`, exit 1) → copy lomgen/template/CLI/requirements (strip signatures, pycache) → create venv `--system-site-packages` once, pip install → write launcher, desktop file, icon, refresh caches → seed config dir sender.toml/signature if absent.
