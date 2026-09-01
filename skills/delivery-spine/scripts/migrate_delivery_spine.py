#!/usr/bin/env python3
"""Preview or write a non-destructive schema-v1 to sharded schema-v2 migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from delivery_spine_projection import DEFAULT_ADAPTER_ROOT, resolve_consumer_path
from validate_delivery_spine import (
    DEFAULT_MANIFEST_PATH,
    Diagnostic,
    load_manifest,
    load_work_items,
    resolve_manifest_path,
    validate_manifest,
)


def claim_identifier(work_item_id: str) -> str:
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", work_item_id):
        return work_item_id
    base = re.sub(r"[^a-z0-9]+", "-", work_item_id.lower()).strip("-") or "claim"
    digest = hashlib.sha256(work_item_id.encode("utf-8")).hexdigest()[:12]
    return f"{base[:40].rstrip('-')}-{digest}"


def claim_record(journey: dict[str, Any], claim_id: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "claim_id": claim_id,
        "journey_id": journey["journey_id"],
        "work_item_id": journey["work_item_id"],
        "target_level": journey["target_level"],
        "current_level": journey["current_level"],
        "boundaries": journey["boundaries"],
        "evidence": journey["evidence"],
        "blockers": journey["blockers"],
    }


def migration_records(
    manifest: dict[str, Any],
    items: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    registrations: list[dict[str, Any]] = []
    claim_entries: list[dict[str, Any]] = []
    records: dict[str, dict[str, Any]] = {}

    for journey in sorted(manifest["journeys"], key=lambda value: value["journey_id"]):
        journey_id = journey["journey_id"]
        work_item_id = journey["work_item_id"]
        owner = items.get(work_item_id)
        if owner is None:
            diagnostics.append(Diagnostic("error", journey_id, f"work_item_id does not resolve: {work_item_id}"))
            continue
        registrations.append({
            "journey_id": journey_id,
            "outcome": journey["outcome"],
            "affected_paths": journey["affected_paths"],
            "suites": [],
        })
        claim_id = claim_identifier(work_item_id)
        claim = claim_record(journey, claim_id)
        if owner.lifecycle == "archived":
            records[f"archive/{journey_id}/{claim_id}.json"] = claim
            records[f"baselines/{journey_id}.json"] = {
                "schema_version": 2,
                "journey_id": journey_id,
                "claim_id": claim_id,
                "current_level": journey["current_level"],
                "boundaries": journey["boundaries"],
                "evidence": journey["evidence"],
            }
        else:
            records[f"claims/{journey_id}.json"] = claim
            claim_entries.append({
                "journey_id": journey_id,
                "work_item_id": work_item_id,
                "claim_path": f"claims/{journey_id}.json",
            })

    active_slice = manifest.get("active_staging_slice")
    if active_slice is not None and not any(entry["journey_id"] == active_slice for entry in claim_entries):
        diagnostics.append(Diagnostic("error", "migration", "active_staging_slice does not resolve to an open claim"))
    if registrations:
        diagnostics.append(Diagnostic(
            "warning",
            "migration",
            f"schema-v1 has no suite references; migrated suites is empty for {len(registrations)} journey(s)",
        ))
    records["registry.json"] = {"schema_version": 2, "journeys": registrations}
    records["claims/index.json"] = {
        "schema_version": 2,
        "active_staging_slice": active_slice,
        "claims": claim_entries,
    }
    return dict(sorted(records.items())), diagnostics


def write_records(destination: Path, records: dict[str, dict[str, Any]]) -> None:
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.migration-", dir=destination.parent))
    try:
        for relative, record in records.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--manifest-path", default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--adapter-root", default=DEFAULT_ADAPTER_ROOT)
    parser.add_argument("--write", action="store_true", help="write the new projection; preview is the default")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    items, diagnostics = load_work_items(root)
    manifest_path, found = resolve_manifest_path(root, args.manifest_path)
    diagnostics.extend(found)
    manifest = None
    if manifest_path is not None:
        manifest, found = load_manifest(manifest_path)
        diagnostics.extend(found)
    if manifest is not None:
        _, found = validate_manifest(manifest, items)
        diagnostics.extend(found)

    destination, found = resolve_consumer_path(root, args.adapter_root, "adapter root")
    diagnostics.extend(found)
    if destination is not None and destination.exists():
        diagnostics.append(Diagnostic("error", str(destination), "migration destination already exists"))

    records: dict[str, dict[str, Any]] = {}
    if manifest is not None and not any(value.severity == "error" for value in diagnostics):
        records, found = migration_records(manifest, items)
        diagnostics.extend(found)

    ordered = sorted(diagnostics, key=lambda value: (value.severity, value.subject, value.message))
    for diagnostic in ordered[:100]:
        print(f"{diagnostic.severity}: {diagnostic.subject}: {diagnostic.message}")
    if len(ordered) > 100:
        print(f"diagnostics omitted: {len(ordered) - 100}")
    errors = sum(value.severity == "error" for value in diagnostics)
    if errors:
        print(f"delivery-spine migration: {errors} error(s); no files written")
        return 1

    record_counts = {
        "registry": sum(path == "registry.json" for path in records),
        "claim_index": sum(path == "claims/index.json" for path in records),
        "current_claims": sum(path.startswith("claims/") and path != "claims/index.json" for path in records),
        "baselines": sum(path.startswith("baselines/") for path in records),
        "archived_claims": sum(path.startswith("archive/") for path in records),
    }
    summary = {
        "mode": "write" if args.write else "preview",
        "destination": str(destination),
        "record_count": len(records),
        "record_counts": record_counts,
        "source_preserved": True,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    if args.write and destination is not None:
        write_records(destination, records)
        print(f"delivery-spine migration: wrote {len(records)} record(s)")
    else:
        print(f"delivery-spine migration preview: {len(records)} record(s); no files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
