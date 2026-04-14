#!/usr/bin/env python3
"""
LLM Wiki lint helper.

Checks structural integrity of a markdown wiki before a deeper LLM review.
Includes Layer 1 semantic candidate extraction for the 2-layer lint architecture.
"""

from __future__ import annotations

import json
import re
import sys
import argparse
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
FRONTMATTER_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*", re.DOTALL)
CODE_BLOCK_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
YEAR_NUMBER_RE = re.compile(
    r"((?:19|20)\d{2})\D{0,10}?([\d,.]+\s*[\uC5B5\uB9CC\uC870\uCC9C\uBC31\uC6D0%\uAC1C\uAC74\uBA85])"
)
SKIP_NAMES = {"index.md", "log.md", "readme.md", "_readme.md", "claude.md"}
CONTENT_DIRS = ("sources", "entities", "topics", "analysis")
SEMANTIC_DIRS = ("entities", "topics")
LEVENSHTEIN_RATIO_THRESHOLD = 0.4
DEFAULT_LEVEL = "standard"
VALID_LEVELS = ("light", "standard", "deep")
ENTITY_HINTS = ("설립", "대표", "소재지", "본사", "창업", "CEO", "주소", "기관", "회사")
TOPIC_HINTS = ("동향", "트렌드", "방법론", "전략", "이슈", "규제", "시장", "개요", "배경")
LOG_HEADING_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] ([^|]+)\|", re.MULTILINE)
LOG_PATH_LINE_RE = re.compile(r"^- (?:Created|Updated|생성|갱신):\s+(.+)$", re.MULTILINE)


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


@dataclass
class PageRecord:
    path: Path
    rel_path: str
    stem: str
    content: str
    frontmatter: dict[str, Any]
    wikilinks: list[str]


def read_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def find_md_files(wiki_path: Path) -> list[Path]:
    return sorted(p for p in wiki_path.rglob("*.md") if p.is_file())


def strip_code(content: str) -> str:
    return INLINE_CODE_RE.sub("", CODE_BLOCK_RE.sub("", content))


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
    fm: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def normalize_link(link: str) -> str:
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def parse_date_value(value: Any):
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
    records = []
    for path in find_md_files(wiki_path):
        rel_path = path.relative_to(wiki_path).as_posix()
        content = read_file(path)
        records.append(PageRecord(
            path=path, rel_path=rel_path, stem=path.stem,
            content=content,
            frontmatter=extract_frontmatter(content),
            wikilinks=extract_wikilinks(content),
        ))
    return records


def count_content_pages(records, dirname):
    prefix = dirname + "/"
    return sum(1 for r in records if r.rel_path.startswith(prefix))


def is_skipped(record):
    return record.rel_path.casefold() in SKIP_NAMES


def resolve_link_target(source, link, by_rel_path, by_stem):
    normalized = normalize_link(link)
    if not normalized:
        return None, None
    direct_md = normalized if normalized.endswith(".md") else normalized + ".md"
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


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(read_file(path))
    except Exception:
        return default


def save_json(path: Path, data: Any):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def page_signature(record: PageRecord) -> str:
    value = record.frontmatter.get("last_updated") or record.frontmatter.get("date")
    parsed = parse_date_value(value)
    if parsed:
        return parsed.isoformat()
    return datetime.fromtimestamp(record.path.stat().st_mtime).date().isoformat()


def cache_key(a: str, b: str) -> str:
    left, right = sorted((a, b))
    return left + "||" + right


def get_page_links(record: PageRecord, by_rel_path, by_stem) -> set[str]:
    linked = set()
    for raw in record.wikilinks:
        resolved, issue = resolve_link_target(record, raw, by_rel_path, by_stem)
        if resolved and resolved != record.rel_path:
            linked.add(resolved)
    return linked


