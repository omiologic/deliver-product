#!/usr/bin/env python3
"""Retrieve bounded context from a selected repository-local planning projection."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import validate_plans as validator  # noqa: E402


LIFECYCLES = ("backlog", "ready", "active", "archived")
MAX_DIAGNOSTICS = 100
Trace = Callable[[str, Path], None]


@dataclass(frozen=True)
class ItemMetadata:
    path: Path
    relative_path: str
    lifecycle: str
    compacted_cycle: str | None
    fields: dict[str, Any]

    @property
    def work_item_id(self) -> str:
        value = self.fields.get("work_item_id")
        return value if isinstance(value, str) else ""

    @property
    def depends_on(self) -> list[str]:
        value = self.fields.get("depends_on")
        return [str(item) for item in value] if isinstance(value, list) else []

    def compact(self) -> dict[str, Any]:
        selected = {
            key: self.fields[key]
            for key in (
                "work_item_id",
                "title",
                "depends_on",
                "phase_id",
                "sprint_id",
                "epic_id",
                "feature_ids",
            )
            if key in self.fields
        }
        return {
            **selected,
            "lifecycle": self.lifecycle,
            "path": self.relative_path,
            "compacted_cycle": self.compacted_cycle,
        }


def _trace(trace: Trace | None, operation: str, path: Path) -> None:
    if trace is not None:
        trace(operation, path)


def _read_frontmatter(path: Path, trace: Trace | None) -> tuple[dict[str, Any], list[str]]:
    """Read only frontmatter lines; do not load the Markdown body."""
    _trace(trace, "metadata", path)
    diagnostics: list[str] = []
    lines: list[str] = []
    try:
        with path.open(encoding="utf-8") as handle:
            if handle.readline().rstrip("\n") != "---":
                return {}, ["missing YAML frontmatter opener"]
            for raw in handle:
                line = raw.rstrip("\n")
                if line == "---":
                    break
                lines.append(line)
            else:
                return {}, ["missing YAML frontmatter closer"]
    except OSError as exc:
        return {}, [f"cannot read file: {exc}"]

    fields: dict[str, Any] = {}
    active_list: str | None = None
    for number, line in enumerate(lines, 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        list_match = re.fullmatch(r"  -\s+(.+)", line)
        if list_match and active_list:
            fields[active_list].append(validator._scalar(list_match.group(1)))
            continue
        field_match = re.fullmatch(r"([a-z][a-z0-9_]*):(?:\s*(.*))?", line)
        if not field_match:
            diagnostics.append(f"unsupported frontmatter syntax at line {number}")
            active_list = None
            continue
        key, raw = field_match.groups()
        if key in fields:
            diagnostics.append(f"duplicate frontmatter key: {key}")
        if raw:
            fields[key] = validator._scalar(raw)
            active_list = None
        else:
            fields[key] = []
            active_list = key
    return fields, diagnostics


def _read_content(path: Path, operation: str, trace: Trace | None) -> str:
    _trace(trace, operation, path)
    return path.read_text(encoding="utf-8")


def _artifact_is_bounded(plans_root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(plans_root)
    except ValueError:
        return False
    return True


def _resolve_plans_root(root: Path, plans_path: Path) -> tuple[Path | None, list[dict[str, str]]]:
    consumer_root = root.resolve()
    configured = Path(plans_path)
    if configured.is_absolute():
        return None, [{"severity": "error", "path": ".", "message": "plans path must be consumer-relative"}]
    plans_root = (consumer_root / configured).resolve()
    try:
        plans_root.relative_to(consumer_root)
    except ValueError:
        return None, [{"severity": "error", "path": ".", "message": "plans path escapes consumer root"}]
    if not plans_root.is_dir():
        return None, [{"severity": "error", "path": configured.as_posix(), "message": f"missing {configured.as_posix()} directory"}]
    return plans_root, []


def inventory_projection(
    root: Path,
    *,
    plans_path: Path = validator.DEFAULT_PLANS_PATH,
    trace: Trace | None = None,
) -> tuple[Path | None, list[ItemMetadata], list[dict[str, str]]]:
    plans_root, diagnostics = _resolve_plans_root(root, plans_path)
    if plans_root is None:
        return None, [], diagnostics

    paths: list[Path] = []
    for lifecycle in LIFECYCLES:
        directory = plans_root / lifecycle
        if directory.is_dir():
            paths.extend(path for path in sorted(directory.glob("*.md")) if validator._recognized(path))
    history_root = plans_root / "archived" / "history"
    paths.extend(path for path in sorted(history_root.glob("*/*.md")) if validator._recognized(path))

    items: list[ItemMetadata] = []
    for path in paths:
        if not _artifact_is_bounded(plans_root, path):
            diagnostics.append(
                {
                    "severity": "error",
                    "path": path.relative_to(plans_root).as_posix(),
                    "message": "projection record escapes planning root",
                }
            )
            continue
        fields, found = _read_frontmatter(path, trace)
        relative = path.relative_to(plans_root)
        cycle = relative.parts[2] if relative.parts[:2] == ("archived", "history") else None
        item = ItemMetadata(path, relative.as_posix(), relative.parts[0], cycle, fields)
        items.append(item)
        diagnostics.extend(
            {"severity": "error", "path": item.relative_path, "message": message}
            for message in found
        )

    seen: dict[str, ItemMetadata] = {}
    for item in items:
        if not item.work_item_id:
            diagnostics.append({"severity": "error", "path": item.relative_path, "message": "missing work_item_id"})
        elif item.work_item_id in seen:
            diagnostics.append({"severity": "error", "path": item.relative_path, "message": f"duplicate work_item_id: {item.work_item_id}"})
        else:
            seen[item.work_item_id] = item
    return plans_root, items, diagnostics


def _body_record(item: ItemMetadata, trace: Trace | None) -> dict[str, Any]:
    return {**item.compact(), "content": _read_content(item.path, "body", trace)}


def _cycle_matches(item: ItemMetadata, cycle_id: str) -> bool:
    if item.compacted_cycle == cycle_id:
        return True
    return any(item.fields.get(field) == cycle_id for field in ("phase_id", "sprint_id"))


def _successful_result(content: str) -> bool:
    match = re.search(r"(?m)^- Result:\s*(.+?)\s*$", content)
    return bool(match and match.group(1).strip().lower() not in {"", "—", "-", "cancelled", "canceled", "superseded"})


def _target_selection(
    plans_root: Path,
    items: list[ItemMetadata],
    work_item_id: str,
    trace: Trace | None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    by_id = {item.work_item_id: item for item in items if item.work_item_id}
    if work_item_id not in by_id:
        return {}, [{"severity": "error", "path": work_item_id, "message": "target work_item_id does not resolve"}]

    selected: list[ItemMetadata] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    diagnostics: list[dict[str, str]] = []

    def visit(identity: str) -> None:
        if identity in visiting:
            diagnostics.append({"severity": "error", "path": identity, "message": "dependency cycle detected"})
            return
        if identity in visited:
            return
        item = by_id.get(identity)
        if item is None:
            diagnostics.append({"severity": "error", "path": identity, "message": "dependency does not resolve"})
            return
        visiting.add(identity)
        for dependency in item.depends_on:
            visit(dependency)
        visiting.remove(identity)
        visited.add(identity)
        selected.append(item)

    visit(work_item_id)
    summaries: list[dict[str, str]] = []
    for cycle_id in sorted({item.compacted_cycle for item in selected if item.compacted_cycle}):
        assert cycle_id is not None
        summary = plans_root / "archived" / "summaries" / f"{cycle_id}.md"
        if summary.is_file() and _artifact_is_bounded(plans_root, summary):
            summaries.append(
                {
                    "cycle_id": cycle_id,
                    "path": summary.relative_to(plans_root).as_posix(),
                    "content": _read_content(summary, "summary", trace),
                }
            )
        elif not summary.is_file():
            diagnostics.append({"severity": "error", "path": cycle_id, "message": "selected archived cycle has no matching summary"})
        else:
            diagnostics.append({"severity": "error", "path": cycle_id, "message": "selected archived summary escapes planning root"})
    records = [_body_record(item, trace) for item in selected]
    return {"target": work_item_id, "summaries": summaries, "records": records}, diagnostics


def _cycle_selection(
    plans_root: Path,
    items: list[ItemMetadata],
    cycle_id: str,
    trace: Trace | None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not validator.ID_PATTERN.fullmatch(cycle_id):
        return {}, [{"severity": "error", "path": cycle_id, "message": "cycle_id must be a lowercase kebab identifier"}]
    selected = [item for item in items if _cycle_matches(item, cycle_id)]
    if not selected:
        return {}, [{"severity": "error", "path": cycle_id, "message": "cycle does not resolve"}]
    summary_path = plans_root / "archived" / "summaries" / f"{cycle_id}.md"
    summary = None
    if summary_path.is_file() and _artifact_is_bounded(plans_root, summary_path):
        summary = {
            "path": summary_path.relative_to(plans_root).as_posix(),
            "content": _read_content(summary_path, "summary", trace),
        }
    records = [_body_record(item, trace) for item in selected]
    current = [item.work_item_id for item in selected if item.lifecycle != "archived"]
    unsuccessful = [
        record["work_item_id"]
        for record in records
        if record["lifecycle"] == "archived" and not _successful_result(record["content"])
    ]
    compacted = any(item.compacted_cycle == cycle_id for item in selected)
    return {
        "cycle_id": cycle_id,
        "summary": summary,
        "records": records,
        "compaction": {
            "scope": [item.work_item_id for item in selected],
            "eligible": not compacted and not current and not unsuccessful,
            "already_compacted": compacted,
            "blocking_current_items": current,
            "blocking_unsuccessful_items": unsuccessful,
        },
    }, []


def _serialize_diagnostics(
    diagnostics: Iterable[validator.Diagnostic], root: Path
) -> tuple[list[dict[str, str]], int]:
    ordered = sorted(diagnostics, key=lambda item: (item.severity, str(item.path), item.message))
    serialized: list[dict[str, str]] = []
    for diagnostic in ordered[:MAX_DIAGNOSTICS]:
        try:
            path = diagnostic.path.relative_to(root.resolve()).as_posix()
        except ValueError:
            path = str(diagnostic.path)
        serialized.append({"severity": diagnostic.severity, "path": path, "message": diagnostic.message})
    return serialized, max(0, len(ordered) - MAX_DIAGNOSTICS)


def retrieve_projection(
    root: Path,
    mode: str,
    *,
    plans_path: Path = validator.DEFAULT_PLANS_PATH,
    profile_path: Path = validator.DEFAULT_PROFILE_PATH,
    work_item_id: str | None = None,
    lifecycle: str | None = None,
    cycle_id: str | None = None,
    trace: Trace | None = None,
) -> dict[str, Any]:
    if mode == "validation":
        found = validator.validate_workspace(root, plans_path=plans_path, profile_path=profile_path)
        diagnostics, omitted = _serialize_diagnostics(found, root)
        return {"mode": mode, "diagnostics": diagnostics, "omitted_diagnostics": omitted}

    plans_root, items, diagnostics = inventory_projection(root, plans_path=plans_path, trace=trace)
    result: dict[str, Any] = {"mode": mode, "diagnostics": diagnostics, "omitted_diagnostics": 0}
    if plans_root is None or diagnostics:
        return result
    if mode == "target":
        if not work_item_id:
            result["diagnostics"].append({"severity": "error", "path": ".", "message": "target mode requires work_item_id"})
        else:
            selected, found = _target_selection(plans_root, items, work_item_id, trace)
            result.update(selected)
            result["diagnostics"].extend(found)
    elif mode == "lifecycle":
        if lifecycle not in LIFECYCLES:
            result["diagnostics"].append({"severity": "error", "path": ".", "message": "lifecycle mode requires backlog, ready, active, or archived"})
        else:
            result.update({"lifecycle": lifecycle, "records": [item.compact() for item in items if item.lifecycle == lifecycle]})
    elif mode == "cycle":
        if not cycle_id:
            result["diagnostics"].append({"severity": "error", "path": ".", "message": "cycle mode requires cycle_id"})
        else:
            selected, found = _cycle_selection(plans_root, items, cycle_id, trace)
            result.update(selected)
            result["diagnostics"].extend(found)
    elif mode == "audit":
        summaries: list[dict[str, str]] = []
        summaries_root = plans_root / "archived" / "summaries"
        if summaries_root.is_dir():
            for path in sorted(summaries_root.glob("*.md")):
                if not _artifact_is_bounded(plans_root, path):
                    result["diagnostics"].append(
                        {
                            "severity": "error",
                            "path": path.relative_to(plans_root).as_posix(),
                            "message": "archived summary escapes planning root",
                        }
                    )
                    continue
                summaries.append({"path": path.relative_to(plans_root).as_posix(), "content": _read_content(path, "summary", trace)})
        result.update({"summaries": summaries, "records": [_body_record(item, trace) for item in items]})
    else:
        result["diagnostics"].append({"severity": "error", "path": ".", "message": f"unsupported retrieval mode: {mode}"})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--mode", required=True, choices=("target", "lifecycle", "cycle", "audit", "validation"))
    parser.add_argument("--work-item-id")
    parser.add_argument("--lifecycle", choices=LIFECYCLES)
    parser.add_argument("--cycle-id")
    parser.add_argument("--plans-path", default=validator.DEFAULT_PLANS_PATH, type=Path)
    parser.add_argument("--profile-path", default=validator.DEFAULT_PROFILE_PATH, type=Path)
    args = parser.parse_args(argv)
    result = retrieve_projection(
        args.root,
        args.mode,
        plans_path=args.plans_path,
        profile_path=args.profile_path,
        work_item_id=args.work_item_id,
        lifecycle=args.lifecycle,
        cycle_id=args.cycle_id,
    )
    print(json.dumps(result, separators=(",", ":")))
    return 1 if any(item["severity"] == "error" for item in result["diagnostics"]) else 0


if __name__ == "__main__":
    sys.exit(main())
