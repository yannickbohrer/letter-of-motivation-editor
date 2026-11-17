"""Read and write TOML files without losing the comments and layout you wrote by hand (tomlkit)."""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit.items import Table

# The fields the editor shows, as (table or None for top level, key).
FIELDS = (
    ("recipient", "company"), ("recipient", "department"), ("recipient", "contact"),
    ("recipient", "street"), ("recipient", "city"), ("recipient", "country"),
    (None, "place"), (None, "date"),
    ("letter", "subject"), ("letter", "reference"), ("letter", "salutation"),
    ("letter", "body"), ("letter", "closing"), ("letter", "enclosures"),
    (None, "file_label"),
)


def _plain(value):
    return value.unwrap() if hasattr(value, "unwrap") else value


class TomlFile:
    """A TOML file you change key by key; save() writes only if something changed."""

    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8") if path.exists() else ""
        self.doc = tomlkit.parse(self.text)   # raises tomlkit.exceptions.ParseError on bad TOML

    def table(self, name: str | None, create: bool = False):
        if name is None:
            return self.doc
        if name not in self.doc and create:
            self.doc.add(tomlkit.nl())
            self.doc.add(name, tomlkit.table())
        return self.doc.get(name)

    def get(self, table: str | None, key: str, default=""):
        t = self.table(table)
        return _plain(t.get(key, default)) if t is not None else default

    def set(self, table: str | None, key: str, value) -> None:
        if self.get(table, key, None) == value:
            return
        t = self.table(table, create=True)
        if isinstance(value, str) and ("\n" in value or key == "body"):
            # Write body = """<newline>text<newline>""" like the template does (TOML drops the first newline).
            escaped = value.replace("\\", "\\\\").replace('"""', '""\\"')
            item = tomlkit.parse(f'x = """\n{escaped}\n"""\n')["x"]
        elif isinstance(value, list):
            item = tomlkit.array()
            item.extend(value)
        else:
            item = value
        if isinstance(t, Table) or t is self.doc:
            t[key] = item

    def save(self) -> bool:
        text = tomlkit.dumps(self.doc)
        if text == self.text:
            return False
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self.path)          # atomic: Drive sync / file watchers never see half a file
        self.text = text
        return True


def read_letter(folder: Path) -> tuple[TomlFile, dict]:
    """Returns the file and {"table.key" or "key": value} for every editor field."""
    f = TomlFile(folder / "letter.toml")
    values = {}
    for table, key in FIELDS:
        default = [] if key == "enclosures" else ""
        value = f.get(table, key, default)
        if key == "body":
            value = value.strip("\n")
        values[f"{table}.{key}" if table else key] = value
    return f, values


def write_letter(f: TomlFile, values: dict) -> bool:
    for table, key in FIELDS:
        name = f"{table}.{key}" if table else key
        if name not in values:
            continue
        value = values[name]
        if key == "body":
            current = f.get(table, key, "")
            if current.strip("\n") == value.strip("\n"):
                continue
            value = value.strip("\n")
        f.set(table, key, value)
    return f.save()