def extract_changed_paths_from_log(log_record: PageRecord, since: date | None) -> set[str]:
    if since is None:
        return set()
    changed = set()
    content = body_without_frontmatter(log_record.content)
    chunks = re.split(r"(?=^## \[\d{4}-\d{2}-\d{2}\])", content, flags=re.MULTILINE)
    for chunk in chunks:
        heading = LOG_HEADING_RE.search(chunk)
        if not heading:
            continue
        log_date = parse_date_value(heading.group(1))
        if not log_date or log_date <= since:
            continue
        for match in LOG_PATH_LINE_RE.finditer(chunk):
            raw = match.group(1).strip()
            if raw.casefold() == "none":
                continue
            for item in raw.split(","):
                normalized = item.strip().replace("\\", "/")
                if normalized.startswith("wiki/"):
                    normalized = normalized[len("wiki/"):]
                if normalized.endswith(".md"):
                    changed.add(normalized)
    return changed


def determine_semantic_scope(records, by_rel_path, by_stem, wiki_path: Path, level: str):
    scope_meta = {"mode": "full", "changed_pages": [], "selected_pages": []}
    if level == "deep":
        return set(r.rel_path for r in records), scope_meta

    last_lint_data = load_json(wiki_path / "_last-lint.json", {"last_lint": None, "scope": []})
    last_lint_date = parse_date_value(last_lint_data.get("last_lint"))
    log_record = by_rel_path.get("log.md")
    changed = set()
    if log_record is not None:
        changed = extract_changed_paths_from_log(log_record, last_lint_date)

    if not changed:
        full_scope = set(r.rel_path for r in records)
        scope_meta["selected_pages"] = sorted(full_scope)
        return full_scope, scope_meta

    selected = set(changed)
    for rel_path in list(changed):
        record = by_rel_path.get(rel_path)
        if record is None:
            continue
        selected.update(get_page_links(record, by_rel_path, by_stem))

    if level == "light":
        selected = {p for p in selected if p.startswith(("entities/", "topics/", "sources/"))}

    scope_meta["mode"] = "incremental"
    scope_meta["changed_pages"] = sorted(changed)
    scope_meta["selected_pages"] = sorted(selected)
    return selected, scope_meta


def read_summary_index(wiki_path: Path):
    data = load_json(wiki_path / "_summary-index.json", {"pages": []})
    if not isinstance(data, dict):
        return {}
    pages = data.get("pages", [])
    if not isinstance(pages, list):
        return {}
    mapping = {}
    for item in pages:
        if isinstance(item, dict) and item.get("path"):
            mapping[str(item["path"]).replace("\\", "/")] = item
    return mapping


# ---------------------------------------------------------------------------
# Semantic candidate extraction (Layer 1)
# ---------------------------------------------------------------------------


def check_semantic_duplicates(records, cache_state, summary_index):
    """#1: Find title-similar page pairs in the same folder."""
    from itertools import combinations
    folder_groups = {}
    for r in records:
        parts = r.rel_path.split("/")
        if len(parts) >= 2 and parts[0] in SEMANTIC_DIRS:
            folder_groups.setdefault(parts[0], []).append(r)
    dupes = []
    for folder, pages in folder_groups.items():
        for a, b in combinations(pages, 2):
            ta = a.frontmatter.get("title", a.stem).casefold()
            tb = b.frontmatter.get("title", b.stem).casefold()
            mx = max(len(ta), len(tb))
            if mx == 0:
                continue
            dist = levenshtein_distance(ta, tb)
            ratio = dist / mx
            if ratio < LEVENSHTEIN_RATIO_THRESHOLD:
                key = cache_key(a.rel_path, b.rel_path)
                sig = {a.rel_path: page_signature(a), b.rel_path: page_signature(b)}
                if cache_state.get(key) == sig:
                    continue
                dupes.append({
                    "page_a": a.rel_path, "page_b": b.rel_path,
                    "title_a": a.frontmatter.get("title", a.stem),
                    "title_b": b.frontmatter.get("title", b.stem),
                    "distance": dist, "ratio": round(ratio, 3),
                    "summary_a": (summary_index.get(a.rel_path) or {}).get("summary", ""),
                    "summary_b": (summary_index.get(b.rel_path) or {}).get("summary", ""),
                })
    return dupes


