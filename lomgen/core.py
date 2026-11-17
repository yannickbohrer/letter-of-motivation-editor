"""Rendering core shared by the CLI and the desktop app.

letter.toml (per application folder) + sender.toml (your details) -> Jinja2 HTML -> WeasyPrint PDF.
"""

from __future__ import annotations

import datetime as dt
import html
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "template"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "letter-of-motivation-generator"

LETTER_FILE = "letter.toml"
SENDER_FILE = "sender.toml"
SIGNATURE_FILES = ("signature.svg", "signature.png")  # first match wins, CONFIG_DIR before TEMPLATE_DIR

# Blocks of letter.html.j2 (by CSS class) that the app can point at.
BLOCKS = ("recipient", "date", "subject", "salutation", "body", "sign-off", "enclosures")


# ---------------------------------------------------------------- paths --------

def sender_path() -> Path:
    """Your details: ~/.config/letter-of-motivation-generator/sender.toml, else template/sender.toml."""
    user = CONFIG_DIR / SENDER_FILE
    return user if user.is_file() else TEMPLATE_DIR / SENDER_FILE


def find_signature(required: bool = True) -> Path | None:
    for directory in (CONFIG_DIR, TEMPLATE_DIR):
        for name in SIGNATURE_FILES:
            if (directory / name).is_file():
                return directory / name
    if not required:
        return None
    raise FileNotFoundError(
        f"No signature file. Put signature.svg or signature.png (transparent background) "
        f"in {CONFIG_DIR} or {TEMPLATE_DIR}.")


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


def today() -> str:
    d = dt.date.today()
    return f"{d.day} {d.strftime('%B')} {d.year}"


def load_sender() -> dict:
    return tomllib.loads(sender_path().read_text(encoding="utf-8"))


def load_context(folder: Path) -> dict:
    sender = load_sender()
    data = tomllib.loads((folder / LETTER_FILE).read_text(encoding="utf-8"))

    recipient = {k: "" for k in ("company", "department", "contact", "street", "city", "country")}
    recipient.update(data.get("recipient", {}))

    letter = {"subject": "", "reference": "", "salutation": "Hiring Team", "body": "",
              "closing": "Kind regards,", "enclosures": []}
    letter.update(data.get("letter", {}))
    letter["paragraphs"] = format_paragraphs(letter["body"])
    letter["salutation"] = letter["salutation"].strip().rstrip(",")

    return {
        "sender": sender,
        "recipient": recipient,
        "letter": letter,
        "date": (data.get("date") or "").strip() or today(),
        "place": (data.get("place") or "").strip() or sender.get("place", ""),
        "file_label": (data.get("file_label") or "").strip(),
    }


def pdf_name(folder: Path, file_label: str, sender: dict, signed: bool) -> str:
    label = file_label or folder.resolve().name
    suffix = "" if signed else "_without-signature"
    return f"letter-of-motivation_{label}_{sender['file_name_suffix']}{suffix}.pdf"


def output_path(folder: Path, ctx: dict, signed: bool) -> Path:
    return folder / pdf_name(folder, ctx["file_label"], ctx["sender"], signed)


def init_letter(folder: Path) -> Path:
    target = folder / LETTER_FILE
    company = folder.resolve().name
    text = (TEMPLATE_DIR / LETTER_FILE).read_text(encoding="utf-8")
    text = text.replace("Company Name", company)
    target.write_text(text, encoding="utf-8")
    return target


# --------------------------------------------------------------- build --------

def _walk(box):
    yield box
    for child in getattr(box, "children", ()):
        yield from _walk(child)


def layout_info(document) -> dict:
    """Where things landed, in CSS px (96 per inch), for the app's page-fill gauge and block outlines.

    fill: how far down the content area the letter reaches; 1.0 = exactly one full page, >1 = overflow.
    lines_over: roughly how many body lines must go for the letter to fit on one page (0 if it fits).
    blocks: {css class: [(page index, x, y, width, height), ...]} (a block split across pages has several).
    """
    blocks: dict[str, list[tuple]] = {}
    first = document.pages[0]._page_box
    content_y, content_h = first.content_box_y(), first.height
    line_h = 11 * 96 / 72 * 1.45

    for index, page in enumerate(document.pages):
        for box in _walk(page._page_box):
            element = getattr(box, "element", None)
            if element is None:
                continue
            classes = (element.get("class") or "").split()
            for name in BLOCKS:
                if name in classes and type(box).__name__ == "BlockBox":
                    rect = (index, box.border_box_x(), box.border_box_y(), box.border_width(), box.border_height())
                    if rect not in blocks.setdefault(name, []):
                        blocks[name].append(rect)
            if "body" in classes and box.element_tag == "div":
                line = next((b for b in _walk(box) if type(b).__name__ == "LineBox"), None)
                if line is not None:
                    line_h = line.height

    # Bottom of the letter's content on each page (the enclosures line lives in the footer margin).
    bottoms = [0.0] * len(document.pages)
    for name, rects in blocks.items():
        if name != "enclosures":
            for index, _x, y, _w, h in rects:
                bottoms[index] = max(bottoms[index], y + h - content_y)

    if len(bottoms) == 1:
        fill, lines_over = bottoms[0] / content_h, 0
    else:
        spill = sum(bottoms[1:]) - (content_h - bottoms[0])   # content beyond what page 1 has room for
        fill = 1 + max(spill, 0) / content_h
        lines_over = max(1, round(spill / line_h + 0.49))

    return {"fill": fill, "lines_over": lines_over, "blocks": blocks,
            "page_size": (first.margin_width(), first.margin_height()),
            "content": (first.content_box_x(), content_y, first.width, content_h)}


def build(folder: Path, signed: bool = False, pdf_path: Path | None = None) -> dict:
    """Render the PDF (to output_path, or to pdf_path for previews). Returns a status dict."""
    from weasyprint import HTML  # imported lazily: slow import

    ctx = load_context(folder)
    ctx["signature"] = find_signature().as_uri() if signed else None
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), undefined=StrictUndefined,
                      autoescape=select_autoescape(["html", "j2"]))
    rendered = env.get_template("letter.html.j2").render(**ctx)

    document = HTML(string=rendered, base_url=str(TEMPLATE_DIR) + "/").render()
    pdf = pdf_path or output_path(folder, ctx, signed)
    document.write_pdf(pdf)
    pages = len(document.pages)
    return {"ok": True, "pages": pages, "pdf": str(pdf), "layout": layout_info(document),
            "message": "" if pages == 1 else f"Letter is {pages} pages long. It should fit on one page."}


def safe_build(folder: Path, signed: bool = False, pdf_path: Path | None = None) -> dict:
    try:
        return build(folder, signed, pdf_path)
    except tomllib.TOMLDecodeError as e:
        return {"ok": False, "pages": 0, "pdf": "", "layout": None, "message": f"{LETTER_FILE}: {e}"}
    except Exception as e:  # show any template/data error instead of crashing
        return {"ok": False, "pages": 0, "pdf": "", "layout": None, "message": f"{type(e).__name__}: {e}"}


def render_pages(pdf: str | Path, out_dir: Path, dpi: int = 160) -> list[Path]:
    """PDF -> one PNG per page via pdftoppm (poppler-utils). Returns [] if pdftoppm is missing."""
    if not shutil.which("pdftoppm"):
        return []
    for old in out_dir.glob("page-*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(out_dir / "page")], check=False)
    return sorted(out_dir.glob("page-*.png"))
