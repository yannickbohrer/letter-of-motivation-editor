#!/usr/bin/env bash
# Install (or update) the Letter of Motivation desktop app for the current user. No sudo needed.
#
#   ./install.sh      run again after `git pull` to update
#   ./uninstall.sh    removes the app, keeps your settings in ~/.config/letter-of-motivation-editor
set -euo pipefail

APP_ID="io.github.yannickbohrer.LetterOfMotivation"
SRC="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA/letter-of-motivation-editor"
BINDIR="$HOME/.local/bin"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/letter-of-motivation-editor"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

# ---- migrate from the old project name (letter-of-motivation-generator)
OLD_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/letter-of-motivation-generator"
if [ -d "$OLD_CONFIG" ] && [ ! -e "$CONFIG" ]; then
  say "Moving settings to $CONFIG"
  mv "$OLD_CONFIG" "$CONFIG"
fi
rm -rf "$DATA/letter-of-motivation-generator"

# ---- system packages (apt) the app needs
missing=()
python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' 2>/dev/null \
  || missing+=(python3-gi gir1.2-gtk-4.0 gir1.2-adw-1)
python3 -m venv --help >/dev/null 2>&1 || missing+=(python3-venv)
command -v pdftoppm >/dev/null || missing+=(poppler-utils)
command -v pdfinfo >/dev/null || missing+=(poppler-utils)
if ((${#missing[@]})); then
  echo "Missing system packages. Install them first:"
  echo "  sudo apt install $(printf '%s\n' "${missing[@]}" | sort -u | tr '\n' ' ')"
  exit 1
fi

# ---- app files
say "Installing to $DEST"
mkdir -p "$DEST"
rm -rf "$DEST/lomgen" "$DEST/template"
cp -r "$SRC/lomgen" "$SRC/template" "$DEST/"
cp "$SRC/create_letter-of-motivation.py" "$SRC/requirements.txt" "$DEST/"
rm -f "$DEST/template/signature.svg" "$DEST/template/signature.png"   # personal: lives in $CONFIG
find "$DEST" -name __pycache__ -type d -prune -exec rm -rf {} +

# ---- Python environment (system PyGObject + pip packages from requirements.txt)
if [ ! -x "$DEST/.venv/bin/python" ]; then
  say "Creating Python environment"
  python3 -m venv --system-site-packages "$DEST/.venv"
fi
"$DEST/.venv/bin/pip" install --quiet --disable-pip-version-check -r "$DEST/requirements.txt"

# ---- launcher, menu entry, icon
mkdir -p "$BINDIR" "$DATA/applications" "$DATA/icons/hicolor/scalable/apps"
cat > "$BINDIR/letter-of-motivation" <<EOF
#!/bin/sh
PYTHONPATH="$DEST" exec "$DEST/.venv/bin/python" -m lomgen "\$@"
EOF
chmod +x "$BINDIR/letter-of-motivation"
sed "s|@BINDIR@|$BINDIR|g" "$SRC/data/$APP_ID.desktop" > "$DATA/applications/$APP_ID.desktop"
cp "$SRC/data/icons/$APP_ID.svg" "$DATA/icons/hicolor/scalable/apps/$APP_ID.svg"
update-desktop-database "$DATA/applications" 2>/dev/null || true
gtk-update-icon-cache -q -t -f "$DATA/icons/hicolor" 2>/dev/null || true

# ---- your details: copied once, never overwritten
mkdir -p "$CONFIG"
[ -f "$CONFIG/sender.toml" ] || cp "$SRC/template/sender.toml" "$CONFIG/sender.toml"
if [ ! -f "$CONFIG/signature.svg" ] && [ ! -f "$CONFIG/signature.png" ]; then
  for f in signature.svg signature.png; do
    if [ -f "$SRC/template/$f" ]; then cp "$SRC/template/$f" "$CONFIG/$f"; break; fi
  done
fi

say "Done. Open “Letter of Motivation” from Activities, or run: letter-of-motivation [folder]"
case ":$PATH:" in *":$BINDIR:"*) ;; *) echo "Note: $BINDIR is not on your PATH (the Activities entry works anyway).";; esac
