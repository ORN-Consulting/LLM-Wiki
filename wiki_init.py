#!/usr/bin/env python3
"""
LLM Wiki initialization helper.

Creates the wiki folder structure for an existing project or Obsidian vault
without modifying the project's current source folders.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


RAW_FOLDER_HINTS = ("raw", "inbox", "reference", "references", "sources")


def find_raw_folders(base: Path) -> list[Path]:
    """Find plausible raw-source folders at the project root."""
    found: list[Path] = []
    if not base.is_dir():
        return found

    for item in sorted(base.iterdir()):
        if not item.is_dir():
            continue
        normalized = item.name.casefold()
        if any(hint in normalized for hint in RAW_FOLDER_HINTS):
            found.append(item)
    return found


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def create_index_content(title: str, today: str) -> str:
    safe_title = escape_yaml(title)
    return f"""---
title: "{safe_title} Index"
last_updated: {today}
---

# {title}

This file is the catalog for the wiki. Keep one-line summaries for each page.

## Sources
- _(none yet)_

## Entities
- _(none yet)_

## Topics
- _(none yet)_

## Analysis
- _(none yet)_
"""


def create_log_content(title: str, today: str) -> str:
    safe_title = escape_yaml(title)
    return f"""---
title: "{safe_title} Log"
---

# Work Log

## [{today}] init | Wiki bootstrap
- Created wiki structure.
- Created `wiki/index.md` and `wiki/log.md`.
- Next step: create `CLAUDE.md` from `schema-template.md`.
"""


def create_wiki_structure(target: str, title: str = "LLM Wiki") -> int:
    base = Path(target).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        print(f"Error: target folder does not exist: {target}")
        return 1

    wiki = base / "wiki"
    today = date.today().isoformat()

    created_items: list[str] = []
    for directory in (
        wiki / "sources",
        wiki / "entities",
        wiki / "topics",
        wiki / "analysis",
    ):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_items.append(str(directory.relative_to(base)))

    index_path = wiki / "index.md"
    if not index_path.exists():
        index_path.write_text(create_index_content(title, today), encoding="utf-8")
        created_items.append(str(index_path.relative_to(base)))

    log_path = wiki / "log.md"
    if not log_path.exists():
        log_path.write_text(create_log_content(title, today), encoding="utf-8")
        created_items.append(str(log_path.relative_to(base)))

    raw_candidates = find_raw_folders(base)
    raw_note: str
    if raw_candidates:
        raw_note = "Using existing raw-source folders: " + ", ".join(
            str(path.relative_to(base)) for path in raw_candidates
        )
    else:
        raw_dir = base / "raw"
        if not raw_dir.exists():
            raw_dir.mkdir(exist_ok=True)
            created_items.append(str(raw_dir.relative_to(base)))
        raw_note = "Created `raw/` for immutable source documents."

    print("=== LLM Wiki initialized ===")
    print(f"Target: {base}")
    print(f"Title: {title}")
    print()

    if created_items:
        print("Created:")
        for item in created_items:
            print(f"  + {item}")
    else:
        print("No files were created. Existing structure was kept as-is.")

    print()
    print(raw_note)
    print()
    print("Next steps:")
    print("  1. Create `CLAUDE.md` from `schema-template.md`.")
    print("  2. Add a source file and run an ingest workflow.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize an LLM Wiki structure.")
    parser.add_argument("target", help="Target folder for the wiki structure")
    parser.add_argument("--title", default="LLM Wiki", help="Human-readable wiki title")
    args = parser.parse_args()
    return create_wiki_structure(args.target, args.title)


if __name__ == "__main__":
    sys.exit(main())
