# Letter of Motivation

Write one-page A4 application letters and export them as PDF. Each application has its own folder
(for example `~/Applications/ACME`) with a `letter.toml` holding that letter's text.

There are two ways to use it: a GNOME desktop app and a command-line tool. Both use the same template
(`template/`) and the same rendering code (`lomgen/core.py`).

## Desktop app

- **Applications list**: one row per folder in your applications folder. Each row shows whether that
  letter has been exported and how many pages it has.
- **Editor**: the fields are in the same order as on the page. Changes save to `letter.toml` as you
  type, and the comments in the file are kept.
- **Page**: the page updates as you type. The bar on its right edge shows how much of the page the
  letter fills, and turns red if the letter runs onto a second page. Click a part of the page to
  jump to its field.

### Install

```sh
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-venv poppler-utils
./install.sh
```

Then open **Letter of Motivation** from Activities, or run `letter-of-motivation [folder]`.
The installer puts the app in `~/.local/share/letter-of-motivation-generator`, the launcher in
`~/.local/bin`, and the menu entry and icon in `~/.local/share`. It needs no sudo.

- **Update**: `git pull && ./install.sh`
- **Uninstall**: `./uninstall.sh` (your settings and letters stay)

### Your details

Your name, default place, file-name suffix and signature are set under Preferences. They are stored
in `~/.config/letter-of-motivation-generator/` (`sender.toml`, `signature.svg` or `.png`), and the CLI
uses them too. If that folder doesn't exist, both fall back to `template/`.

### Run from the repository (development)

```sh
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m lomgen
```

## Command line

```sh
python3 create_letter-of-motivation.py <folder>            # PDF without signature
python3 create_letter-of-motivation.py <folder> --signed   # with signature
python3 create_letter-of-motivation.py <folder> --watch    # rebuild on save + browser preview
```

The first run on a folder without `letter.toml` creates one from `template/letter.toml`.

## License

[MIT](LICENSE) © 2026 Yannick Bohrer

The bundled Roboto fonts in `template/fonts/` are licensed under the Apache License 2.0
(see [`template/fonts/LICENSE-Roboto.txt`](template/fonts/LICENSE-Roboto.txt)).
