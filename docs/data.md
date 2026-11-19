# Data

File formats and in-memory dicts. One `## name` per entry.

## letter.toml
Per application folder. Template: `template/letter.toml`; full example: `example/letter.toml`.
Defaults applied in `core.load_context`; editor field list in `letter_file.FIELDS`.

| key | default | notes |
| --- | --- | --- |
| `date` | today (`core.today`, "19 November 2026") | free text |
| `place` | sender.place | |
| `file_label` | folder name | PDF name only |
| `font_size` | 11 | number, clamped 9–13; see glossary font_size |
| `[recipient] company` | "" | bold; template seed = folder name |
| `[recipient] department contact country` | "" | optional, line hidden if empty |
| `[recipient] street city` | "" | always printed |
| `[letter] subject` | "" | bold |
| `[letter] reference` | "" | renders ` (Ref. X)` |
| `[letter] salutation` | "Hiring Team" | after "Dear ", trailing comma stripped then re-added |
| `[letter] body` | "" | see glossary body |
| `[letter] closing` | "Kind regards," | |
| `[letter] enclosures` | [] | list of str |

Unknown keys are ignored by rendering and preserved by tomlkit.

## sender.toml
Resolved: `CONFIG_DIR/sender.toml`, else `template/sender.toml` (`core.sender_path`).
Keys: `name` (under signature line, HTML title/author), `place` (default place), `file_name_suffix` (PDF name, required).
App writes via `preferences.user_sender_file()` (creates config copy first).

## settings.toml
`CONFIG_DIR/settings.toml`, app only. `settings.DEFAULTS`: `root` (str), `last` (last opened application path), `signed` (bool), `width`/`height` (int), `maximized` (bool). Only these keys persist.

## signature files
`signature.svg` | `signature.png` in CONFIG_DIR then TEMPLATE_DIR; first hit wins. App's Preferences copies the chosen file to CONFIG_DIR as `signature.<ext>` after deleting both.

## template context
Variables available in `letter.html.j2`: `sender` (dict), `font_size` (str, e.g. "10.5"), `recipient` (dict, all 6 keys present), `letter` (dict + `paragraphs: list[Markup]`), `date`, `place`, `file_label`, `signature` (file URI or None). StrictUndefined: any new variable must be supplied by `load_context`/`build`.

## status dict
`core.build`/`safe_build` → `{ok: bool, pages: int, pdf: str, layout: dict|None, message: str}`. On failure ok=False, pages=0, pdf="", layout=None, message = error text (TOML errors prefixed `letter.toml:`). `message` non-empty when pages>1. CLI `--watch` adds version/images/time and drops layout before writing status.json.

## layout dict
`core.layout_info` (CSS px, 96/in):
- `fill: float`, `lines_over: int`
- `blocks: {block: [(page_index, x, y, w, h), …]}` (border boxes; several if split across pages)
- `page_size: (w, h)` (A4 ≈ 793.7×1122.5)
- `content: (x, y, w, h)` of page 1 content box

## editor values
`Editor.values()` / `read_letter` dict: keys `"recipient.company"`, `"letter.body"`, `"place"`, `"font_size"`… (from `letter_file.FIELDS`). enclosures = list[str]; font_size = float rounded to 0.5; body without surrounding newlines.

## install layout
`~/.local/share/letter-of-motivation-editor/` (lomgen, template, CLI, requirements, .venv), `~/.local/bin/letter-of-motivation` (`PYTHONPATH=… python -m lomgen "$@"`), `~/.local/share/applications/<APP_ID>.desktop`, `~/.local/share/icons/hicolor/scalable/apps/<APP_ID>.svg`. Installed copy is separate from the repo: run `./install.sh` again to see changes in the installed app.