def check_source_reliability(records, by_rel_path, by_stem):
    """#5: Find entity/topic pages depending solely on low-reliability sources."""
    src_map = {}
    for r in records:
        if r.rel_path.startswith("sources/"):
            src_map[r.stem] = r
            src_map[r.rel_path] = r
    weak = []
    for r in records:
        parts = r.rel_path.split("/")
        if not (len(parts) >= 2 and parts[0] in SEMANTIC_DIRS):
            continue
        src_links, rels = [], []
        for raw in r.wikilinks:
            nm = normalize_link(raw)
            st = Path(nm).stem
            src = src_map.get(nm) or src_map.get(st)
            if src is None:
                for _k, sr in src_map.items():
                    if sr.stem == st:
                        src = sr
                        break
            if src:
                src_links.append(src.rel_path)
                rels.append(str(src.frontmatter.get("reliability", "unknown")).lower())
        if not src_links:
            continue
        low_n = sum(1 for x in rels if x == "low")
        hm_n = sum(1 for x in rels if x in ("high", "medium"))
        if low_n > 0 and hm_n == 0:
            weak.append({
                "page": r.rel_path, "sources": src_links,
                "reliabilities": rels, "issue": "all_sources_low",
            })
    return weak


def check_temporal_order(records):
    """#6: Find year+number sequences not in chronological order."""
    disorders = []
    for r in records:
        parts = r.rel_path.split("/")
        if not (len(parts) >= 2 and parts[0] in SEMANTIC_DIRS):
            continue
        body = body_without_frontmatter(r.content)
        sections = re.split(r"^##\s+", body, flags=re.MULTILINE)
        for sec in sections:
            matches = YEAR_NUMBER_RE.findall(sec)
            if len(matches) < 2:
                continue
            years = [int(m[0]) for m in matches]
            for i in range(1, len(years)):
                if years[i] < years[i - 1]:
                    title = sec.split("\n", 1)[0].strip()[:50]
                    disorders.append({
                        "page": r.rel_path, "section": title,
                        "year_sequence": years, "issue": "non_chronological",
                    })
                    break
    return disorders


def check_weak_crosslinks(records, by_rel_path, by_stem, cache_state):
    """#7: Find page pairs sharing 3+ sources but no mutual wikilinks."""
    from itertools import combinations
    page_src = {}
    for r in records:
        parts = r.rel_path.split("/")
        if not (len(parts) >= 2 and parts[0] in SEMANTIC_DIRS):
            continue
        sources = set()
        fm_s = r.frontmatter.get("sources", [])
        if isinstance(fm_s, list):
            for s in fm_s:
                sources.add(str(s).strip())
        for raw in r.wikilinks:
            nm = normalize_link(raw)
            if nm.startswith("sources/") or nm.startswith("source-"):
                sources.add(Path(nm).stem)
        if sources:
            page_src[r.rel_path] = sources
    page_stems = {}
    for r in records:
        stems = set()
        for raw in r.wikilinks:
            stems.add(Path(normalize_link(raw)).stem)
        page_stems[r.rel_path] = stems
    missing = []
    items = list(page_src.items())
    for (pa, sa), (pb, sb) in combinations(items, 2):
        shared = sa & sb
        if len(shared) < 3:
            continue
        sta = Path(pa).stem
        stb = Path(pb).stem
        a2b = stb in page_stems.get(pa, set())
        b2a = sta in page_stems.get(pb, set())
        if not a2b and not b2a:
            rec_a = next((r for r in records if r.rel_path == pa), None)
            rec_b = next((r for r in records if r.rel_path == pb), None)
            if rec_a and rec_b:
                key = cache_key(pa, pb)
                sig = {pa: page_signature(rec_a), pb: page_signature(rec_b)}
                if cache_state.get(key) == sig:
                    continue
            missing.append({
                "page_a": pa, "page_b": pb,
                "shared_sources": len(shared),
                "shared_source_list": sorted(shared),
            })
    return missing


