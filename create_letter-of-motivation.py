#!/usr/bin/env python3
"""Create a letter of motivation (A4) from a per-application TOML file.

Usage (from anywhere; <folder> is the application folder, e.g. ~/GoogleDrive/Bewerbungen/STARK):
    python3 create_letter-of-motivation.py <folder>            # <folder>/letter-of-motivation_<Folder>_Bohrer-Yannick_without-signature.pdf
    python3 create_letter-of-motivation.py <folder> --signed   # <folder>/letter-of-motivation_<Folder>_Bohrer-Yannick.pdf (with signature)
    python3 create_letter-of-motivation.py <folder> --watch    # rebuild on every save + live preview at http://127.0.0.1:8765

--signed uses template/signature.svg (preferred) or template/signature.png (transparent background).
The signature file is git-ignored, so it never ends up in the repository.

Each application folder needs a letter.toml: copy template/letter.toml there, or just run the
script on the folder once and it copies the template for you (with the company name filled in).
The PDF is named after the folder; set file_label in letter.toml to override it.
Setup: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
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
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import tomllib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

LETTER_FILE = "letter.toml"
SIGNATURE_FILES = ("signature.svg", "signature.png")  # looked up in TEMPLATE_DIR, first match wins
GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


# ---------------------------------------------------------------- data --------

def format_paragraphs(body: str) -> list[Markup]:
    """Blank line = new paragraph, single newlines are joined. Supports *italic*; **bold** is printed plain."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", body.strip()):
        text = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not text:
            continue
        text = html.escape(text, quote=False)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # no bold in the body text
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
        paragraphs.append(Markup(text))
    return paragraphs


def load_context(folder: Path) -> dict:
    sender = tomllib.loads((TEMPLATE_DIR / "sender.toml").read_text(encoding="utf-8"))
    data = tomllib.loads((folder / LETTER_FILE).read_text(encoding="utf-8"))

    recipient = {k: "" for k in ("company", "department", "contact", "street", "city", "country")}
    recipient.update(data.get("recipient", {}))

    letter = {"subject": "", "reference": "", "salutation": "Hiring Team", "body": "",
              "closing": "Kind regards,", "enclosures": []}
    letter.update(data.get("letter", {}))
    letter["paragraphs"] = format_paragraphs(letter["body"])
    letter["salutation"] = letter["salutation"].strip().rstrip(",")

    date = (data.get("date") or "").strip()
    if not date:
        today = dt.date.today()
        date = f"{today.day} {today.strftime('%B')} {today.year}"

    return {
        "sender": sender,
        "recipient": recipient,
        "letter": letter,
        "date": date,
        "place": (data.get("place") or "").strip() or sender.get("place", ""),
        "file_label": (data.get("file_label") or "").strip(),
    }


def output_path(folder: Path, ctx: dict, signed: bool) -> Path:
    label = ctx["file_label"] or folder.resolve().name
    suffix = "" if signed else "_without-signature"
    return folder / f"letter-of-motivation_{label}_{ctx['sender']['file_name_suffix']}{suffix}.pdf"


def find_signature() -> str:
    for name in SIGNATURE_FILES:
        if (TEMPLATE_DIR / name).is_file():
            return name
    raise FileNotFoundError(
        f"--signed needs a signature file: put it at {TEMPLATE_DIR / SIGNATURE_FILES[0]} "
        f"or {TEMPLATE_DIR / SIGNATURE_FILES[1]}")


def init_letter(folder: Path) -> Path:
    target = folder / LETTER_FILE
    company = folder.resolve().name
    text = (TEMPLATE_DIR / LETTER_FILE).read_text(encoding="utf-8")
    text = text.replace("Company Name", company)
    target.write_text(text, encoding="utf-8")
    return target


# --------------------------------------------------------------- build --------

def build(folder: Path, signed: bool = False) -> dict:
    """Render the PDF. Returns a status dict (ok, pages, pdf, message)."""
    from weasyprint import HTML  # imported lazily: slow import

    ctx = load_context(folder)
    ctx["signature"] = find_signature() if signed else None
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), undefined=StrictUndefined,
                      autoescape=select_autoescape(["html", "j2"]))
    rendered = env.get_template("letter.html.j2").render(**ctx)

    document = HTML(string=rendered, base_url=str(TEMPLATE_DIR) + "/").render()
    pdf = output_path(folder, ctx, signed)
    document.write_pdf(pdf)
    pages = len(document.pages)
    return {"ok": True, "pages": pages, "pdf": str(pdf),
            "message": "" if pages == 1 else f"Letter is {pages} pages long. It should fit on one page."}


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


def safe_build(folder: Path, signed: bool = False) -> dict:
    try:
        return build(folder, signed)
    except tomllib.TOMLDecodeError as e:
        return {"ok": False, "pages": 0, "pdf": "", "message": f"{LETTER_FILE}: {e}"}
    except Exception as e:  # show any template/data error instead of crashing watch mode
        return {"ok": False, "pages": 0, "pdf": "", "message": f"{type(e).__name__}: {e}"}


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
    images = []
    if status["ok"] and shutil.which("pdftoppm"):
        for old in preview_dir.glob("page-*.png"):
            old.unlink()
        subprocess.run(["pdftoppm", "-png", "-r", "160", status["pdf"], str(preview_dir / "page")],
                       check=False)
        images = sorted(p.name for p in preview_dir.glob("page-*.png"))
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
    return [folder / LETTER_FILE, *(p for p in TEMPLATE_DIR.rglob("*") if p.is_file())]


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
    parser.add_argument("folder", help="application folder, e.g. ~/GoogleDrive/Bewerbungen/STARK")
    parser.add_argument("--signed", action="store_true",
                        help="insert the signature from template/signature.svg or .png")
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
