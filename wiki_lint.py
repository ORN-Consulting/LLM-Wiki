#!/usr/bin/env python3
"""
LLM Wiki lint helper.

Checks structural integrity of a markdown wiki before a deeper LLM review.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*", re.DOTALL)
CODE_BLOCK_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
SKIP_NAMES = {"index.md", "log.md", "readme.md", "_readme.md", "claude.md"}
CONTENT_DIRS = ("sources", "entities", "topics", "analysis")


@dataclass
class PageRecord:
    path: Path
    rel_path: str
    stem: str
    content: str
    frontmatter: dict[str, Any]
    wikilinks: list[str]


def read_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def find_md_files(wiki_path: Path) -> list[Path]:
    return sorted(path for path in wiki_path.rglob("*.md") if path.is_file())


def strip_code(content: str) -> str:
    without_blocks = CODE_BLOCK_RE.sub("", content)
    return INLINE_CODE_RE.sub("", without_blocks)


def extract_wikilinks(content: str) -> list[str]:
    return WIKILINK_RE.findall(strip_code(content))


def extract_frontmatter(content: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}
    raw = match.group(1)

    if YAML_AVAILABLE:
        try:
            loaded = _yaml.safe_load(raw)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass

    frontmatter: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    return frontmatter


def normalize_link(link: str) -> str:
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def parse_date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def body_without_frontmatter(content: str) -> str:
    return FRONTMATTER_RE.sub("", content, count=1).strip()


def build_records(wiki_path: Path) -> list[PageRecord]:
    records: list[PageRecord] = []
    for path in find_md_files(wiki_path):
        rel_path = path.relative_to(wiki_path).as_posix()
        content = read_file(path)
        records.append(
            PageRecord(
                path=path,
                rel_path=rel_path,
                stem=path.stem,
                content=content,
                frontmatter=extract_frontmatter(content),
                wikilinks=extract_wikilinks(content),
            )
        )
    return records


def count_content_pages(records: list[PageRecord], dirname: str) -> int:
    prefix = f"{dirname}/"
    return sum(1 for record in records if record.rel_path.startswith(prefix))


def is_skipped(record: PageRecord) -> bool:
    return record.rel_path.casefold() in SKIP_NAMES


def resolve_link_target(
    source: PageRecord,
    link: str,
    by_rel_path: dict[str, PageRecord],
    by_stem: dict[str, list[PageRecord]],
) -> tuple[str | None, str | None]:
    """Return (resolved_rel_path, issue_code)."""
    normalized = normalize_link(link)
    if not normalized:
        return None, None

    direct_md = normalized if normalized.endswith(".md") else f"{normalized}.md"
    direct_md = direct_md.replace("\\", "/")
    if direct_md in by_rel_path:
        return direct_md, None

    if normalized in by_rel_path:
        return normalized, None

    stem = Path(normalized).stem
    matches = by_stem.get(stem, [])
    if len(matches) == 1:
        return matches[0].rel_path, None
    if len(matches) > 1:
        return None, "ambiguous"
    return None, "missing"


def run_lint(wiki_path_str: str) -> dict[str, Any]:
    wiki_path = Path(wiki_path_str).expanduser().resolve()
    if not wiki_path.exists() or not wiki_path.is_dir():
        return {"error": f"Wiki folder does not exist: {wiki_path_str}"}

    records = build_records(wiki_path)
    if not records:
        return {"error": f"No markdown files found under: {wiki_path_str}"}

    by_rel_path = {record.rel_path: record for record in records}
    by_stem: dict[str, list[PageRecord]] = {}
    for record in records:
        by_stem.setdefault(record.stem, []).append(record)

    inbound: dict[str, list[str]] = {record.rel_path: [] for record in records}
    missing_links: list[dict[str, str]] = []
    ambiguous_links: list[dict[str, Any]] = []

    for record in records:
        for raw_link in record.wikilinks:
            resolved, issue = resolve_link_target(record, raw_link, by_rel_path, by_stem)
            if resolved:
                inbound[resolved].append(record.rel_path)
                continue
            if issue == "ambiguous":
                ambiguous_links.append(
                    {
                        "link": normalize_link(raw_link),
                        "referenced_by": record.rel_path,
                        "candidates": [candidate.rel_path for candidate in by_stem.get(Path(normalize_link(raw_link)).stem, [])],
                    }
                )
            elif issue == "missing":
                missing_links.append(
                    {
                        "link": normalize_link(raw_link),
                        "referenced_by": record.rel_path,
                    }
                )

    cutoff = date.today() - timedelta(days=90)
    orphan_pages: list[str] = []
    weak_pages: list[dict[str, Any]] = []
    stale_pages: list[dict[str, str]] = []
    duplicate_stems = {
        stem: sorted(record.rel_path for record in matched)
        for stem, matched in by_stem.items()
        if len(matched) > 1
    }

    for record in records:
        if not is_skipped(record) and not inbound[record.rel_path]:
            orphan_pages.append(record.rel_path)

        if record.rel_path.startswith(("entities/", "topics/")):
            body_length = len(body_without_frontmatter(record.content))
            if body_length < 200:
                weak_pages.append({"page": record.rel_path, "body_length": body_length})

        if not is_skipped(record):
            last_updated = parse_date_value(record.frontmatter.get("last_updated"))
            if last_updated and last_updated < cutoff:
                stale_pages.append(
                    {"page": record.rel_path, "last_updated": last_updated.isoformat()}
                )

    index_sync: list[str] = []
    index_record = by_rel_path.get("index.md")
    if index_record:
        indexed_targets: set[str] = set()
        for raw_link in index_record.wikilinks:
            resolved, issue = resolve_link_target(index_record, raw_link, by_rel_path, by_stem)
            if resolved:
                indexed_targets.add(resolved)
            elif issue == "ambiguous":
                ambiguous_links.append(
                    {
                        "link": normalize_link(raw_link),
                        "referenced_by": index_record.rel_path,
                        "candidates": [candidate.rel_path for candidate in by_stem.get(Path(normalize_link(raw_link)).stem, [])],
                    }
                )
        for record in records:
            if is_skipped(record):
                continue
            if record.rel_path not in indexed_targets:
                index_sync.append(record.rel_path)

    avg_links = round(
        sum(len(record.wikilinks) for record in records) / max(len(records), 1),
        1,
    )

    results: dict[str, Any] = {
        "stats": {
            "total_pages": len(records),
            "total_sources": count_content_pages(records, "sources"),
            "total_entities": count_content_pages(records, "entities"),
            "total_topics": count_content_pages(records, "topics"),
            "total_analyses": count_content_pages(records, "analysis"),
            "avg_links_per_page": avg_links,
            "yaml_parser": "pyyaml" if YAML_AVAILABLE else "builtin-regex",
        },
        "duplicate_stems": duplicate_stems,
        "orphan_pages": sorted(orphan_pages),
        "missing_links": missing_links,
        "ambiguous_links": ambiguous_links,
        "weak_pages": sorted(weak_pages, key=lambda item: item["page"]),
        "stale_pages": sorted(stale_pages, key=lambda item: item["page"]),
        "index_sync": sorted(index_sync),
        "notes": [],
    }

    results["notes"].append(
        "Structural lint covers duplicate names, broken links, orphan pages, weak pages, stale pages, and index drift."
    )
    results["notes"].append(
        "Semantic contradiction checks still require an LLM pass over the relevant pages."
    )
    if not YAML_AVAILABLE:
        results["notes"].append(
            "Install PyYAML for more accurate frontmatter parsing: `pip install pyyaml`."
        )

    return results


def format_report(results: dict[str, Any]) -> str:
    if "error" in results:
        return f"Error: {results['error']}"

    stats = results["stats"]
    lines = [
        f"## [{date.today().isoformat()}] lint | Wiki health check",
        "",
        "### Stats",
        f"- Total pages: {stats['total_pages']}",
        f"- Sources: {stats['total_sources']}",
        f"- Entities: {stats['total_entities']}",
        f"- Topics: {stats['total_topics']}",
        f"- Analysis pages: {stats['total_analyses']}",
        f"- Average wikilinks per page: {stats['avg_links_per_page']}",
        f"- Frontmatter parser: {stats['yaml_parser']}",
    ]

    if results["duplicate_stems"]:
        lines.append("")
        lines.append(f"### Duplicate stems ({len(results['duplicate_stems'])})")
        for stem, paths in sorted(results["duplicate_stems"].items()):
            lines.append(f"- `{stem}` -> {', '.join(f'`{path}`' for path in paths)}")

    if results["orphan_pages"]:
        lines.append("")
        lines.append(f"### Orphan pages ({len(results['orphan_pages'])})")
        for rel_path in results["orphan_pages"]:
            lines.append(f"- `{rel_path}`")

    if results["missing_links"]:
        lines.append("")
        lines.append(f"### Missing links ({len(results['missing_links'])})")
        for item in results["missing_links"]:
            lines.append(f"- `[[{item['link']}]]` referenced by `{item['referenced_by']}`")

    if results["ambiguous_links"]:
        lines.append("")
        lines.append(f"### Ambiguous links ({len(results['ambiguous_links'])})")
        for item in results["ambiguous_links"]:
            candidates = ", ".join(f"`{path}`" for path in item["candidates"])
            lines.append(
                f"- `[[{item['link']}]]` in `{item['referenced_by']}` matches multiple pages: {candidates}"
            )

    if results["weak_pages"]:
        lines.append("")
        lines.append(f"### Weak pages ({len(results['weak_pages'])})")
        for item in results["weak_pages"]:
            lines.append(f"- `{item['page']}` body length: {item['body_length']}")

    if results["stale_pages"]:
        lines.append("")
        lines.append(f"### Stale pages ({len(results['stale_pages'])})")
        for item in results["stale_pages"]:
            lines.append(f"- `{item['page']}` last_updated: {item['last_updated']}")

    if results["index_sync"]:
        lines.append("")
        lines.append(f"### Missing from index ({len(results['index_sync'])})")
        for rel_path in results["index_sync"]:
            lines.append(f"- `{rel_path}`")

    issue_sections = (
        results["duplicate_stems"],
        results["orphan_pages"],
        results["missing_links"],
        results["ambiguous_links"],
        results["weak_pages"],
        results["stale_pages"],
        results["index_sync"],
    )
    if not any(issue_sections):
        lines.extend(["", "### Status", "- No structural issues detected."])

    if results["notes"]:
        lines.append("")
        lines.append("### Notes")
        for note in results["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python wiki_lint.py <wiki_folder_path>")
        return 1

    wiki_path = sys.argv[1]
    results = run_lint(wiki_path)
    json_path = Path(wiki_path).expanduser().resolve().parent / "_lint_result.json"

    try:
        json_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        json_note = str(json_path)
    except Exception as exc:
        json_note = f"JSON output failed: {exc}"

    print(format_report(results))
    print(f"\n(JSON: {json_note})")
    return 0 if "error" not in results else 1


if __name__ == "__main__":
    sys.exit(main())
