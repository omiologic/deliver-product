#!/usr/bin/env python3
"""Read and validate the Delivery Spine schema-v2 sharded projection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


LEVELS = ("source_complete", "integrated", "staging_verified")
LEVEL_RANK = {name: index for index, name in enumerate(LEVELS)}
EVIDENCE_CLASSES = ("component", "contract", "integrated_local", "staging_e2e")
BOUNDARY_STATES = ("missing", "source_only", "configured", "deployed", "verified")
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DEFAULT_ADAPTER_ROOT = "_notes/delivery-spine"


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    subject: str
    message: str


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


def resolve_consumer_path(root: Path, value: str, label: str) -> tuple[Path | None, list[Diagnostic]]:
    if not safe_relative_path(value):
        return None, [Diagnostic("error", value, f"{label} must be a relative POSIX path without traversal or backslashes")]
    path = (root / PurePosixPath(value)).resolve(strict=False)
    if not path.is_relative_to(root):
        return None, [Diagnostic("error", value, f"{label} escapes the consumer root through a symlink")]
    return path, []


def read_json(path: Path) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [Diagnostic("error", str(path), f"cannot read projection: {exc}")]
    except json.JSONDecodeError as exc:
        return None, [Diagnostic("error", str(path), f"invalid JSON: {exc}")]
    if not isinstance(value, dict):
        return None, [Diagnostic("error", str(path), "projection record must be an object")]
    return value, []


def _exact_fields(record: dict[str, Any], required: set[str], subject: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    missing = sorted(required - record.keys())
    extra = sorted(record.keys() - required)
    if missing:
        diagnostics.append(Diagnostic("error", subject, f"missing fields: {', '.join(missing)}"))
    if extra:
        diagnostics.append(Diagnostic("error", subject, f"unknown fields: {', '.join(extra)}"))
    return diagnostics


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.fullmatch(value))


def _validate_boundaries(boundaries: Any, subject: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(boundaries, list) or not boundaries:
        return [Diagnostic("error", subject, "boundaries must be a non-empty array")]
    names: set[str] = set()
    for boundary in boundaries:
        if not isinstance(boundary, dict) or set(boundary) != {"name", "owner", "target", "state"}:
            diagnostics.append(Diagnostic("error", subject, "each boundary requires only name, owner, target, and state"))
            continue
        name = boundary.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            diagnostics.append(Diagnostic("error", subject, "boundary names must be non-empty and unique"))
        else:
            names.add(name)
        for field in ("owner", "target"):
            if not isinstance(boundary.get(field), str) or not boundary[field].strip():
                diagnostics.append(Diagnostic("error", subject, f"boundary {field} must be non-empty"))
        if boundary.get("state") not in BOUNDARY_STATES:
            diagnostics.append(Diagnostic("error", subject, "boundary state is invalid"))
    return diagnostics


def _validate_evidence(evidence: Any, subject: str) -> tuple[set[str], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    classes: set[str] = set()
    if not isinstance(evidence, list):
        return classes, [Diagnostic("error", subject, "evidence must be an array")]
    for record in evidence:
        if not isinstance(record, dict) or set(record) != {"class", "reference", "observed_at"}:
            diagnostics.append(Diagnostic("error", subject, "each evidence record requires only class, reference, and observed_at"))
            continue
        evidence_class = record.get("class")
        if evidence_class not in EVIDENCE_CLASSES:
            diagnostics.append(Diagnostic("error", subject, "evidence class is invalid"))
        else:
            classes.add(evidence_class)
        if not isinstance(record.get("reference"), str) or not record["reference"].strip():
            diagnostics.append(Diagnostic("error", subject, "evidence reference must be non-empty"))
        if not valid_time(record.get("observed_at")):
            diagnostics.append(Diagnostic("error", subject, "evidence observed_at must be RFC 3339"))
    return classes, diagnostics


def validate_registry(data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
    diagnostics = _exact_fields(data, {"schema_version", "journeys"}, "registry")
    if data.get("schema_version") != 2:
        diagnostics.append(Diagnostic("error", "registry", "schema_version must be 2"))
    raw_journeys = data.get("journeys")
    if not isinstance(raw_journeys, list):
        return {}, diagnostics + [Diagnostic("error", "registry", "journeys must be an array")]
    journeys: dict[str, dict[str, Any]] = {}
    required = {"journey_id", "outcome", "affected_paths", "suites"}
    for index, raw in enumerate(raw_journeys):
        subject = f"registry.journeys[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(Diagnostic("error", subject, "journey registration must be an object"))
            continue
        diagnostics.extend(_exact_fields(raw, required, subject))
        journey_id = raw.get("journey_id")
        if not _valid_id(journey_id):
            diagnostics.append(Diagnostic("error", subject, "journey_id is invalid"))
            continue
        if journey_id in journeys:
            diagnostics.append(Diagnostic("error", journey_id, "duplicate journey_id"))
        journeys[journey_id] = raw
        if not isinstance(raw.get("outcome"), str) or not raw["outcome"].strip():
            diagnostics.append(Diagnostic("error", journey_id, "outcome must be non-empty"))
        paths = raw.get("affected_paths")
        if not isinstance(paths, list) or not paths:
            diagnostics.append(Diagnostic("error", journey_id, "affected_paths must be a non-empty array"))
        elif any(not safe_relative_path(path) for path in paths):
            diagnostics.append(Diagnostic("error", journey_id, "affected_paths must contain relative POSIX paths"))
        suites = raw.get("suites")
        if not isinstance(suites, list) or any(not isinstance(suite, str) or not suite.strip() for suite in suites):
            diagnostics.append(Diagnostic("error", journey_id, "suites must be an array of non-empty references"))
    return journeys, diagnostics


def validate_claim_index(data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[Diagnostic]]:
    diagnostics = _exact_fields(data, {"schema_version", "active_staging_slice", "claims"}, "claims/index")
    if data.get("schema_version") != 2:
        diagnostics.append(Diagnostic("error", "claims/index", "schema_version must be 2"))
    active = data.get("active_staging_slice")
    if active is not None and not _valid_id(active):
        diagnostics.append(Diagnostic("error", "claims/index", "active_staging_slice must be a journey ID or null"))
    raw_claims = data.get("claims")
    if not isinstance(raw_claims, list):
        return {}, {}, diagnostics + [Diagnostic("error", "claims/index", "claims must be an array")]
    by_journey: dict[str, dict[str, Any]] = {}
    by_work_item: dict[str, str] = {}
    required = {"journey_id", "work_item_id", "claim_path"}
    for index, raw in enumerate(raw_claims):
        subject = f"claims[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(Diagnostic("error", subject, "claim index entry must be an object"))
            continue
        diagnostics.extend(_exact_fields(raw, required, subject))
        journey_id = raw.get("journey_id")
        work_item_id = raw.get("work_item_id")
        if not _valid_id(journey_id):
            diagnostics.append(Diagnostic("error", subject, "journey_id is invalid"))
            continue
        if not isinstance(work_item_id, str) or not work_item_id.strip():
            diagnostics.append(Diagnostic("error", journey_id, "work_item_id must be non-empty"))
        if journey_id in by_journey:
            diagnostics.append(Diagnostic("error", journey_id, "duplicate current journey claim"))
        by_journey[journey_id] = raw
        if isinstance(work_item_id, str) and work_item_id in by_work_item:
            diagnostics.append(Diagnostic("error", work_item_id, "duplicate current work-item claim"))
        elif isinstance(work_item_id, str):
            by_work_item[work_item_id] = journey_id
        expected = f"claims/{journey_id}.json"
        if raw.get("claim_path") != expected:
            diagnostics.append(Diagnostic("error", journey_id, f"claim_path must be {expected}"))
    if active is not None and active not in by_journey:
        diagnostics.append(Diagnostic("error", "claims/index", "active_staging_slice does not resolve to a current claim"))
    return by_journey, by_work_item, diagnostics


def validate_claim(data: dict[str, Any], subject: str = "claim") -> list[Diagnostic]:
    required = {
        "schema_version", "claim_id", "journey_id", "work_item_id", "target_level",
        "current_level", "boundaries", "evidence", "blockers"
    }
    diagnostics = _exact_fields(data, required, subject)
    if data.get("schema_version") != 2:
        diagnostics.append(Diagnostic("error", subject, "schema_version must be 2"))
    for field in ("claim_id", "journey_id"):
        if not _valid_id(data.get(field)):
            diagnostics.append(Diagnostic("error", subject, f"{field} is invalid"))
    if not isinstance(data.get("work_item_id"), str) or not data["work_item_id"].strip():
        diagnostics.append(Diagnostic("error", subject, "work_item_id must be non-empty"))
    target = data.get("target_level")
    current = data.get("current_level")
    if target not in LEVELS:
        diagnostics.append(Diagnostic("error", subject, "target_level is invalid"))
    if current not in LEVELS:
        diagnostics.append(Diagnostic("error", subject, "current_level is invalid"))
    if target in LEVELS and current in LEVELS and LEVEL_RANK[current] > LEVEL_RANK[target]:
        diagnostics.append(Diagnostic("error", subject, "current_level exceeds target_level"))
    diagnostics.extend(_validate_boundaries(data.get("boundaries"), subject))
    classes, evidence_diagnostics = _validate_evidence(data.get("evidence"), subject)
    diagnostics.extend(evidence_diagnostics)
    if current == "integrated" and not ({"integrated_local", "staging_e2e"} & classes):
        diagnostics.append(Diagnostic("error", subject, "integrated requires integrated_local or staging_e2e evidence"))
    if current == "staging_verified" and "staging_e2e" not in classes:
        diagnostics.append(Diagnostic("error", subject, "staging_verified requires staging_e2e evidence"))
    blockers = data.get("blockers")
    if not isinstance(blockers, list) or any(not isinstance(value, str) or not value.strip() for value in blockers):
        diagnostics.append(Diagnostic("error", subject, "blockers must be an array of non-empty strings"))
    return diagnostics


def validate_baseline(data: dict[str, Any], subject: str = "baseline") -> list[Diagnostic]:
    required = {"schema_version", "journey_id", "claim_id", "current_level", "boundaries", "evidence"}
    diagnostics = _exact_fields(data, required, subject)
    if data.get("schema_version") != 2:
        diagnostics.append(Diagnostic("error", subject, "schema_version must be 2"))
    for field in ("journey_id", "claim_id"):
        if not _valid_id(data.get(field)):
            diagnostics.append(Diagnostic("error", subject, f"{field} is invalid"))
    current = data.get("current_level")
    if current not in LEVELS:
        diagnostics.append(Diagnostic("error", subject, "current_level is invalid"))
    diagnostics.extend(_validate_boundaries(data.get("boundaries"), subject))
    classes, evidence_diagnostics = _validate_evidence(data.get("evidence"), subject)
    diagnostics.extend(evidence_diagnostics)
    if current == "integrated" and not ({"integrated_local", "staging_e2e"} & classes):
        diagnostics.append(Diagnostic("error", subject, "integrated requires integrated_local or staging_e2e evidence"))
    if current == "staging_verified" and "staging_e2e" not in classes:
        diagnostics.append(Diagnostic("error", subject, "staging_verified requires staging_e2e evidence"))
    return diagnostics


class ShardedAdapter:
    """Load only the records required by one retrieval mode."""

    def __init__(self, consumer_root: Path, adapter_path: str) -> None:
        self.consumer_root = consumer_root.resolve()
        resolved, diagnostics = resolve_consumer_path(self.consumer_root, adapter_path, "adapter root")
        self.root = resolved
        self.path_diagnostics = diagnostics

    def read(self, relative: str) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
        if self.root is None:
            return None, list(self.path_diagnostics)
        if not safe_relative_path(relative):
            return None, [Diagnostic("error", relative, "projection record path is invalid")]
        path = (self.root / PurePosixPath(relative)).resolve(strict=False)
        if not path.is_relative_to(self.root):
            return None, [Diagnostic("error", relative, "projection record escapes the adapter root")]
        return read_json(path)

    def registry(self) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
        data, diagnostics = self.read("registry.json")
        if data is None:
            return {}, diagnostics
        journeys, found = validate_registry(data)
        return journeys, diagnostics + found

    def claim_index(self) -> tuple[dict[str, dict[str, Any]], dict[str, str], str | None, list[Diagnostic]]:
        data, diagnostics = self.read("claims/index.json")
        if data is None:
            return {}, {}, None, diagnostics
        by_journey, by_work_item, found = validate_claim_index(data)
        active = data.get("active_staging_slice") if isinstance(data.get("active_staging_slice"), str) else None
        return by_journey, by_work_item, active, diagnostics + found

    def claim(self, journey_id: str) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
        if not _valid_id(journey_id):
            return None, [Diagnostic("error", journey_id, "journey ID is invalid")]
        data, diagnostics = self.read(f"claims/{journey_id}.json")
        return data, diagnostics + (validate_claim(data, journey_id) if data is not None else [])

    def baseline(self, journey_id: str, *, required: bool = False) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
        if not _valid_id(journey_id):
            return None, [Diagnostic("error", journey_id, "journey ID is invalid")]
        if self.root is None:
            return None, list(self.path_diagnostics)
        path = self.root / "baselines" / f"{journey_id}.json"
        if not path.exists() and not required:
            return None, []
        data, diagnostics = self.read(f"baselines/{journey_id}.json")
        return data, diagnostics + (validate_baseline(data, journey_id) if data is not None else [])

    def archived_claim(self, journey_id: str, claim_id: str) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
        if not _valid_id(journey_id) or not _valid_id(claim_id):
            return None, [Diagnostic("error", f"{journey_id}/{claim_id}", "journey and claim IDs must be safe identifiers")]
        data, diagnostics = self.read(f"archive/{journey_id}/{claim_id}.json")
        return data, diagnostics + (validate_claim(data, f"{journey_id}/{claim_id}") if data is not None else [])

    def archive_paths(self) -> list[Path]:
        if self.root is None:
            return []
        archive = self.root / "archive"
        return sorted(path for path in archive.glob("*/*.json") if path.resolve(strict=False).is_relative_to(self.root))


def impacted_registrations(paths: Iterable[str], journeys: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [PurePosixPath(path) for path in paths if safe_relative_path(path)]
    impacted: list[dict[str, Any]] = []
    for journey_id, journey in journeys.items():
        prefixes = [PurePosixPath(path) for path in journey.get("affected_paths", []) if safe_relative_path(path)]
        if any(changed == prefix or prefix in changed.parents or changed in prefix.parents for changed in normalized for prefix in prefixes):
            impacted.append({"journey_id": journey_id, "suites": journey.get("suites", [])})
    return sorted(impacted, key=lambda value: value["journey_id"])