def check_coverage_gaps(records, by_rel_path, by_stem):
    """#3: Find sources mentioning an entity not reflected in that entity page."""
    ent_map = {}
    for r in records:
        if r.rel_path.startswith("entities/"):
            ent_map[r.stem] = r
    if not ent_map:
        return []
    src_to_ent = {}
    for r in records:
        if not r.rel_path.startswith("sources/"):
            continue
        linked = set()
        for raw in r.wikilinks:
            nm = normalize_link(raw)
            st = Path(nm).stem
            if st in ent_map or nm.startswith("entities/"):
                linked.add(st)
        if linked:
            src_to_ent[r.rel_path] = linked
    gaps = []
    for est, erec in ent_map.items():
        e_src_stems = set()
        for raw in erec.wikilinks:
            nm = normalize_link(raw)
            st = Path(nm).stem
            if nm.startswith("sources/") or st.startswith("source-"):
                e_src_stems.add(st)
        mentioning = []
        for sp, ents in src_to_ent.items():
            if est in ents:
                sst = Path(sp).stem
                if sst not in e_src_stems:
                    mentioning.append(sp)
        if mentioning:
            gaps.append({
                "entity": erec.rel_path,
                "unreflected_sources": mentioning,
                "count": len(mentioning),
            })
    return gaps


def extract_page_metrics(record: PageRecord):
    metrics = []
    body = body_without_frontmatter(record.content)
    sections = re.split(r"^##\s+", body, flags=re.MULTILINE)
    for sec in sections:
        title = sec.split("\n", 1)[0].strip()[:80] or "본문"
        for year, value in YEAR_NUMBER_RE.findall(sec):
            metrics.append({
                "section": title,
                "year": int(year),
                "value": value.strip(),
            })
    return metrics


def page_source_reliabilities(record: PageRecord, records):
    by_source = {}
    for r in records:
        if r.rel_path.startswith("sources/"):
            by_source[r.stem] = str(r.frontmatter.get("reliability", "unknown")).lower()
    rels = []
    for raw in record.wikilinks:
        nm = normalize_link(raw)
        st = Path(nm).stem
        if st in by_source:
            rels.append(by_source[st])
    return sorted(set(rels)) or ["unknown"]


def check_contradictions(records, by_rel_path, by_stem, cache_state):
    entity_records = [r for r in records if r.rel_path.startswith("entities/")]
    contradictions = []
    records_by_path = {r.rel_path: r for r in records}
    for entity in entity_records:
        entity_metrics = extract_page_metrics(entity)
        if not entity_metrics:
            continue
        entity_stem = entity.stem
        linked_pages = []
        for record in records:
            if record.rel_path == entity.rel_path:
                continue
            linked_stems = {Path(normalize_link(raw)).stem for raw in record.wikilinks}
            if entity_stem in linked_stems:
                linked_pages.append(record)

        for other in linked_pages:
            other_metrics = extract_page_metrics(other)
            if not other_metrics:
                continue
            key = cache_key(entity.rel_path, other.rel_path)
            sig = {entity.rel_path: page_signature(entity), other.rel_path: page_signature(other)}
            if cache_state.get(key) == sig:
                continue
            for em in entity_metrics:
                for om in other_metrics:
                    if em["year"] != om["year"]:
                        continue
                    if em["value"] == om["value"]:
                        continue
                    contradictions.append({
                        "entity": entity.rel_path,
                        "page_a": entity.rel_path,
                        "page_b": other.rel_path,
                        "year": em["year"],
                        "metric": em["section"],
                        "value_a": em["value"],
                        "value_b": om["value"],
                        "reliability_a": page_source_reliabilities(entity, records),
                        "reliability_b": page_source_reliabilities(other, records),
                    })
                    break
                else:
                    continue
                break
    return contradictions


