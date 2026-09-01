#!/usr/bin/env python3
"""Retrieve or validate Delivery Spine projections and transition evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from delivery_spine_projection import (
    DEFAULT_ADAPTER_ROOT,
    ShardedAdapter,
    impacted_registrations,
    safe_relative_path as projection_safe_relative_path,
    validate_claim,
)


LEVELS = ("source_complete", "integrated", "staging_verified")
LEVEL_RANK = {name: index for index, name in enumerate(LEVELS)}
EVIDENCE_CLASSES = ("component", "contract", "integrated_local", "staging_e2e")
BOUNDARY_STATES = ("missing", "source_only", "configured", "deployed", "verified")
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORK_ITEM_DIRS = ("backlog", "ready", "active", "archived")
BLOCKER_STATES = ("detected", "investigating", "owner_assigned", "waiting_for_human", "implementation_pending", "verified", "resumed")
UNRESOLVED_BLOCKER_STATES = set(BLOCKER_STATES[:5])
DEFAULT_MANIFEST_PATH = "_notes/delivery-spine.json"


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    subject: str
    message: str


@dataclass(frozen=True)
class WorkItem:
    work_item_id: str
    lifecycle: str
    path: Path
    body: str
    delivery: dict[str, str]


def section(body: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", body, re.MULTILINE)
    if not match:
        return ""
    remainder = body[match.end() :]
    next_heading = re.search(r"^## \S", remainder, re.MULTILINE)
    return remainder[: next_heading.start()] if next_heading else remainder


def delivery_fields(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in re.findall(r"^- ([A-Za-z][A-Za-z ]+):\s*(.+?)\s*$", section(body, "Delivery spine"), re.MULTILINE):
        result[key.lower().replace(" ", "_")] = value.strip(" `")
    return result


def parse_work_item(path: Path, lifecycle: str) -> WorkItem | None:
    text = path.read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not frontmatter:
        return None
    identity = re.search(r'^work_item_id:\s*["\']?([^"\'\n]+)', frontmatter.group(1), re.MULTILINE)
    if not identity:
        return None
    body = frontmatter.group(2)
    return WorkItem(identity.group(1).strip(), lifecycle, path, body, delivery_fields(body))


def load_work_items(root: Path) -> tuple[dict[str, WorkItem], list[Diagnostic]]:
    items: dict[str, WorkItem] = {}
    diagnostics: list[Diagnostic] = []
    plans = root / "_notes" / "plans"
    for lifecycle in WORK_ITEM_DIRS:
        directory = plans / lifecycle
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            item = parse_work_item(path, lifecycle)
            if not item:
                diagnostics.append(Diagnostic("error", str(path), "cannot parse work_item_id and body"))
                continue
            if item.work_item_id in items:
                diagnostics.append(Diagnostic("error", item.work_item_id, "duplicate direct lifecycle work item"))
            items[item.work_item_id] = item
    return items, diagnostics


def safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def valid_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def blocker_state(body: str) -> str | None:
    content = section(body, "Blocker resolution")
    if not content:
        return None
    match = re.search(r"^- State:\s*([^\n]+?)\s*$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def placeholder_paths(root: Path, item: WorkItem) -> list[str]:
    found: list[str] = []
    for raw_path in item.path.read_text(encoding="utf-8").split("target_paths:", 1)[-1].split("created_at:", 1)[0].splitlines():
        match = re.match(r'^\s+-\s+"?([^"\n]+)', raw_path)
        if not match:
            continue
        candidate = root / match.group(1).strip()
        files = [candidate] if candidate.is_file() else list(candidate.rglob("*.json")) if candidate.is_dir() else []
        for path in files:
            if path.name.endswith(".example.json"):
                continue
            try:
                if "REPLACE_WITH_" in path.read_text(encoding="utf-8"):
                    found.append(str(path.relative_to(root)))
            except UnicodeDecodeError:
                continue
    return sorted(set(found))


def resolve_manifest_path(root: Path, value: str) -> tuple[Path | None, list[Diagnostic]]:
    if not safe_relative_path(value):
        return None, [Diagnostic("error", value, "manifest path must be a relative POSIX path without traversal or backslashes")]
    path = (root / PurePosixPath(value)).resolve(strict=False)
    if not path.is_relative_to(root):
        return None, [Diagnostic("error", value, "manifest path escapes the consumer root through a symlink")]
    return path, []


def load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [Diagnostic("error", str(path), f"cannot read manifest: {exc}")]
    except json.JSONDecodeError as exc:
        return None, [Diagnostic("error", str(path), f"invalid JSON: {exc}")]
    if not isinstance(data, dict):
        return None, [Diagnostic("error", str(path), "manifest must be an object")]
    return data, []


def validate_manifest(data: dict[str, Any], items: dict[str, WorkItem]) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    journeys_by_id: dict[str, dict[str, Any]] = {}
    if data.get("schema_version") != 1:
        diagnostics.append(Diagnostic("error", "manifest", "schema_version must be 1"))
    active_slice = data.get("active_staging_slice")
    if active_slice is not None and (not isinstance(active_slice, str) or not ID_PATTERN.fullmatch(active_slice)):
        diagnostics.append(Diagnostic("error", "manifest", "active_staging_slice must be a journey ID or null"))
    journeys = data.get("journeys")
    if not isinstance(journeys, list):
        return {}, diagnostics + [Diagnostic("error", "manifest", "journeys must be an array")]

    required = {"journey_id", "outcome", "work_item_id", "target_level", "current_level", "boundaries", "evidence", "blockers", "affected_paths"}
    for index, raw in enumerate(journeys):
        subject = f"journeys[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(Diagnostic("error", subject, "journey must be an object"))
            continue
        missing = sorted(required - raw.keys())
        extra = sorted(raw.keys() - required)
        if missing:
            diagnostics.append(Diagnostic("error", subject, f"missing fields: {', '.join(missing)}"))
        if extra:
            diagnostics.append(Diagnostic("error", subject, f"unknown fields: {', '.join(extra)}"))
        journey_id = raw.get("journey_id")
        if not isinstance(journey_id, str) or not ID_PATTERN.fullmatch(journey_id):
            diagnostics.append(Diagnostic("error", subject, "journey_id is invalid"))
            continue
        if journey_id in journeys_by_id:
            diagnostics.append(Diagnostic("error", journey_id, "duplicate journey_id"))
        journeys_by_id[journey_id] = raw
        if not isinstance(raw.get("outcome"), str) or not raw["outcome"].strip():
            diagnostics.append(Diagnostic("error", journey_id, "outcome must be non-empty"))
        work_item_id = raw.get("work_item_id")
        if not isinstance(work_item_id, str) or work_item_id not in items:
            diagnostics.append(Diagnostic("error", journey_id, f"work_item_id does not resolve: {work_item_id}"))
        target = raw.get("target_level")
        current = raw.get("current_level")
        if target not in LEVELS:
            diagnostics.append(Diagnostic("error", journey_id, "target_level is invalid"))
        if current not in LEVELS:
            diagnostics.append(Diagnostic("error", journey_id, "current_level is invalid"))
        if target in LEVELS and current in LEVELS and LEVEL_RANK[current] > LEVEL_RANK[target]:
            diagnostics.append(Diagnostic("error", journey_id, "current_level exceeds target_level"))

        boundaries = raw.get("boundaries")
        if not isinstance(boundaries, list) or not boundaries:
            diagnostics.append(Diagnostic("error", journey_id, "boundaries must be a non-empty array"))
        else:
            names: set[str] = set()
            for boundary in boundaries:
                if not isinstance(boundary, dict) or set(boundary) != {"name", "owner", "target", "state"}:
                    diagnostics.append(Diagnostic("error", journey_id, "each boundary requires only name, owner, target, and state"))
                    continue
                name = boundary.get("name")
                if not isinstance(name, str) or not name.strip() or name in names:
                    diagnostics.append(Diagnostic("error", journey_id, "boundary names must be non-empty and unique"))
                else:
                    names.add(name)
                if not isinstance(boundary.get("owner"), str) or not boundary["owner"].strip():
                    diagnostics.append(Diagnostic("error", journey_id, "boundary owner must be non-empty"))
                if not isinstance(boundary.get("target"), str) or not boundary["target"].strip():
                    diagnostics.append(Diagnostic("error", journey_id, "boundary target must be non-empty"))
                if boundary.get("state") not in BOUNDARY_STATES:
                    diagnostics.append(Diagnostic("error", journey_id, "boundary state is invalid"))

        evidence = raw.get("evidence")
        evidence_classes: set[str] = set()
        if not isinstance(evidence, list):
            diagnostics.append(Diagnostic("error", journey_id, "evidence must be an array"))
        else:
            for record in evidence:
                if not isinstance(record, dict) or set(record) != {"class", "reference", "observed_at"}:
                    diagnostics.append(Diagnostic("error", journey_id, "each evidence record requires only class, reference, and observed_at"))
                    continue
                evidence_class = record.get("class")
                if evidence_class not in EVIDENCE_CLASSES:
                    diagnostics.append(Diagnostic("error", journey_id, "evidence class is invalid"))
                else:
                    evidence_classes.add(evidence_class)
                if not isinstance(record.get("reference"), str) or not record["reference"].strip():
                    diagnostics.append(Diagnostic("error", journey_id, "evidence reference must be non-empty"))
                if not valid_time(record.get("observed_at")):
                    diagnostics.append(Diagnostic("error", journey_id, "evidence observed_at must be RFC 3339"))
        if current == "integrated" and not ({"integrated_local", "staging_e2e"} & evidence_classes):
            diagnostics.append(Diagnostic("error", journey_id, "integrated requires integrated_local or staging_e2e evidence"))
        if current == "staging_verified" and "staging_e2e" not in evidence_classes:
            diagnostics.append(Diagnostic("error", journey_id, "staging_verified requires staging_e2e evidence"))

        for field in ("blockers", "affected_paths"):
            value = raw.get(field)
            if not isinstance(value, list) or (field == "affected_paths" and not value):
                diagnostics.append(Diagnostic("error", journey_id, f"{field} must be {'a non-empty' if field == 'affected_paths' else 'an'} array"))
                continue
            if any(not isinstance(entry, str) or not entry.strip() for entry in value):
                diagnostics.append(Diagnostic("error", journey_id, f"{field} entries must be non-empty strings"))
        if isinstance(raw.get("affected_paths"), list):
            for path in raw["affected_paths"]:
                if not safe_relative_path(path):
                    diagnostics.append(Diagnostic("error", journey_id, f"affected path is not repository-relative: {path}"))

    if active_slice is not None and active_slice not in journeys_by_id:
        diagnostics.append(Diagnostic("error", "manifest", "active_staging_slice does not resolve"))
    elif active_slice is not None:
        journey = journeys_by_id[active_slice]
        owner = items.get(str(journey.get("work_item_id")))
        if journey.get("target_level") != "staging_verified":
            diagnostics.append(Diagnostic("error", active_slice, "active staging slice must target staging_verified"))
        if owner and owner.lifecycle != "active":
            diagnostics.append(Diagnostic("error", active_slice, "active staging slice owner must be in active/"))

    active_claims = []
    for item in items.values():
        if item.lifecycle == "active" and item.delivery.get("target_evidence") == "staging_verified":
            active_claims.append(item.delivery.get("journey_id", item.work_item_id))
    if active_slice is None and active_claims:
        diagnostics.append(Diagnostic("error", "manifest", "active staging work exists but active_staging_slice is null"))
    if active_slice is not None and sorted(active_claims) != [active_slice]:
        diagnostics.append(Diagnostic("error", "manifest", f"active staging claims must be exactly {active_slice}: {active_claims}"))

    for journey_id, journey in journeys_by_id.items():
        owner = items.get(str(journey.get("work_item_id")))
        if not owner:
            continue
        if owner.delivery.get("journey_id") != journey_id:
            diagnostics.append(Diagnostic("error", owner.work_item_id, "Delivery spine Journey ID does not match manifest"))
        if owner.delivery.get("target_evidence") != journey.get("target_level"):
            diagnostics.append(Diagnostic("error", owner.work_item_id, "Delivery spine Target evidence does not match manifest"))
        if not owner.delivery.get("integration_consumer"):
            diagnostics.append(Diagnostic("error", owner.work_item_id, "Delivery spine Integration consumer is required"))
    return journeys_by_id, diagnostics


def transition_diagnostics(
    transition: str,
    work_item_id: str,
    items: dict[str, WorkItem],
    journeys: dict[str, dict[str, Any]],
    active_slice: str | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    item = items.get(work_item_id)
    if not item:
        return [Diagnostic("error", work_item_id, "work item does not resolve")]
    if transition == "start" and item.lifecycle != "ready":
        diagnostics.append(Diagnostic("error", work_item_id, "start transition requires ready/ lifecycle"))
    if transition == "archive" and item.lifecycle != "active":
        diagnostics.append(Diagnostic("error", work_item_id, "archive transition requires active/ lifecycle"))

    target = item.delivery.get("target_evidence")
    journey_id = item.delivery.get("journey_id")
    if target and target not in LEVELS:
        diagnostics.append(Diagnostic("error", work_item_id, "Target evidence is invalid"))
    if target == "source_complete" and journey_id == "none" and item.delivery.get("integration_consumer") in (None, "none", "self"):
        diagnostics.append(Diagnostic("error", work_item_id, "source-only work with no journey must name an exact integration consumer"))
    if target in ("integrated", "staging_verified"):
        if not journey_id or journey_id == "none":
            diagnostics.append(Diagnostic("error", work_item_id, "integrated or staging work requires a registered journey"))
        if transition == "start":
            preflight = section(item.body, "Integration preflight")
            if not preflight:
                diagnostics.append(Diagnostic("error", work_item_id, "Integration preflight section is required"))
            elif re.search(r"^- \[ \]", preflight, re.MULTILINE):
                diagnostics.append(Diagnostic("error", work_item_id, "Integration preflight has unchecked criteria"))
    if transition == "start" and target == "staging_verified" and active_slice not in (None, journey_id):
        diagnostics.append(Diagnostic("error", work_item_id, f"staging slot is owned by {active_slice}"))
    if transition == "start":
        placeholders = placeholder_paths(items[work_item_id].path.parents[3], item)
        if placeholders:
            diagnostics.append(Diagnostic("error", work_item_id, f"required configuration still has placeholders: {', '.join(placeholders)}"))

    if transition == "archive":
        state = blocker_state(item.body)
        if state is not None and (state == "" or state not in BLOCKER_STATES):
            diagnostics.append(Diagnostic("error", work_item_id, "Blocker resolution State is invalid"))
        elif state in UNRESOLVED_BLOCKER_STATES:
            diagnostics.append(Diagnostic("error", work_item_id, f"unresolved blocker state prevents archive: {state}"))
        for heading in ("Acceptance criteria", "Verification"):
            content = section(item.body, heading)
            if not content:
                diagnostics.append(Diagnostic("error", work_item_id, f"{heading} section is required"))
            elif re.search(r"^- \[ \]", content, re.MULTILINE):
                diagnostics.append(Diagnostic("error", work_item_id, f"{heading} contains unchecked criteria"))
        completion = section(item.body, "Completion record")
        for label in ("Result", "Evidence"):
            match = re.search(rf"^- {label}:\s*(.*?)\s*$", completion, re.MULTILINE)
            value = match.group(1).strip() if match else ""
            if not value or value in {"—", "-", "Active", "Active."}:
                diagnostics.append(Diagnostic("error", work_item_id, f"Completion {label.lower()} is missing or placeholder"))
        if journey_id and journey_id in journeys and target in LEVELS:
            current = journeys[journey_id].get("current_level")
            if current not in LEVELS or LEVEL_RANK[current] < LEVEL_RANK[target]:
                diagnostics.append(Diagnostic("error", work_item_id, f"manifest current level {current} does not satisfy {target}"))
    return diagnostics


def impacted_journeys(paths: Iterable[str], journeys: dict[str, dict[str, Any]]) -> list[str]:
    normalized = [PurePosixPath(path) for path in paths if safe_relative_path(path)]
    impacted: list[str] = []
    for journey_id, journey in journeys.items():
        prefixes = [PurePosixPath(path) for path in journey.get("affected_paths", []) if safe_relative_path(path)]
        if any(changed == prefix or prefix in changed.parents or changed in prefix.parents for changed in normalized for prefix in prefixes):
            impacted.append(journey_id)
    return sorted(impacted)


def emit(diagnostics: list[Diagnostic], *, limit: int = 100) -> int:
    ordered = sorted(diagnostics, key=lambda value: (value.severity, value.subject, value.message))
    for diagnostic in ordered[:limit]:
        print(f"{diagnostic.severity}: {diagnostic.subject}: {diagnostic.message}")
    errors = sum(diagnostic.severity == "error" for diagnostic in diagnostics)
    if len(ordered) > limit:
        print(f"diagnostics omitted: {len(ordered) - limit}")
    print(f"delivery-spine validation: {errors} error(s)")
    return 1 if errors else 0


def validate_sharded_projection(
    adapter: ShardedAdapter,
    items: dict[str, WorkItem],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], str | None, list[Diagnostic]]:
    journeys, diagnostics = adapter.registry()
    indexed, by_work_item, active_slice, found = adapter.claim_index()
    diagnostics.extend(found)
    archived_work_items: set[str] = set()

    for journey_id, entry in indexed.items():
        if journey_id not in journeys:
            diagnostics.append(Diagnostic("error", journey_id, "current claim journey is not registered"))
        claim, claim_diagnostics = adapter.claim(journey_id)
        diagnostics.extend(claim_diagnostics)
        if claim is None:
            continue
        if claim.get("journey_id") != journey_id:
            diagnostics.append(Diagnostic("error", journey_id, "claim journey_id does not match its index entry"))
        if claim.get("work_item_id") != entry.get("work_item_id"):
            diagnostics.append(Diagnostic("error", journey_id, "claim work_item_id does not match its index entry"))
        owner = items.get(str(claim.get("work_item_id")))
        if not owner:
            diagnostics.append(Diagnostic("error", journey_id, f"work_item_id does not resolve: {claim.get('work_item_id')}"))
            continue
        if owner.lifecycle == "archived":
            diagnostics.append(Diagnostic("error", journey_id, "completed WorkItem remains in the current claim working set"))
        if owner.delivery.get("journey_id") != journey_id:
            diagnostics.append(Diagnostic("error", owner.work_item_id, "Delivery spine Journey ID does not match claim"))
        if owner.delivery.get("target_evidence") != claim.get("target_level"):
            diagnostics.append(Diagnostic("error", owner.work_item_id, "Delivery spine Target evidence does not match claim"))
        if not owner.delivery.get("integration_consumer"):
            diagnostics.append(Diagnostic("error", owner.work_item_id, "Delivery spine Integration consumer is required"))

    for journey_id in journeys:
        baseline, baseline_diagnostics = adapter.baseline(journey_id)
        diagnostics.extend(baseline_diagnostics)
        if baseline is not None and baseline.get("journey_id") != journey_id:
            diagnostics.append(Diagnostic("error", journey_id, "baseline journey_id does not match its filename"))
        if baseline is not None and isinstance(baseline.get("claim_id"), str):
            archived, archive_diagnostics = adapter.archived_claim(journey_id, baseline["claim_id"])
            diagnostics.extend(archive_diagnostics)
            if archived is not None and archived.get("current_level") != baseline.get("current_level"):
                diagnostics.append(Diagnostic("error", journey_id, "baseline level does not match its archived claim"))

    for path in adapter.archive_paths():
        data, archive_diagnostics = adapter.read(str(path.relative_to(adapter.root))) if adapter.root else (None, [])
        diagnostics.extend(archive_diagnostics)
        subject = str(path.relative_to(adapter.root)) if adapter.root else str(path)
        if data is None:
            continue
        diagnostics.extend(validate_claim(data, subject))
        journey_id = data.get("journey_id")
        claim_id = data.get("claim_id")
        if journey_id not in journeys:
            diagnostics.append(Diagnostic("error", subject, "archived claim journey is not registered"))
        if path.parent.name != journey_id or path.stem != claim_id:
            diagnostics.append(Diagnostic("error", subject, "archived claim path does not match its journey_id and claim_id"))
        work_item_id = data.get("work_item_id")
        if isinstance(work_item_id, str):
            if work_item_id in archived_work_items:
                diagnostics.append(Diagnostic("error", work_item_id, "duplicate archived WorkItem claim"))
            archived_work_items.add(work_item_id)
            if work_item_id in by_work_item:
                diagnostics.append(Diagnostic("error", work_item_id, "archived WorkItem also has a current claim"))
            owner = items.get(work_item_id)
            if owner is None:
                diagnostics.append(Diagnostic("error", work_item_id, "archived claim WorkItem does not resolve"))
            elif owner.lifecycle != "archived":
                diagnostics.append(Diagnostic("error", work_item_id, "historical claim requires an archived owner-produced WorkItem"))

    if active_slice is not None:
        active_claim, claim_diagnostics = adapter.claim(active_slice)
        diagnostics.extend(claim_diagnostics)
        if active_claim is not None:
            owner = items.get(str(active_claim.get("work_item_id")))
            if active_claim.get("target_level") != "staging_verified":
                diagnostics.append(Diagnostic("error", active_slice, "active staging slice must target staging_verified"))
            if owner and owner.lifecycle != "active":
                diagnostics.append(Diagnostic("error", active_slice, "active staging slice owner must be in active/"))

    active_claims = sorted(
        item.delivery.get("journey_id", item.work_item_id)
        for item in items.values()
        if item.lifecycle == "active" and item.delivery.get("target_evidence") == "staging_verified"
    )
    if active_slice is None and active_claims:
        diagnostics.append(Diagnostic("error", "claims/index", "active staging work exists but active_staging_slice is null"))
    if active_slice is not None and active_claims != [active_slice]:
        diagnostics.append(Diagnostic("error", "claims/index", f"active staging claims must be exactly {active_slice}: {active_claims}"))
    return journeys, indexed, active_slice, diagnostics


def sharded_selection(
    adapter: ShardedAdapter,
    mode: str,
    *,
    journey_id: str | None,
    work_item_id: str | None,
    claim_id: str | None,
    evidence_reference: str | None,
    dependency: str | None,
    changed_paths: list[str],
) -> tuple[dict[str, Any] | None, str | None, list[Diagnostic]]:
    journeys, diagnostics = adapter.registry()
    if mode == "impact":
        for path in changed_paths:
            if not projection_safe_relative_path(path):
                diagnostics.append(Diagnostic("error", path, "changed path must be repository-relative"))
        impacted = impacted_registrations(changed_paths, journeys)
        return {
            "mode": "impact",
            "impacted": impacted,
            "missing_suite_references": [value["journey_id"] for value in impacted if not value["suites"]],
        }, None, diagnostics

    indexed, by_work_item, active_slice, index_diagnostics = adapter.claim_index()
    diagnostics.extend(index_diagnostics)
    selected_journey = journey_id
    if mode == "work-item":
        if not work_item_id:
            diagnostics.append(Diagnostic("error", "retrieval", "work-item mode requires --work-item"))
        else:
            selected_journey = by_work_item.get(work_item_id)
            if selected_journey is None:
                diagnostics.append(Diagnostic("error", work_item_id, "no current claim matches the WorkItem"))

    if mode in ("target", "work-item"):
        if not selected_journey:
            diagnostics.append(Diagnostic("error", "retrieval", f"{mode} mode requires an exact journey or WorkItem"))
            return None, None, diagnostics
        registration = journeys.get(selected_journey)
        if registration is None:
            diagnostics.append(Diagnostic("error", selected_journey, "journey is not registered"))
            return None, selected_journey, diagnostics
        claim = None
        if selected_journey in indexed:
            claim, found = adapter.claim(selected_journey)
            diagnostics.extend(found)
        baseline, found = adapter.baseline(selected_journey)
        diagnostics.extend(found)
        return {
            "mode": mode,
            "journey": registration,
            "claim": claim,
            "baseline": baseline,
            "active_staging_slice": active_slice,
        }, selected_journey, diagnostics

    if mode == "history":
        if not selected_journey:
            diagnostics.append(Diagnostic("error", "retrieval", "history mode requires --journey"))
            return None, None, diagnostics
        if claim_id:
            claim, found = adapter.archived_claim(selected_journey, claim_id)
            diagnostics.extend(found)
            return {"mode": "history", "journey_id": selected_journey, "claim": claim}, selected_journey, diagnostics
        if evidence_reference or dependency:
            matches: list[dict[str, Any]] = []
            for path in adapter.archive_paths():
                if path.parent.name != selected_journey:
                    continue
                data, found = adapter.read(str(path.relative_to(adapter.root))) if adapter.root else (None, [])
                diagnostics.extend(found)
                evidence_match = evidence_reference and any(
                    record.get("reference") == evidence_reference
                    for record in data.get("evidence", [])
                    if isinstance(record, dict)
                )
                dependency_match = dependency and data and data.get("work_item_id") == dependency
                if data and (evidence_match or dependency_match):
                    matches.append(data)
            if len(matches) != 1:
                selector = "evidence reference" if evidence_reference else "dependency"
                diagnostics.append(Diagnostic("error", selected_journey, f"{selector} must resolve exactly one archived claim; found {len(matches)}"))
            return {"mode": "history", "journey_id": selected_journey, "claims": matches}, selected_journey, diagnostics
        diagnostics.append(Diagnostic("error", "retrieval", "history mode requires --claim, --dependency, or --evidence-reference"))
        return None, selected_journey, diagnostics

    if mode == "audit":
        records: list[dict[str, Any]] = []
        for path in adapter.archive_paths():
            data, found = adapter.read(str(path.relative_to(adapter.root))) if adapter.root else (None, [])
            diagnostics.extend(found)
            if data is not None:
                records.append(data)
        current: list[dict[str, Any]] = []
        for selected in sorted(indexed):
            data, found = adapter.claim(selected)
            diagnostics.extend(found)
            if data is not None:
                current.append(data)
        baselines: list[dict[str, Any]] = []
        for selected in sorted(journeys):
            data, found = adapter.baseline(selected)
            diagnostics.extend(found)
            if data is not None:
                baselines.append(data)
        return {
            "mode": "audit",
            "registry": list(journeys.values()),
            "current_claims": current,
            "baselines": baselines,
            "archived_claims": records,
        }, None, diagnostics
    return None, None, diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--manifest-path",
        default=DEFAULT_MANIFEST_PATH,
        help=f"consumer-relative manifest path (default: {DEFAULT_MANIFEST_PATH})",
    )
    parser.add_argument("--adapter", choices=("v1", "sharded"), default="v1")
    parser.add_argument(
        "--adapter-root",
        default=DEFAULT_ADAPTER_ROOT,
        help=f"consumer-relative sharded adapter root (default: {DEFAULT_ADAPTER_ROOT})",
    )
    parser.add_argument("--mode", choices=("target", "work-item", "impact", "validation", "history", "audit"), default="validation")
    parser.add_argument("--journey")
    parser.add_argument("--claim")
    parser.add_argument("--evidence-reference")
    parser.add_argument("--dependency", help="exact archived WorkItem dependency reference")
    parser.add_argument("--transition", choices=("start", "archive"))
    parser.add_argument("--work-item")
    parser.add_argument("--changed-path", action="append", default=[])
    args = parser.parse_args(argv)
    if args.transition and not args.work_item:
        parser.error("--transition requires --work-item")
    if args.work_item and not args.transition and args.mode != "work-item":
        parser.error("--work-item without --transition requires --mode work-item")

    root = args.root.resolve()
    if args.changed_path and args.mode == "validation":
        mode = "impact"
    else:
        mode = args.mode
    items: dict[str, WorkItem] = {}
    diagnostics: list[Diagnostic] = []
    if args.adapter == "v1" or args.transition or mode == "validation":
        items, diagnostics = load_work_items(root)

    if args.adapter == "sharded":
        adapter = ShardedAdapter(root, args.adapter_root)
        if args.transition and args.work_item:
            item = items.get(args.work_item)
            journey_id = item.delivery.get("journey_id") if item else None
            journeys_for_gate: dict[str, dict[str, Any]] = {}
            active_slice = None
            if journey_id and journey_id != "none":
                result, selected_journey, found = sharded_selection(
                    adapter,
                    "work-item",
                    journey_id=None,
                    work_item_id=args.work_item,
                    claim_id=None,
                    evidence_reference=None,
                    dependency=None,
                    changed_paths=[],
                )
                diagnostics.extend(found)
                if result is not None:
                    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
                claim = result.get("claim") if result else None
                if selected_journey and claim is not None:
                    journeys_for_gate[selected_journey] = claim
                _, _, active_slice, found = adapter.claim_index()
                diagnostics.extend(found)
            diagnostics.extend(transition_diagnostics(args.transition, args.work_item, items, journeys_for_gate, active_slice))
            return emit(diagnostics)
        if mode == "validation":
            _, _, _, found = validate_sharded_projection(adapter, items)
            diagnostics.extend(found)
        else:
            result, selected_journey, found = sharded_selection(
                adapter,
                mode,
                journey_id=args.journey,
                work_item_id=args.work_item,
                claim_id=args.claim,
                evidence_reference=args.evidence_reference,
                dependency=args.dependency,
                changed_paths=args.changed_path,
            )
            diagnostics.extend(found)
            if result is not None:
                print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return emit(diagnostics)

    manifest_path, path_diagnostics = resolve_manifest_path(root, args.manifest_path)
    diagnostics.extend(path_diagnostics)
    manifest: dict[str, Any] | None = None
    if manifest_path is not None:
        manifest, manifest_diagnostics = load_manifest(manifest_path)
        diagnostics.extend(manifest_diagnostics)
    journeys: dict[str, dict[str, Any]] = {}
    if manifest is not None:
        journeys, found = validate_manifest(manifest, items)
        diagnostics.extend(found)
        if args.transition and args.work_item:
            diagnostics.extend(transition_diagnostics(args.transition, args.work_item, items, journeys, manifest.get("active_staging_slice")))
        if mode == "target":
            if not args.journey or args.journey not in journeys:
                diagnostics.append(Diagnostic("error", args.journey or "retrieval", "target mode requires a registered --journey"))
            else:
                print(json.dumps({"mode": "target", "journey": journeys[args.journey]}, sort_keys=True, separators=(",", ":")))
        elif mode == "work-item":
            selected = [journey for journey in journeys.values() if journey.get("work_item_id") == args.work_item]
            if len(selected) != 1:
                diagnostics.append(Diagnostic("error", args.work_item or "retrieval", f"work-item mode must resolve exactly one journey; found {len(selected)}"))
            else:
                print(json.dumps({"mode": "work-item", "journey": selected[0]}, sort_keys=True, separators=(",", ":")))
        elif mode == "history":
            diagnostics.append(Diagnostic("error", "schema-v1", "history is unavailable because the monolithic manifest has no archived claim projection"))
        elif mode == "audit":
            print(json.dumps({"mode": "audit", "manifest": manifest}, sort_keys=True, separators=(",", ":")))
        if mode == "impact":
            invalid = [path for path in args.changed_path if not safe_relative_path(path)]
            for path in invalid:
                diagnostics.append(Diagnostic("error", path, "changed path must be repository-relative"))
            impacted = impacted_journeys(args.changed_path, journeys)
            print("impacted journeys: " + (", ".join(impacted) if impacted else "none"))
    return emit(diagnostics)


if __name__ == "__main__":
    raise SystemExit(main())
