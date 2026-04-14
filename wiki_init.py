#!/usr/bin/env python3
"""
LLM Wiki initialization helper.

Creates the wiki folder structure for an existing project or Obsidian vault
without modifying the project's current source folders.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


RAW_FOLDER_HINTS = ("raw", "inbox", "reference", "references", "sources")


def find_raw_folders(base: Path) -> list[Path]:
    """Find plausible raw-source folders at the project root."""
    found = []
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
    safe = escape_yaml(title)
    return (
        '---\ntitle: "%s Index"\nlast_updated: %s\n---\n\n'
        '# %s\n\n'
        'This file is the catalog for the wiki. Keep one-line summaries for each page.\n\n'
        '## Sources\n- _(none yet)_\n\n'
        '## Entities\n- _(none yet)_\n\n'
        '## Topics\n- _(none yet)_\n\n'
        '## Analysis\n- _(none yet)_\n'
    ) % (safe, today, title)


def create_log_content(title: str, today: str) -> str:
    safe = escape_yaml(title)
    return (
        '---\ntitle: "%s Log"\n---\n\n'
        '# Work Log\n\n'
        '## [%s] init | Wiki bootstrap\n'
        '- Created wiki structure.\n'
        '- Created `wiki/index.md` and `wiki/log.md`.\n'
        '- Next step: create `CLAUDE.md` from `schema-template.md`.\n'
    ) % (safe, today)


def create_wiki_structure(target: str, title: str = "LLM Wiki") -> int:
    base = Path(target).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        print("Error: target folder does not exist: %s" % target)
        return 1

    wiki = base / "wiki"
    today = date.today().isoformat()

    created_items = []
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

    # Operational JSON files for LINT/QUERY token optimization
    summary_index_path = wiki / "_summary-index.json"
    if not summary_index_path.exists():
        summary_index_path.write_text(
            json.dumps({"pages": [], "last_updated": today}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created_items.append(str(summary_index_path.relative_to(base)))

    last_lint_path = wiki / "_last-lint.json"
    if not last_lint_path.exists():
        last_lint_path.write_text(
            json.dumps({"last_lint": None, "scope": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created_items.append(str(last_lint_path.relative_to(base)))

    lint_cache_path = wiki / "_lint-cache.json"
    if not lint_cache_path.exists():
        lint_cache_path.write_text(
            json.dumps({"checked_pairs": [], "last_updated": today}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created_items.append(str(lint_cache_path.relative_to(base)))

    raw_candidates = find_raw_folders(base)
    if raw_candidates:
        raw_note = "Using existing raw-source folders: " + ", ".join(
            str(p.relative_to(base)) for p in raw_candidates
        )
    else:
        raw_dir = base / "raw"
        if not raw_dir.exists():
            raw_dir.mkdir(exist_ok=True)
            created_items.append(str(raw_dir.relative_to(base)))
        raw_note = "Created `raw/` for immutable source documents."

    print("=== LLM Wiki initialized ===")
    print("Target: %s" % base)
    print("Title: %s" % title)
    print()
    if created_items:
        print("Created:")
        for item in created_items:
            print("  + %s" % item)
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