def check_misclassification(records, summary_index):
    candidates = []
    for record in records:
        if not record.rel_path.startswith(("entities/", "topics/")):
            continue
        body = body_without_frontmatter(record.content)
        entity_score = sum(body.count(token) for token in ENTITY_HINTS)
        topic_score = sum(body.count(token) for token in TOPIC_HINTS)
        type_hint = str(record.frontmatter.get("type", "")).strip().lower()
        summary = (summary_index.get(record.rel_path) or {}).get("summary", "")
        if record.rel_path.startswith("entities/"):
            if type_hint and type_hint != "entity":
                candidates.append({
                    "page": record.rel_path,
                    "reason": "frontmatter type mismatch",
                    "suggested_folder": "topics/",
                    "summary": summary,
                })
            elif topic_score >= entity_score + 2 and entity_score == 0:
                candidates.append({
                    "page": record.rel_path,
                    "reason": "topic-like language dominates entity traits",
                    "suggested_folder": "topics/",
                    "summary": summary,
                })
        else:
            if type_hint and type_hint != "topic":
                candidates.append({
                    "page": record.rel_path,
                    "reason": "frontmatter type mismatch",
                    "suggested_folder": "entities/",
                    "summary": summary,
                })
            elif entity_score >= topic_score + 2 and topic_score == 0:
                candidates.append({
                    "page": record.rel_path,
                    "reason": "entity-like profile traits dominate topic language",
                    "suggested_folder": "entities/",
                    "summary": summary,
                })
    return candidates


# ---------------------------------------------------------------------------
# Main lint runner
# ---------------------------------------------------------------------------


