# Glossary

Domain terms. One `## term` per entry, alphabetical. Refs are `file:symbol`.

## application
One job application = one subfolder of the root, holding `letter.toml` and exported PDFs. Folder name = default company/file label.
Created by `window.py:MainWindow._create_application` / `core.init_letter`. See: root, letter.toml (data.md).

## block
Named region of the printed letter, identified by CSS class in `template/letter.html.j2`. List: `core.BLOCKS` = recipient, date, subject, salutation, body, sign-off, enclosures.
Used for: outlines + click-to-edit on the page, focus-scroll from the editor. Positions come from `core.layout_info` → `layout["blocks"]`. Editor field→block map: `editor.GROUPS` (3rd tuple item). See recipes.md: add-block.

## body
Letter text in `[letter].body`. Blank line = new paragraph, single newlines joined, `*italic*` → `<em>`, `**bold**` stripped to plain. `core.format_paragraphs`. Written back as `"""\n…\n"""` by `TomlFile.set`.

## config dir
`core.CONFIG_DIR` = `$XDG_CONFIG_HOME/letter-of-motivation-editor` (default `~/.config/…`). Holds sender.toml, signature.svg|png, settings.toml. Takes precedence over `template/`. See data.md.

## desk
Grey background area the rendered pages sit on (`page_view.PageView`, CSS `.desk` in `lomgen/style.css`).

## enclosures
List in `[letter].enclosures`; printed right-aligned in the page-1 footer via CSS `position: running(enclosures)`. Editor shows comma-separated. Excluded from fill calculation (lives in the margin).

## export
Writing the real PDF next to `letter.toml` (vs. preview PDF in a temp dir). App: `window.py:MainWindow._export` (Ctrl+E); CLI: default action. Name: see pdf name.

## file_label
Optional `letter.toml` top-level key overriding the folder name in the PDF file name.

## file_name_suffix
`sender.toml` key, appended to every PDF name (e.g. `Doe-Jane`). Required by `core.pdf_name` (KeyError → build error if missing).

## fill
Fraction of page 1's content area the letter reaches. 1.0 = exactly full, >1 = overflows onto page 2. Computed by `core.layout_info`. UI: gauge colour ink ≤0.95 < warn ≤1 < error; caption text in `window.py:MainWindow._render_done`.

## font_size
Per-letter text size in pt, top-level in `letter.toml`. Default `core.DEFAULT_FONT_SIZE` (11), clamped to `core.FONT_SIZE_RANGE` (9–13); editor steps 0.5. Passed to template as CSS var `--text-size`. Not written to files that never had it while it equals the default (`letter_file.write_letter`).

## gauge
Thin vertical bar right of page 1 showing fill. Drawn in `page_view.py:PageCanvas.do_snapshot`.

## layout
Dict returned in status["layout"] from `core.layout_info`: fill, lines_over, blocks, page_size, content. Units CSS px (96/in). See data.md: layout dict.

## lines_over
Rough count of body lines to cut to fit one page (0 if it fits). `core.layout_info`.

## pdf name
`letter-of-motivation_<file_label or folder>_<file_name_suffix>[_without-signature].pdf`. `core.pdf_name`. Sidebar finds exports by glob `letter-of-motivation_*.pdf`.

## preview
Throwaway render used for the live page. App: `preview_dir/preview.pdf` + PNGs (temp dir, removed on close). CLI `--watch`: temp dir served over HTTP. Both rasterise via `core.render_pages` (poppler `pdftoppm`).

## root
The "applications folder": parent dir holding one folder per application. Stored as `settings.toml: root`. Chosen via `win.choose-root` (Ctrl+O). Also set implicitly when the app is opened with a folder whose parent differs (`MainWindow.open_folder`).

## sender
Your own details shared by all letters: `sender.toml` (name, place, file_name_suffix). Resolved by `core.sender_path` (config dir, else template). Edited in Preferences.

## signature
`signature.svg` (preferred) or `signature.png`, config dir before template dir (`core.find_signature`). Inserted only when "signed" (CLI `--signed`, app switch "Include signature", persisted as `settings.toml: signed`). Template copies are git-ignored.

## signed
Boolean: include signature image and drop `_without-signature` from PDF name. App: effective only if a signature file exists (`MainWindow._signed`).

## stale
Page canvas state after a failed render: last good page shown dimmed, error in banner. `PageCanvas.mark_stale`.

## status dict
Return value of `core.build`/`core.safe_build`; see data.md. Never raises from `safe_build`.

## template dir
`core.TEMPLATE_DIR` = `<repo or install>/template`: Jinja template, print CSS, fonts, default letter.toml/sender.toml. Fallback for config dir.
