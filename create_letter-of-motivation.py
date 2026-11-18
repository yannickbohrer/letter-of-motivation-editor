#!/usr/bin/env python3
"""Create a letter of motivation (A4) from a per-application TOML file.

Usage (from anywhere; <folder> is the application folder, e.g. ~/Applications/ACME):
    python3 create_letter-of-motivation.py <folder>            # <folder>/letter-of-motivation_<Folder>_<Your-Name>_without-signature.pdf
    python3 create_letter-of-motivation.py <folder> --signed   # <folder>/letter-of-motivation_<Folder>_<Your-Name>.pdf (with signature)
    python3 create_letter-of-motivation.py <folder> --watch    # rebuild on every save + live preview at http://127.0.0.1:8765

--signed uses signature.svg (preferred) or signature.png (transparent background) from
~/.config/letter-of-motivation-editor/, else from template/ (git-ignored there).
Your details come from ~/.config/letter-of-motivation-editor/sender.toml, else template/sender.toml.
The rendering code lives in lomgen/core.py and is shared with the desktop app (python3 -m lomgen).

Each application folder needs a letter.toml: copy template/letter.toml there, or just run the
script on the folder once and it copies the template for you (with the company name filled in).
The PDF is named after the folder; set file_label in letter.toml to override it.
Setup: python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt
Desktop app: ./install.sh (see README.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "template"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

# Re-launch inside the project venv so `python3 create_letter-of-motivation.py` just works.
if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

import argparse
import json
import shutil
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(ROOT))
from lomgen.core import CONFIG_DIR, LETTER_FILE, init_letter, render_pages, safe_build  # noqa: E402

GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


# --------------------------------------------------------------- report --------

def report(status: dict) -> None:
    if not status["ok"]:
        print(f"{RED}✗ {status['message']}{RESET}", flush=True)
        return
    stamp = time.strftime("%H:%M:%S")
    rel = os.path.relpath(status["pdf"], Path.cwd())
    if status["pages"] == 1:
        print(f"{GREEN}✓ [{stamp}] {rel}  (1 page){RESET}", flush=True)
    else:
        print(f"{YELLOW}⚠ [{stamp}] {rel}  ({status['message']}){RESET}", flush=True)


# ------------------------------------------------------- watch + preview --------

PREVIEW_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Letter preview</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; background: #e5e5e5; font: 13px/1.4 system-ui, sans-serif; }
  #bar { position: sticky; top: 0; z-index: 1; padding: 8px 16px; background: #111; color: #fff;
         display: flex; gap: 16px; align-items: center; }
  #bar .warn { color: #ffd54a; } #bar .err { color: #ff7b72; white-space: pre-wrap; }
  #pages { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 24px 16px; }
  #pages img { width: min(100%, 210mm); background: #fff; box-shadow: 0 2px 12px rgba(0,0,0,.25); }
</style></head>
<body>
<div id="bar"><strong>Letter preview</strong><span id="state">waiting…</span></div>
<div id="pages"></div>
<script>
let version = -1;
async function poll() {
  try {
    const s = await (await fetch("status.json?" + Date.now())).json();
    if (s.version !== version) {
      version = s.version;
      const state = document.getElementById("state");
      if (!s.ok) { state.className = "err"; state.textContent = s.message; }
      else {
        state.className = s.pages === 1 ? "" : "warn";
        state.textContent = (s.pages === 1 ? "1 page" : s.message) + " · built " + s.time;
        document.getElementById("pages").innerHTML =
          s.images.map(src => `<img src="${src}?v=${s.version}" alt="Letter page">`).join("");
      }
    }
  } catch (e) {}
  setTimeout(poll, 600);
}
poll();
</script></body></html>
"""


def render_preview(status: dict, preview_dir: Path, version: int) -> None:
    images = [p.name for p in render_pages(status["pdf"], preview_dir)] if status["ok"] else []
    status = {k: v for k, v in status.items() if k != "layout"}
    payload = {**status, "version": version, "images": images, "time": time.strftime("%H:%M:%S")}
    (preview_dir / "status.json").write_text(json.dumps(payload), encoding="utf-8")


def serve(preview_dir: Path, port: int) -> int:
    """Serve the preview; if the port is taken (e.g. another --watch), use the next free one."""
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(preview_dir), **kw)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *args):
            pass

    for candidate in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"No free port between {port} and {port + 19} for the live preview.")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return candidate


def watched_files(folder: Path) -> list[Path]:
    files = [folder / LETTER_FILE, *(p for p in TEMPLATE_DIR.rglob("*") if p.is_file())]
    return files + [p for p in CONFIG_DIR.glob("*") if p.is_file()] if CONFIG_DIR.is_dir() else files


def snapshot(files: list[Path]) -> dict:
    return {p: p.stat().st_mtime_ns for p in files if p.exists()}


def watch(folder: Path, port: int, signed: bool = False) -> None:
    preview_dir = Path(tempfile.mkdtemp(prefix="letter-preview-"))
    (preview_dir / "index.html").write_text(PREVIEW_PAGE, encoding="utf-8")
    port = serve(preview_dir, port)
    print(f"Live preview: http://127.0.0.1:{port}   (Ctrl+C to stop)", flush=True)

    version, last = 0, None
    try:
        while True:
            current = snapshot(watched_files(folder))
            if current != last:
                last = current
                version += 1
                status = safe_build(folder, signed)
                report(status)
                render_preview(status, preview_dir, version)
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)


# ----------------------------------------------------------------- main --------

def main() -> int:
    parser = argparse.ArgumentParser(description="Create an A4 letter of motivation PDF.")
    parser.add_argument("folder", help="application folder, e.g. ~/Applications/ACME")
    parser.add_argument("--signed", action="store_true",
                        help="insert your signature (signature.svg or .png)")
    parser.add_argument("--watch", action="store_true", help="rebuild on save and serve a live preview")
    parser.add_argument("--port", type=int, default=8765, help="preview port for --watch (default 8765)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"{RED}Folder '{folder}' does not exist. Create it first.{RESET}")
        return 1

    if not (folder / LETTER_FILE).exists():
        created = init_letter(folder)
        print(f"Created {created}. Fill it in, then run the command again (or use --watch).")
        if not args.watch:
            return 0

    if args.watch:
        watch(folder, args.port, args.signed)
        return 0

    status = safe_build(folder, args.signed)
    report(status)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
