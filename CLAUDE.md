# CLAUDE.md

One-page A4 letters of motivation: `letter.toml` per application folder → Jinja2 HTML → WeasyPrint PDF.
Two front ends share `lomgen/core.py`: GTK4/libadwaita app (`python -m lomgen`) and CLI
(`create_letter-of-motivation.py`). Python 3.11+ (`tomllib`), Linux/GNOME, no tests, no build step.

## Look things up (don't read whole docs)

Every doc entry is a `## <key>` heading. Find it, then read only that entry:

```sh
grep -n '^## ' docs/*.md            # list all keys (cheap index)
grep -n -A12 '^## font_size' docs/*.md   # read one entry
```

| File | Keys are… | Read when |
| --- | --- | --- |
| `docs/glossary.md` | domain terms (block, fill, root, sender, stale…) | a word in code/request is unclear |
| `docs/modules.md` | source files (`core.py`, `window.py`…) | locating code, knowing what depends on what |
| `docs/data.md` | file formats & keys (`letter.toml`, `sender.toml`, `settings.toml`, status dict, layout dict) | touching any data/config |
| `docs/flows.md` | runtime sequences (render, autosave, reload, export, watch, install) | changing behaviour over time/threads |
| `docs/recipes.md` | change types (add-letter-field, add-block, add-shortcut…) | **before** implementing a change: lists every touch point |
| `docs/gotchas.md` | traps and invariants | before editing GTK, TOML writing, or layout code |

## Run / verify

```sh
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt  # once
.venv/bin/python create_letter-of-motivation.py example      # CLI build; expect "✓ … (1 page)"
.venv/bin/python -m lomgen example                           # app (needs a display)
.venv/bin/python -c "import lomgen.core, lomgen.letter_file"  # import smoke test, no display
```
No test suite: verify core changes with a CLI build of `example/`; GUI changes with the `run` skill.
PDFs are git-ignored; `example/` may already hold the user's PDFs, so remove only files you created (`ls` before and after).

## Rules

- Rendering logic lives only in `lomgen/core.py`; CLI and app must stay behaviourally identical.
- Never write `letter.toml`/`sender.toml` with plain `tomllib`/string ops — use `letter_file.TomlFile` (keeps user comments, atomic save).
- GTK calls only on the main thread; workers hand back via `GLib.idle_add`.
- Personal data (signature, real sender details) never goes into the repo; `template/` holds neutral placeholders.
- Commits: imperative subject, optional wrapped body explaining what/why (see `git log`).
- **Keep docs current**: a change that adds/renames a term, key, file, flow or touch point updates the matching `## ` entry in `docs/` in the same commit. Keep entries terse (fragment style, `file:symbol` refs, no line numbers).
