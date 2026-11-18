#!/usr/bin/env bash
# Remove the Letter of Motivation desktop app. Your settings, details and signature in
# ~/.config/letter-of-motivation-editor and your letters are left alone.
set -euo pipefail

APP_ID="io.github.yannickbohrer.LetterOfMotivation"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"

rm -rf "$DATA/letter-of-motivation-editor"
rm -f "$HOME/.local/bin/letter-of-motivation" \
      "$DATA/applications/$APP_ID.desktop" \
      "$DATA/icons/hicolor/scalable/apps/$APP_ID.svg"
update-desktop-database "$DATA/applications" 2>/dev/null || true
gtk-update-icon-cache -q -t -f "$DATA/icons/hicolor" 2>/dev/null || true

echo "Removed. Settings kept in ${XDG_CONFIG_HOME:-$HOME/.config}/letter-of-motivation-editor"