def run_lint(wiki_path_str, level=DEFAULT_LEVEL):
    wiki_path = Path(wiki_path_str).expanduser().resolve()
    if not wiki_path.exists() or not wiki_path.is_dir():
        return {"error": "Wiki folder does not exist: " + wiki_path_str}
    records = build_records(wiki_path)
    if not records:
        return {"error": "No markdown files found under: " + wiki_path_str}

    by_rel_path = {r.rel_path: r for r in records}
    by_stem = {}
    for r in records:
        by_stem.setdefault(r.stem, []).append(r)
    summary_index = read_summary_index(wiki_path)
    if level == "deep":
        cache_state = {}
    else:
        cache_data = load_json(wiki_path / "_lint-cache.json", {"checked_pairs": {}})
        cache_state = cache_data.get("checked_pairs", {})
        if isinstance(cache_state, list):
            cache_state = {}

    inbound = {r.rel_path: [] for r in records}
    missing_links = []
    ambiguous_links = []

    for r in records:
        for raw in r.wikilinks:
            resolved, issue = resolve_link_target(r, raw, by_rel_path, by_stem)
            if resolved:
                inbound[resolved].append(r.rel_path)
                continue
            nm = normalize_link(raw)
            if issue == "ambiguous":
                ambiguous_links.append({
                    "link": nm, "referenced_by": r.rel_path,
                    "candidates": [c.rel_path for c in by_stem.get(Path(nm).stem, [])],
                })
            elif issue == "missing":
                missing_links.append({"link": nm, "referenced_by": r.rel_path})

    cutoff = date.today() - timedelta(days=90)
    orphan_pages = []
    weak_pages = []
    stale_pages = []
    dup_stems = {
        st: sorted(x.rel_path for x in ms)
        for st, ms in by_stem.items() if len(ms) > 1
    }

    for r in records:
        if not is_skipped(r) and not inbound[r.rel_path]:
            orphan_pages.append(r.rel_path)
        if r.rel_path.startswith(("entities/", "topics/")):
            bl = len(body_without_frontmatter(r.content))
            if bl < 200:
                weak_pages.append({"page": r.rel_path, "body_length": bl})
        if not is_skipped(r):
            lu = parse_date_value(r.frontmatter.get("last_updated"))
            if lu and lu < cutoff:
                stale_pages.append({"page": r.rel_path, "last_updated": lu.isoformat()})

    idx_sync = []
    idx_rec = by_rel_path.get("index.md")
    if idx_rec:
        idx_targets = set()
        for raw in idx_rec.wikilinks:
            resolved, issue = resolve_link_target(idx_rec, raw, by_rel_path, by_stem)
            if resolved:
                idx_targets.add(resolved)
        for r in records:
            if not is_skipped(r) and r.rel_path not in idx_targets:
                idx_sync.append(r.rel_path)

    avg_links = round(
        sum(len(r.wikilinks) for r in records) / max(len(records), 1), 1
    )

    semantic_scope, scope_meta = determine_semantic_scope(records, by_rel_path, by_stem, wiki_path, level)
    scoped_records = [r for r in records if r.rel_path in semantic_scope]

    # Semantic Layer 1
    sem_dup = check_semantic_duplicates(scoped_records, cache_state, summary_index)
    sem_rel = check_source_reliability(scoped_records, by_rel_path, by_stem)
    sem_tmp = check_temporal_order(scoped_records)
    sem_xln = check_weak_crosslinks(scoped_records, by_rel_path, by_stem, cache_state)
    sem_cov = check_coverage_gaps(scoped_records, by_rel_path, by_stem)
    sem_con = [] if level == "light" else check_contradictions(scoped_records, by_rel_path, by_stem, cache_state)
    sem_mis = [] if level == "light" else check_misclassification(scoped_records, summary_index)

    results = {
        "stats": {
            "total_pages": len(records),
            "total_sources": count_content_pages(records, "sources"),
            "total_entities": count_content_pages(records, "entities"),
            "total_topics": count_content_pages(records, "topics"),
            "total_analyses": count_content_pages(records, "analysis"),
            "avg_links_per_page": avg_links,
            "yaml_parser": "pyyaml" if YAML_AVAILABLE else "builtin-regex",
            "lint_level": level,
            "semantic_scope_pages": len(scoped_records),
        },
        "semantic_scope": scope_meta,
        "duplicate_stems": dup_stems,
        "orphan_pages": sorted(orphan_pages),
        "missing_links": missing_links,
        "ambiguous_links": ambiguous_links,
        "weak_pages": sorted(weak_pages, key=lambda x: x["page"]),
        "stale_pages": sorted(stale_pages, key=lambda x: x["page"]),
        "index_sync": sorted(idx_sync),
        "semantic_duplicates": sem_dup,
        "source_reliability": sem_rel,
        "temporal_disorders": sem_tmp,
        "weak_crosslinks": sem_xln,
        "coverage_gaps": sem_cov,
        "contradiction_candidates": sem_con,
        "misclassification_candidates": sem_mis,
        "notes": [],
    }
    results["notes"].append(
        "Structural lint: duplicate names, broken links, orphan/weak/stale pages, index drift."
    )
    results["notes"].append(
        "Semantic L1: duplicate titles (#1), weak evidence (#5), temporal disorder (#6), missing crosslinks (#7), coverage gaps (#3)."
    )
    results["notes"].append(
        "Semantic L2 (LLM): duplicate confirmation (#1), contradiction (#2), coverage importance (#3), misclassification (#4)."
    )
    if not YAML_AVAILABLE:
        results["notes"].append("Install PyYAML for better frontmatter parsing: pip install pyyaml")

    checked_pairs = dict(cache_state)
    for bucket in ("semantic_duplicates", "weak_crosslinks", "contradiction_candidates"):
        for item in results.get(bucket, []):
            key = cache_key(item["page_a"], item["page_b"])
            rec_a = by_rel_path.get(item["page_a"])
            rec_b = by_rel_path.get(item["page_b"])
            if rec_a and rec_b:
                checked_pairs[key] = {
                    item["page_a"]: page_signature(rec_a),
                    item["page_b"]: page_signature(rec_b),
                }
    save_json(wiki_path / "_lint-cache.json", {
        "checked_pairs": checked_pairs,
        "last_updated": date.today().isoformat(),
    })
    save_json(wiki_path / "_last-lint.json", {
        "last_lint": date.today().isoformat(),
        "scope": scope_meta.get("selected_pages", []),
        "level": level,
    })
    return results


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------


