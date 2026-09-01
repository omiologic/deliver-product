#!/usr/bin/env python3
"""Validate the selected repository-local work-item projection."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


DIMENSIONS = ("phase", "sprint", "epic", "feature")
DIMENSION_FIELDS = {
    "phase": "phase_id",
    "sprint": "sprint_id",
    "epic": "epic_id",
    "feature": "feature_ids",
}
PRESETS = {
    "minimal": {},
    "phased": {"phase": "required"},
    "sprint": {"sprint": "required"},
    "product": {"epic": "optional", "feature": "required"},
}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LEGACY_LOCAL_PATTERN = re.compile(r"^work-\d{8}-\d{3}$")
LEGACY_QUALIFIED_PATTERN = re.compile(
    r"^work-(?P<project_key>[a-z0-9]+(?:-[a-z0-9]+)*)-(?P<date>\d{8})-(?P<sequence>\d{3})$"
)
CANONICAL_PATTERN = re.compile(
    r"^(?P<project_key>[a-z0-9]+(?:-[a-z0-9]+)*)-(?P<sequence>\d{5})$"
)
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    path: Path
    message: str


@dataclass
class Dimension:
    mode: str
    catalog: dict[str, dict[str, str]]


@dataclass
class Profile:
    schema_version: int
    name: str
    dimensions: dict[str, Dimension]
    project_key: str | None = None
    qualified_ids_from: datetime | None = None
    canonical_ids_from: datetime | None = None
    last_work_item_sequence: int | None = None


@dataclass
class WorkItem:
    path: Path
    lifecycle: str
    compacted: bool
    fields: dict[str, Any]
    body: str

    @property
    def work_item_id(self) -> str:
        value = self.fields.get("work_item_id")
        return value if isinstance(value, str) else ""


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "[]":
        return []
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"\d+", value):
        return int(value)
    return value


def _frontmatter(path: Path) -> tuple[list[str], str, list[Diagnostic]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], "", [Diagnostic("error", path, f"cannot read file: {exc}")]
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return [], text, [Diagnostic("error", path, "missing YAML frontmatter opener")]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return [], text, [Diagnostic("error", path, "missing YAML frontmatter closer")]
    diagnostics = []
    if any("\t" in line for line in lines[1:end]):
        diagnostics.append(Diagnostic("error", path, "tabs are not allowed in frontmatter"))
    return lines[1:end], "\n".join(lines[end + 1 :]), diagnostics


def _parse_flat(path: Path) -> tuple[dict[str, Any], str, list[Diagnostic]]:
    lines, body, diagnostics = _frontmatter(path)
    fields: dict[str, Any] = {}
    active_list: str | None = None
    for number, line in enumerate(lines, 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        list_match = re.fullmatch(r"  -\s+(.+)", line)
        if list_match and active_list:
            fields[active_list].append(_scalar(list_match.group(1)))
            continue
        field_match = re.fullmatch(r"([a-z][a-z0-9_]*):(?:\s*(.*))?", line)
        if not field_match:
            diagnostics.append(
                Diagnostic("error", path, f"unsupported frontmatter syntax at line {number}")
            )
            active_list = None
            continue
        key, raw = field_match.groups()
        if key in fields:
            diagnostics.append(Diagnostic("error", path, f"duplicate frontmatter key: {key}"))
        if raw:
            fields[key] = _scalar(raw)
            active_list = None
        else:
            fields[key] = []
            active_list = key
    return fields, body, diagnostics


def parse_profile(path: Path) -> tuple[Profile | None, list[Diagnostic]]:
    """Parse planning-owned fields while preserving governance-owned sections as opaque."""
    lines, _, diagnostics = _frontmatter(path)
    top: dict[str, Any] = {}
    dimensions: dict[str, dict[str, Any]] = {}
    section: str | None = None
    current_dimension: str | None = None
    current_record: dict[str, str] | None = None
    in_catalog = False

    for number, line in enumerate(lines, 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0:
            current_dimension = None
            current_record = None
            in_catalog = False
            if stripped == "dimensions:":
                section = "dimensions"
                continue
            if stripped in {"git_governance:", "version_governance:"}:
                section = "opaque"
                continue
            section = None
            match = re.fullmatch(
                r"(schema_version|profile|project_key|qualified_ids_from|canonical_ids_from|last_work_item_sequence):\s*(.+)",
                stripped,
            )
            if not match:
                diagnostics.append(Diagnostic("error", path, f"unsupported profile key at line {number}"))
                continue
            key, raw = match.groups()
            if key in top:
                diagnostics.append(Diagnostic("error", path, f"duplicate profile key: {key}"))
            top[key] = _scalar(raw)
            continue
        if section == "opaque":
            continue
        if section != "dimensions":
            diagnostics.append(Diagnostic("error", path, f"content outside dimensions at line {number}"))
            continue
        dimension_match = re.fullmatch(r"  ([a-z]+):", line)
        if dimension_match:
            name = dimension_match.group(1)
            if name not in DIMENSIONS:
                diagnostics.append(Diagnostic("error", path, f"unknown dimension: {name}"))
            if name in dimensions:
                diagnostics.append(Diagnostic("error", path, f"duplicate dimension: {name}"))
            dimensions[name] = {"catalog": []}
            current_dimension = name
            current_record = None
            in_catalog = False
            continue
        if current_dimension is None:
            diagnostics.append(Diagnostic("error", path, f"dimension content has no owner at line {number}"))
            continue
        mode_match = re.fullmatch(r"    mode:\s*(required|optional)", line)
        if mode_match:
            dimensions[current_dimension]["mode"] = mode_match.group(1)
            continue
        if line == "    catalog:":
            in_catalog = True
            current_record = None
            continue
        record_match = re.fullmatch(r"      - id:\s*(.+)", line)
        if record_match and in_catalog:
            current_record = {"id": str(_scalar(record_match.group(1)))}
            dimensions[current_dimension]["catalog"].append(current_record)
            continue
        property_match = re.fullmatch(r"        (title|definition|starts_on|ends_on):\s*(.+)", line)
        if property_match and current_record is not None:
            key, raw = property_match.groups()
            current_record[key] = str(_scalar(raw))
            continue
        diagnostics.append(Diagnostic("error", path, f"unsupported profile syntax at line {number}"))

    schema = top.get("schema_version")
    if schema not in {1, 2, 3}:
        diagnostics.append(Diagnostic("error", path, "schema_version must be 1, 2, or 3"))
    name = top.get("profile")
    if name not in {*PRESETS, "custom"}:
        diagnostics.append(Diagnostic("error", path, "profile must be minimal, phased, sprint, product, or custom"))

    project_key: str | None = None
    qualified: datetime | None = None
    canonical: datetime | None = None
    sequence: int | None = None
    if schema == 1:
        for field in ("project_key", "qualified_ids_from", "canonical_ids_from", "last_work_item_sequence"):
            if field in top:
                diagnostics.append(Diagnostic("error", path, f"{field} is not supported by schema_version 1"))
    elif schema in {2, 3}:
        raw_key = top.get("project_key")
        if not isinstance(raw_key, str) or not ID_PATTERN.fullmatch(raw_key) or not 2 <= len(raw_key) <= 16:
            diagnostics.append(Diagnostic("error", path, "project_key must be a 2-16 character lowercase kebab slug"))
        else:
            project_key = raw_key
        cutoff_field = "qualified_ids_from" if schema == 2 else "canonical_ids_from"
        raw_cutoff = top.get(cutoff_field)
        if not isinstance(raw_cutoff, str) or not RFC3339_PATTERN.fullmatch(raw_cutoff):
            diagnostics.append(Diagnostic("error", path, f"{cutoff_field} must be an RFC 3339 timestamp"))
        else:
            parsed = datetime.fromisoformat(raw_cutoff.replace("Z", "+00:00"))
            if schema == 2:
                qualified = parsed
            else:
                canonical = parsed
        if schema == 2:
            for field in ("canonical_ids_from", "last_work_item_sequence"):
                if field in top:
                    diagnostics.append(Diagnostic("error", path, f"{field} requires schema_version 3"))
        else:
            raw_sequence = top.get("last_work_item_sequence")
            if not isinstance(raw_sequence, int) or not 0 <= raw_sequence <= 99999:
                diagnostics.append(Diagnostic("error", path, "last_work_item_sequence must be between 0 and 99999"))
            else:
                sequence = raw_sequence
            if "qualified_ids_from" in top:
                diagnostics.append(Diagnostic("error", path, "qualified_ids_from is supported only by schema_version 2"))

    parsed_dimensions: dict[str, Dimension] = {}
    for dimension, raw in dimensions.items():
        mode = raw.get("mode")
        catalog = raw.get("catalog", [])
        if mode not in {"required", "optional"}:
            diagnostics.append(Diagnostic("error", path, f"{dimension} must declare a mode"))
            continue
        if not catalog:
            diagnostics.append(Diagnostic("error", path, f"enabled dimension {dimension} requires a catalog"))
        records: dict[str, dict[str, str]] = {}
        for record in catalog:
            record_id = record.get("id", "")
            if not ID_PATTERN.fullmatch(record_id):
                diagnostics.append(Diagnostic("error", path, f"invalid {dimension} catalog id: {record_id!r}"))
            if record_id in records:
                diagnostics.append(Diagnostic("error", path, f"duplicate {dimension} catalog id: {record_id}"))
            for required in ("title", "definition"):
                if not record.get(required, "").strip():
                    diagnostics.append(Diagnostic("error", path, f"{dimension} catalog {record_id!r} needs {required}"))
            if dimension != "sprint" and ({"starts_on", "ends_on"} & record.keys()):
                diagnostics.append(Diagnostic("error", path, f"dates are supported only for sprint catalogs"))
            if dimension == "sprint":
                parsed_dates: dict[str, date] = {}
                for field in ("starts_on", "ends_on"):
                    if field in record:
                        try:
                            parsed_dates[field] = date.fromisoformat(record[field])
                        except ValueError:
                            diagnostics.append(Diagnostic("error", path, f"{dimension} catalog {record_id!r} has invalid {field}"))
                if parsed_dates.get("ends_on") and parsed_dates.get("starts_on") and parsed_dates["ends_on"] < parsed_dates["starts_on"]:
                    diagnostics.append(Diagnostic("error", path, f"sprint catalog {record_id!r} ends before it starts"))
            records[record_id] = record
        parsed_dimensions[dimension] = Dimension(str(mode), records)

    expected = PRESETS.get(str(name))
    if expected is not None:
        observed = {key: value.mode for key, value in parsed_dimensions.items()}
        if observed != expected:
            diagnostics.append(Diagnostic("error", path, f"profile {name} requires dimensions {expected}"))
    if any(item.severity == "error" for item in diagnostics):
        return None, diagnostics
    return Profile(int(schema), str(name), parsed_dimensions, project_key, qualified, canonical, sequence), diagnostics


def _recognized(path: Path) -> bool:
    work_id = path.name.split(".", 1)[0]
    return bool(
        LEGACY_LOCAL_PATTERN.fullmatch(work_id)
        or LEGACY_QUALIFIED_PATTERN.fullmatch(work_id)
        or CANONICAL_PATTERN.fullmatch(work_id)
    )


def _work_item(path: Path, plans_root: Path, profile: Profile | None) -> tuple[WorkItem, list[Diagnostic]]:
    fields, body, diagnostics = _parse_flat(path)
    relative = path.relative_to(plans_root)
    lifecycle = relative.parts[0]
    compacted = relative.parts[:2] == ("archived", "history")
    item = WorkItem(path, lifecycle, compacted, fields, body)
    for required in ("work_item_id", "title", "depends_on", "target_paths", "created_at", "updated_at"):
        if required not in fields:
            diagnostics.append(Diagnostic("error", path, f"missing required field: {required}"))
    work_id = item.work_item_id
    filename_id = path.name.split(".", 1)[0]
    if work_id and filename_id != work_id:
        diagnostics.append(Diagnostic("error", path, "filename must begin with work_item_id"))
    canonical = CANONICAL_PATTERN.fullmatch(work_id)
    local_legacy = LEGACY_LOCAL_PATTERN.fullmatch(work_id)
    qualified_legacy = LEGACY_QUALIFIED_PATTERN.fullmatch(work_id)
    if work_id and not (canonical or local_legacy or qualified_legacy):
        diagnostics.append(Diagnostic("error", path, f"unsupported work_item_id: {work_id}"))
    if canonical and profile and profile.schema_version == 3:
        if canonical.group("project_key") != profile.project_key:
            diagnostics.append(Diagnostic("error", path, f"work_item_id project key must match {profile.project_key!r}"))
        if profile.last_work_item_sequence is not None and int(canonical.group("sequence")) > profile.last_work_item_sequence:
            diagnostics.append(Diagnostic("error", path, "work_item_id sequence exceeds last_work_item_sequence"))
    if qualified_legacy and profile and profile.project_key and qualified_legacy.group("project_key") != profile.project_key:
        diagnostics.append(Diagnostic("error", path, f"legacy work_item_id project key must match {profile.project_key!r}"))
    created = fields.get("created_at")
    if (local_legacy or qualified_legacy) and isinstance(created, str) and RFC3339_PATTERN.fullmatch(created):
        cutoff = profile.qualified_ids_from if profile and profile.schema_version == 2 and local_legacy else profile.canonical_ids_from if profile and profile.schema_version == 3 else None
        cutoff_name = "qualified_ids_from" if profile and profile.schema_version == 2 else "canonical_ids_from"
        if cutoff and datetime.fromisoformat(created.replace("Z", "+00:00")) >= cutoff:
            diagnostics.append(Diagnostic("error", path, f"legacy work_item_id is not allowed on or after {cutoff_name}"))
    if "status" in fields:
        diagnostics.append(Diagnostic("error", path, "status is forbidden; directory is authoritative"))
    for key in ("depends_on", "target_paths"):
        if not isinstance(fields.get(key), list):
            diagnostics.append(Diagnostic("error", path, f"{key} must be a YAML list"))
    for key in ("created_at", "updated_at"):
        value = fields.get(key)
        if not isinstance(value, str) or not RFC3339_PATTERN.fullmatch(value):
            diagnostics.append(Diagnostic("error", path, f"{key} must be an RFC 3339 timestamp"))
    for target in fields.get("target_paths", []) if isinstance(fields.get("target_paths"), list) else []:
        value = str(target)
        pure = PurePosixPath(value)
        if not value or value == "." or pure.is_absolute() or ".." in pure.parts or "\\" in value:
            diagnostics.append(Diagnostic("error", path, f"target path must be repository-relative: {value!r}"))
    title = fields.get("title")
    if isinstance(title, str) and not re.search(rf"(?m)^# {re.escape(title)}\s*$", body):
        diagnostics.append(Diagnostic("error", path, "first heading must match title"))
    return item, diagnostics


def _validate_dimensions(item: WorkItem, profile: Profile | None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if profile is None:
        for field in DIMENSION_FIELDS.values():
            if field in item.fields:
                diagnostics.append(Diagnostic("warning", item.path, f"legacy {field} has no _notes/GOVERNANCE.md catalog"))
        return diagnostics
    for dimension, field in DIMENSION_FIELDS.items():
        configured = profile.dimensions.get(dimension)
        value = item.fields.get(field)
        severity = "warning" if item.lifecycle == "archived" else "error"
        suffix = " in archived history" if severity == "warning" else ""
        if configured is None:
            if field in item.fields:
                diagnostics.append(Diagnostic(severity, item.path, f"{field} is disabled by the profile{suffix}"))
            continue
        if configured.mode == "required" and field not in item.fields:
            diagnostics.append(Diagnostic(severity, item.path, f"required profile field is missing: {field}{suffix}"))
            continue
        if field not in item.fields:
            continue
        values: list[str]
        if dimension == "feature":
            if not isinstance(value, list) or not value:
                diagnostics.append(Diagnostic(severity, item.path, f"feature_ids must be a non-empty list{suffix}"))
                continue
            values = [str(entry) for entry in value]
            if len(values) != len(set(values)):
                diagnostics.append(Diagnostic(severity, item.path, f"feature_ids must be unique{suffix}"))
        else:
            if not isinstance(value, str) or not value:
                diagnostics.append(Diagnostic(severity, item.path, f"{field} must be one ID{suffix}"))
                continue
            values = [value]
        for value_id in values:
            if value_id not in configured.catalog:
                diagnostics.append(Diagnostic(severity, item.path, f"{field} references undeclared {dimension} id: {value_id}{suffix}"))
    return diagnostics


def _successful_archive(item: WorkItem) -> bool:
    if item.lifecycle != "archived":
        return False
    match = re.search(r"(?m)^- Result:\s*(.+?)\s*$", item.body)
    return bool(match and match.group(1).strip().lower() not in {"", "—", "-", "cancelled", "canceled", "superseded"})


def _links(path: Path) -> list[str]:
    try:
        return re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
    except OSError:
        return []


def next_work_item_id(profile: Profile, highest_visible_sequence: int = 0) -> str:
    if profile.schema_version != 3 or not profile.project_key or profile.last_work_item_sequence is None:
        raise ValueError("schema_version 3 project identity is required")
    sequence = max(profile.last_work_item_sequence, highest_visible_sequence)
    if sequence >= 99999:
        raise ValueError("work-item sequence space is exhausted; a schema revision is required")
    return f"{profile.project_key}-{sequence + 1:05d}"


def validate_workspace(root: Path) -> list[Diagnostic]:
    root = root.resolve()
    plans_root = root / "_notes" / "plans"
    diagnostics: list[Diagnostic] = []
    if not plans_root.is_dir():
        return [Diagnostic("error", plans_root, "missing _notes/plans directory")]
    profile_path = root / "_notes" / "GOVERNANCE.md"
    for legacy in (plans_root / "GOVERNANCE.md", plans_root / "PLANNING.md"):
        if legacy.exists():
            diagnostics.append(Diagnostic("error", legacy, "legacy governance file must be moved to _notes/GOVERNANCE.md"))
    profile: Profile | None = None
    if profile_path.exists():
        profile, profile_diagnostics = parse_profile(profile_path)
        diagnostics.extend(profile_diagnostics)
        if profile and profile.schema_version == 3 and profile.last_work_item_sequence == 99999:
            diagnostics.append(Diagnostic("warning", profile_path, "work-item sequence space is exhausted; define a later schema before creating more work"))

    current_paths: list[Path] = []
    for lifecycle in ("backlog", "ready", "active", "archived"):
        directory = plans_root / lifecycle
        if not directory.is_dir():
            diagnostics.append(Diagnostic("error", directory, "missing lifecycle directory"))
            continue
        current_paths.extend(path for path in sorted(directory.glob("*.md")) if _recognized(path))
    history_paths = [path for path in sorted((plans_root / "archived" / "history").glob("**/*.md")) if _recognized(path)]
    items: list[WorkItem] = []
    for path in current_paths + history_paths:
        item, item_diagnostics = _work_item(path, plans_root, profile)
        items.append(item)
        diagnostics.extend(item_diagnostics)
        diagnostics.extend(_validate_dimensions(item, profile))

    by_id: dict[str, WorkItem] = {}
    for item in items:
        if item.work_item_id in by_id:
            diagnostics.append(Diagnostic("error", item.path, f"duplicate work_item_id: {item.work_item_id}"))
        elif item.work_item_id:
            by_id[item.work_item_id] = item
    for item in items:
        dependencies = item.fields.get("depends_on", [])
        if not isinstance(dependencies, list):
            continue
        if len(dependencies) != len(set(map(str, dependencies))):
            diagnostics.append(Diagnostic("error", item.path, "depends_on values must be unique"))
        satisfied = True
        for dependency in map(str, dependencies):
            target = by_id.get(dependency)
            if target is None:
                diagnostics.append(Diagnostic("error", item.path, f"dependency does not resolve: {dependency}"))
                satisfied = False
            elif not _successful_archive(target):
                satisfied = False
        if item.lifecycle == "ready" and not satisfied:
            diagnostics.append(Diagnostic("error", item.path, "ready item has unsatisfied dependencies"))
        if item.lifecycle == "backlog" and satisfied:
            diagnostics.append(Diagnostic("error", item.path, "backlog item has satisfied dependencies"))

    index_path = plans_root / "PLAN.md"
    if not index_path.is_file():
        diagnostics.append(Diagnostic("error", index_path, "missing work-item index"))
        return diagnostics
    index_text = index_path.read_text(encoding="utf-8")
    for heading in ("Backlog", "Ready", "Active", "Archived"):
        if not re.search(rf"(?m)^## {heading}\s*$", index_text):
            diagnostics.append(Diagnostic("error", index_path, f"missing index heading: {heading}"))
    resolved: list[Path] = []
    for link in _links(index_path):
        if re.match(r"^[a-z]+://", link) or link.startswith("#"):
            continue
        target = (index_path.parent / link.split("#", 1)[0]).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            diagnostics.append(Diagnostic("error", index_path, f"index link escapes consumer root: {link}"))
            continue
        resolved.append(target)
        if not target.exists():
            diagnostics.append(Diagnostic("error", index_path, f"broken index link: {link}"))
    for path in current_paths:
        count = resolved.count(path.resolve())
        if count != 1:
            diagnostics.append(Diagnostic("error", index_path, f"{path.relative_to(plans_root)} is indexed {count} times"))
    history_root = plans_root / "archived" / "history"
    summaries_root = plans_root / "archived" / "summaries"
    if history_root.is_dir():
        for cycle in sorted(path for path in history_root.iterdir() if path.is_dir()):
            if not any(_recognized(path) for path in cycle.glob("**/*.md")):
                continue
            summary = summaries_root / f"{cycle.name}.md"
            if not summary.is_file():
                diagnostics.append(Diagnostic("error", cycle, "compacted cycle has no matching summary"))
            elif resolved.count(summary.resolve()) != 1:
                diagnostics.append(Diagnostic("error", index_path, f"summary {summary.name} must be indexed exactly once"))
    return diagnostics


def _print(diagnostics: Iterable[Diagnostic], base: Path) -> tuple[int, int]:
    errors = warnings = 0
    for diagnostic in sorted(diagnostics, key=lambda item: (item.severity, str(item.path), item.message)):
        try:
            display = diagnostic.path.relative_to(base.resolve())
        except ValueError:
            display = diagnostic.path
        print(f"{diagnostic.severity.upper()} {display}: {diagnostic.message}")
        if diagnostic.severity == "error":
            errors += 1
        else:
            warnings += 1
    print(f"Validation complete: {errors} error(s), {warnings} warning(s)")
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args(argv)
    diagnostics = validate_workspace(args.root)
    errors, _ = _print(diagnostics, args.root)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