def format_report(results):
    if "error" in results:
        return "Error: " + results["error"]

    stats = results["stats"]
    lines = [
        "## [%s] lint | Wiki health check" % date.today().isoformat(),
        "",
        "### Stats",
        "- Total pages: %d" % stats["total_pages"],
        "- Sources: %d" % stats["total_sources"],
        "- Entities: %d" % stats["total_entities"],
        "- Topics: %d" % stats["total_topics"],
        "- Analysis pages: %d" % stats["total_analyses"],
        "- Average wikilinks per page: %s" % stats["avg_links_per_page"],
        "- Frontmatter parser: %s" % stats["yaml_parser"],
        "- Lint level: %s" % stats["lint_level"],
        "- Semantic scope pages: %d" % stats["semantic_scope_pages"],
    ]

    if results.get("semantic_scope", {}).get("mode") == "incremental":
        lines.extend([
            "",
            "### Incremental scope",
            "- Changed pages: %d" % len(results["semantic_scope"].get("changed_pages", [])),
            "- Selected pages: %d" % len(results["semantic_scope"].get("selected_pages", [])),
        ])

    if results["duplicate_stems"]:
        lines.append("")
        lines.append("### Duplicate stems (%d)" % len(results["duplicate_stems"]))
        for stem, paths in sorted(results["duplicate_stems"].items()):
            joined = ", ".join("`%s`" % p for p in paths)
            lines.append("- `%s` -> %s" % (stem, joined))

    if results["orphan_pages"]:
        lines.append("")
        lines.append("### Orphan pages (%d)" % len(results["orphan_pages"]))
        for rp in results["orphan_pages"]:
            lines.append("- `%s`" % rp)

    if results["missing_links"]:
        lines.append("")
        lines.append("### Missing links (%d)" % len(results["missing_links"]))
        for it in results["missing_links"]:
            lines.append("- `[[%s]]` referenced by `%s`" % (it["link"], it["referenced_by"]))

    if results["ambiguous_links"]:
        lines.append("")
        lines.append("### Ambiguous links (%d)" % len(results["ambiguous_links"]))
        for it in results["ambiguous_links"]:
            cands = ", ".join("`%s`" % p for p in it["candidates"])
            lines.append("- `[[%s]]` in `%s` matches: %s" % (it["link"], it["referenced_by"], cands))

    if results["weak_pages"]:
        lines.append("")
        lines.append("### Weak pages (%d)" % len(results["weak_pages"]))
        for it in results["weak_pages"]:
            lines.append("- `%s` body length: %d" % (it["page"], it["body_length"]))

    if results["stale_pages"]:
        lines.append("")
        lines.append("### Stale pages (%d)" % len(results["stale_pages"]))
        for it in results["stale_pages"]:
            lines.append("- `%s` last_updated: %s" % (it["page"], it["last_updated"]))

    if results["index_sync"]:
        lines.append("")
        lines.append("### Missing from index (%d)" % len(results["index_sync"]))
        for rp in results["index_sync"]:
            lines.append("- `%s`" % rp)

    structural = (
        results["duplicate_stems"], results["orphan_pages"],
        results["missing_links"], results["ambiguous_links"],
        results["weak_pages"], results["stale_pages"], results["index_sync"],
    )
    if not any(structural):
        lines.extend(["", "### Status", "- No structural issues detected."])

    # Semantic candidates
    has_sem = False
    def sem_hdr():
        nonlocal has_sem
        if not has_sem:
            lines.extend(["", "---", "", "## Semantic candidates (Layer 1)"])
            has_sem = True

    if results.get("semantic_duplicates"):
        sem_hdr()
        lines.append("")
        lines.append("### #1 Duplicate candidates (%d)" % len(results["semantic_duplicates"]))
        for it in results["semantic_duplicates"]:
            lines.append("- `%s` <-> `%s` (distance=%d, ratio=%s)" % (
                it["page_a"], it["page_b"], it["distance"], it["ratio"]))

    if results.get("source_reliability"):
        sem_hdr()
        lines.append("")
        lines.append("### #5 Weak evidence (%d)" % len(results["source_reliability"]))
        for it in results["source_reliability"]:
            srcs = ", ".join("`%s`" % s for s in it["sources"])
            lines.append("- `%s` -- all sources low reliability: %s" % (it["page"], srcs))

    if results.get("temporal_disorders"):
        sem_hdr()
        lines.append("")
        lines.append("### #6 Temporal disorder (%d)" % len(results["temporal_disorders"]))
        for it in results["temporal_disorders"]:
            seq = " -> ".join(str(y) for y in it["year_sequence"])
            lines.append("- `%s` @ %s -- %s" % (it["page"], it["section"], seq))

    if results.get("weak_crosslinks"):
        sem_hdr()
        lines.append("")
        lines.append("### #7 Missing crosslinks (%d)" % len(results["weak_crosslinks"]))
        for it in results["weak_crosslinks"]:
            lines.append("- `%s` <-> `%s` (shared sources: %d)" % (
                it["page_a"], it["page_b"], it["shared_sources"]))

    if results.get("coverage_gaps"):
        sem_hdr()
        lines.append("")
        lines.append("### #3 Coverage gaps (%d)" % len(results["coverage_gaps"]))
        for it in results["coverage_gaps"]:
            srcs = ", ".join("`%s`" % s for s in it["unreflected_sources"])
            lines.append("- `%s` -- %d source(s) mention but not reflected: %s" % (
                it["entity"], it["count"], srcs))

    if results.get("contradiction_candidates"):
        sem_hdr()
        lines.append("")
        lines.append("### #2 Contradiction candidates (%d)" % len(results["contradiction_candidates"]))
        for it in results["contradiction_candidates"]:
            lines.append('- `%s` year=%s metric="%s" -- `%s` vs `%s` (%s / %s)' % (
                it["entity"], it["year"], it["metric"], it["value_a"], it["value_b"],
                ",".join(it["reliability_a"]), ",".join(it["reliability_b"])))

    if results.get("misclassification_candidates"):
        sem_hdr()
        lines.append("")
        lines.append("### #4 Misclassification candidates (%d)" % len(results["misclassification_candidates"]))
        for it in results["misclassification_candidates"]:
            lines.append("- `%s` -> suggested `%s` (%s)" % (
                it["page"], it["suggested_folder"], it["reason"]))

    sem_all = (
        results.get("semantic_duplicates", []),
        results.get("contradiction_candidates", []),
        results.get("misclassification_candidates", []),
        results.get("source_reliability", []),
        results.get("temporal_disorders", []),
        results.get("weak_crosslinks", []),
        results.get("coverage_gaps", []),
    )
    if not any(sem_all):
        lines.extend(["", "---", "", "## Semantic candidates (Layer 1)",
                       "- No semantic candidates detected."])

    if results["notes"]:
        lines.append("")
        lines.append("### Notes")
        for note in results["notes"]:
            lines.append("- %s" % note)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Run structural and semantic lint for an LLM Wiki.")
    parser.add_argument("wiki_folder_path", help="Path to the wiki folder")
    parser.add_argument(
        "--level",
        default=DEFAULT_LEVEL,
        choices=VALID_LEVELS,
        help="Semantic lint depth: light, standard, or deep",
    )
    args = parser.parse_args()
    wiki_path = args.wiki_folder_path
    results = run_lint(wiki_path, level=args.level)
    json_path = Path(wiki_path).expanduser().resolve().parent / "_lint_result.json"
    try:
        json_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        json_note = str(json_path)
    except Exception as exc:
        json_note = "JSON output failed: %s" % exc
    print(format_report(results))
    print("\n(JSON: %s)" % json_note)
    return 0 if "error" not in results else 1


if __name__ == "__main__":
    sys.exit(main())
