from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_delivery_spine.py"
MIGRATION_SCRIPT = Path(__file__).parents[1] / "scripts" / "migrate_delivery_spine.py"


def work_item(work_item_id: str, journey_id: str, target: str, *, complete: bool = False, preflight: bool = True, integration_consumer: str = "self") -> str:
    check = "x" if preflight else " "
    result = "Completed with retained evidence." if complete else "Active."
    evidence = "staging journey receipt." if complete else "—"
    return f'''---
work_item_id: "{work_item_id}"
title: "Test delivery"
depends_on: []
target_paths:
  - "services/test"
created_at: "2026-08-27T00:00:00Z"
updated_at: "2026-08-27T00:00:00Z"
---

# Test delivery

## Outcome

Deliver one test outcome.

## Context

Test fixture.

## Delivery spine

- Journey ID: {journey_id}
- Target evidence: {target}
- Integration consumer: {integration_consumer}

## Integration preflight

- [{check}] Required boundaries are identified.
- [{check}] Test authority is available.
- [{check}] Environment inputs are resolved.
- [{check}] Real journey route is defined.

## Scope

### In scope

- Test.

### Out of scope

- Nothing else.

## Implementation checklist

- [x] Implement.

## Acceptance criteria

- [x] Journey works.

## Verification

- [x] Verify journey.

## Completion record

- Result: {result}
- Evidence: {evidence}
- Follow-ups: None.
'''


def journey(journey_id: str, work_item_id: str, target: str = "staging_verified", current: str = "source_complete", evidence_class: str = "component") -> dict:
    return {
        "journey_id": journey_id,
        "outcome": "A user completes the test journey.",
        "work_item_id": work_item_id,
        "target_level": target,
        "current_level": current,
        "boundaries": [{"name": "browser", "owner": "interfaces/test", "target": "test", "state": "verified"}],
        "evidence": [{"class": evidence_class, "reference": "tests/evidence", "observed_at": "2026-08-27T00:00:00Z"}],
        "blockers": [],
        "affected_paths": ["interfaces/test", "services/test"]
    }


class DeliverySpineValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for lifecycle in ("backlog", "ready", "active", "archived"):
            (self.root / "_notes" / "plans" / lifecycle).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_item(self, lifecycle: str, identity: str, journey_id: str, target: str, **kwargs: object) -> None:
        path = self.root / "_notes" / "plans" / lifecycle / f"{identity}.test.md"
        path.write_text(work_item(identity, journey_id, target, **kwargs), encoding="utf-8")

    def write_manifest(self, active: str | None, journeys: list[dict], path: str = "_notes/delivery-spine.json") -> None:
        manifest = self.root / path
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"schema_version": 1, "active_staging_slice": active, "journeys": journeys}),
            encoding="utf-8",
        )

    def snapshot(self) -> list[tuple[str, bytes]]:
        return sorted(
            (str(path.relative_to(self.root)), path.read_bytes())
            for path in self.root.rglob("*")
            if path.is_file()
        )

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root), *arguments],
            check=False,
            text=True,
            capture_output=True,
        )

    def run_migration(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MIGRATION_SCRIPT), str(self.root), *arguments],
            check=False,
            text=True,
            capture_output=True,
        )

    def write_sharded(
        self,
        active: str | None,
        current: list[dict],
        *,
        registered: list[dict] | None = None,
        archived: list[dict] | None = None,
    ) -> None:
        adapter = self.root / "_notes" / "delivery-spine"
        all_journeys = registered if registered is not None else current
        registry = {
            "schema_version": 2,
            "journeys": [
                {
                    "journey_id": value["journey_id"],
                    "outcome": value["outcome"],
                    "affected_paths": value["affected_paths"],
                    "suites": [f"tests/{value['journey_id']}.test"],
                }
                for value in all_journeys
            ],
        }
        index = {
            "schema_version": 2,
            "active_staging_slice": active,
            "claims": [
                {
                    "journey_id": value["journey_id"],
                    "work_item_id": value["work_item_id"],
                    "claim_path": f"claims/{value['journey_id']}.json",
                }
                for value in current
            ],
        }
        (adapter / "claims").mkdir(parents=True, exist_ok=True)
        (adapter / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        (adapter / "claims" / "index.json").write_text(json.dumps(index), encoding="utf-8")
        for value in current:
            claim = {
                "schema_version": 2,
                "claim_id": value["work_item_id"],
                **{key: value[key] for key in ("journey_id", "work_item_id", "target_level", "current_level", "boundaries", "evidence", "blockers")},
            }
            (adapter / "claims" / f"{value['journey_id']}.json").write_text(json.dumps(claim), encoding="utf-8")
        for value in archived or []:
            claim = {
                "schema_version": 2,
                "claim_id": value["work_item_id"],
                **{key: value[key] for key in ("journey_id", "work_item_id", "target_level", "current_level", "boundaries", "evidence", "blockers")},
            }
            path = adapter / "archive" / value["journey_id"] / f"{value['work_item_id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(claim), encoding="utf-8")
            baseline = {
                "schema_version": 2,
                "journey_id": value["journey_id"],
                "claim_id": value["work_item_id"],
                "current_level": value["current_level"],
                "boundaries": value["boundaries"],
                "evidence": value["evidence"],
            }
            baseline_path = adapter / "baselines" / f"{value['journey_id']}.json"
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    def test_default_manifest_path_remains_supported(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001")])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_custom_nested_manifest_path_is_consumer_relative(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001")], "operations/journeys/spine.json")
        result = self.run_cli("--manifest-path", "operations/journeys/spine.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_manifest_path_rejects_absolute_traversal_and_backslashes(self) -> None:
        for configured_path in ("/tmp/delivery-spine.json", "../delivery-spine.json", "operations\\delivery-spine.json"):
            with self.subTest(configured_path=configured_path):
                result = self.run_cli("--manifest-path", configured_path)
                self.assertEqual(result.returncode, 1)
                self.assertIn("manifest path must be a relative POSIX path", result.stdout)

    def test_manifest_path_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "operations").symlink_to(outside, target_is_directory=True)
            result = self.run_cli("--manifest-path", "operations/delivery-spine.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest path escapes the consumer root through a symlink", result.stdout)

    def test_missing_configured_manifest_reports_resolved_consumer_path(self) -> None:
        result = self.run_cli("--manifest-path", "operations/missing.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(self.root / "operations" / "missing.json"), result.stdout)
        self.assertIn("cannot read manifest", result.stdout)

    def test_integrated_level_rejects_component_only_evidence(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001", current="integrated")])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("integrated requires integrated_local", result.stdout)

    def test_start_rejects_unchecked_preflight(self) -> None:
        self.write_item("ready", "test-00001", "test-journey", "integrated", preflight=False)
        self.write_manifest(None, [journey("test-journey", "test-00001", target="integrated")])
        result = self.run_cli("--transition", "start", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 1)
        self.assertIn("preflight has unchecked", result.stdout.lower())

    def test_start_rejects_required_placeholder_configuration(self) -> None:
        self.write_item("ready", "test-00001", "test-journey", "integrated")
        target = self.root / "services" / "test"
        target.mkdir(parents=True)
        (target / "staging.json").write_text('{"endpoint":"REPLACE_WITH_ENDPOINT"}', encoding="utf-8")
        self.write_manifest(None, [journey("test-journey", "test-00001", target="integrated")])
        result = self.run_cli("--transition", "start", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 1)
        self.assertIn("required configuration still has placeholders", result.stdout)

    def test_start_ignores_inert_example_configuration(self) -> None:
        self.write_item("ready", "test-00001", "test-journey", "integrated")
        target = self.root / "services" / "test"
        target.mkdir(parents=True)
        (target / "staging.example.json").write_text('{"endpoint":"REPLACE_WITH_ENDPOINT"}', encoding="utf-8")
        (target / "staging.json").write_text('{"endpoint":"https://staging.example.test"}', encoding="utf-8")
        self.write_manifest(None, [journey("test-journey", "test-00001", target="integrated")])
        before = self.snapshot()
        result = self.run_cli("--transition", "start", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue((self.root / "_notes" / "plans" / "ready" / "test-00001.test.md").is_file())

    def test_start_rejects_second_staging_slice(self) -> None:
        self.write_item("active", "test-00001", "first-journey", "staging_verified")
        self.write_item("ready", "test-00002", "second-journey", "staging_verified")
        self.write_manifest("first-journey", [journey("first-journey", "test-00001"), journey("second-journey", "test-00002")])
        result = self.run_cli("--transition", "start", "--work-item", "test-00002")
        self.assertEqual(result.returncode, 1)
        self.assertIn("staging slot is owned by first-journey", result.stdout)

    def test_archive_requires_checked_acceptance_and_verification(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified", complete=True)
        path = next((self.root / "_notes" / "plans" / "active").glob("*.md"))
        path.write_text(path.read_text(encoding="utf-8").replace("- [x] Journey works.", "- [ ] Journey works."), encoding="utf-8")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001", current="staging_verified", evidence_class="staging_e2e")])
        result = self.run_cli("--transition", "archive", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Acceptance criteria contains unchecked", result.stdout)

    def test_archive_accepts_staging_evidence_and_completed_record(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified", complete=True)
        self.write_manifest("test-journey", [journey("test-journey", "test-00001", current="staging_verified", evidence_class="staging_e2e")])
        before = self.snapshot()
        result = self.run_cli("--transition", "archive", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue((self.root / "_notes" / "plans" / "active" / "test-00001.test.md").is_file())

    def test_archive_rejects_placeholder_completion_evidence(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001", current="staging_verified", evidence_class="staging_e2e")])
        result = self.run_cli("--transition", "archive", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Completion result is missing or placeholder", result.stdout)
        self.assertIn("Completion evidence is missing or placeholder", result.stdout)

    def test_source_only_work_requires_exact_integration_consumer(self) -> None:
        self.write_item("active", "test-00001", "none", "source_complete", complete=True, integration_consumer="none")
        self.write_manifest(None, [])
        result = self.run_cli("--transition", "archive", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 1)
        self.assertIn("must name an exact integration consumer", result.stdout)

    def test_source_only_work_accepts_exact_integration_consumer(self) -> None:
        self.write_item("active", "test-00001", "none", "source_complete", complete=True, integration_consumer="test-00002")
        self.write_manifest(None, [])
        result = self.run_cli("--transition", "archive", "--work-item", "test-00001")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_paths_select_only_impacted_journeys(self) -> None:
        self.write_item("active", "test-00001", "first-journey", "staging_verified")
        self.write_item("ready", "test-00002", "second-journey", "integrated")
        second = journey("second-journey", "test-00002", target="integrated")
        second["affected_paths"] = ["domains/second"]
        self.write_manifest("first-journey", [journey("first-journey", "test-00001"), second])
        result = self.run_cli("--changed-path", "interfaces/test/component.ts")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"impacted_journey_ids":["first-journey"]', result.stdout)
        self.assertNotIn('"impacted_journey_ids":["second-journey"]', result.stdout)

    def test_sharded_projection_validates_and_preserves_gate_authority(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified", complete=True)
        record = journey("test-journey", "test-00001", current="staging_verified", evidence_class="staging_e2e")
        self.write_sharded("test-journey", [record])
        before = self.snapshot()
        result = self.run_cli("--adapter", "sharded")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        gate = self.run_cli("--adapter", "sharded", "--transition", "archive", "--work-item", "test-00001")
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertTrue((self.root / "_notes" / "plans" / "active" / "test-00001.test.md").is_file())

    def test_target_and_work_item_retrieval_return_only_exact_current_records(self) -> None:
        self.write_item("active", "test-00001", "first-journey", "staging_verified")
        self.write_item("ready", "test-00002", "second-journey", "integrated")
        first = journey("first-journey", "test-00001")
        second = journey("second-journey", "test-00002", target="integrated")
        self.write_sharded("first-journey", [first, second])
        target = self.run_cli("--adapter", "sharded", "--mode", "target", "--journey", "second-journey")
        self.assertEqual(target.returncode, 0, target.stdout + target.stderr)
        self.assertIn('"journey_id":"second-journey"', target.stdout)
        self.assertNotIn('"journey_id":"first-journey"', target.stdout)
        selected = self.run_cli("--adapter", "sharded", "--mode", "work-item", "--work-item", "test-00002")
        self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
        self.assertIn('"work_item_id":"test-00002"', selected.stdout)
        self.assertNotIn('"work_item_id":"test-00001"', selected.stdout)

    def test_impact_reads_registry_without_claim_projection(self) -> None:
        first = journey("first-journey", "test-00001")
        second = journey("second-journey", "test-00002")
        second["affected_paths"] = ["domains/second"]
        self.write_sharded(None, [], registered=[first, second])
        (self.root / "_notes" / "delivery-spine" / "claims" / "index.json").unlink()
        (self.root / "_notes" / "plans" / "active" / "unrelated.md").write_text("not a WorkItem", encoding="utf-8")
        result = self.run_cli("--adapter", "sharded", "--mode", "impact", "--changed-path", "interfaces/test/view.ts")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"journey_id":"first-journey"', result.stdout)
        self.assertIn('"suites":["tests/first-journey.test"]', result.stdout)
        self.assertNotIn("second-journey", result.stdout)

    def test_completed_claim_leaves_current_set_but_remains_registered_and_exactly_retrievable(self) -> None:
        self.write_item("archived", "test-00001", "test-journey", "staging_verified", complete=True)
        completed = journey("test-journey", "test-00001", current="staging_verified", evidence_class="staging_e2e")
        self.write_sharded(None, [], registered=[completed], archived=[completed])
        target = self.run_cli("--adapter", "sharded", "--mode", "target", "--journey", "test-journey")
        self.assertEqual(target.returncode, 0, target.stdout + target.stderr)
        self.assertIn('"claim":null', target.stdout)
        self.assertIn('"baseline":{', target.stdout)
        history = self.run_cli("--adapter", "sharded", "--mode", "history", "--journey", "test-journey", "--claim", "test-00001")
        self.assertEqual(history.returncode, 0, history.stdout + history.stderr)
        self.assertIn('"claim_id":"test-00001"', history.stdout)

    def test_history_requires_exact_reference_and_audit_is_explicit(self) -> None:
        completed = journey("test-journey", "test-00001")
        self.write_sharded(None, [], registered=[completed], archived=[completed])
        history = self.run_cli("--adapter", "sharded", "--mode", "history", "--journey", "test-journey")
        self.assertEqual(history.returncode, 1)
        self.assertIn("history mode requires --claim, --dependency, or --evidence-reference", history.stdout)
        dependency = self.run_cli(
            "--adapter", "sharded", "--mode", "history", "--journey", "test-journey", "--dependency", "test-00001"
        )
        self.assertEqual(dependency.returncode, 0, dependency.stdout + dependency.stderr)
        self.assertIn('"claim_id":"test-00001"', dependency.stdout)
        audit = self.run_cli("--adapter", "sharded", "--mode", "audit")
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
        self.assertIn('"archived_claims"', audit.stdout)

    def test_target_context_stays_bounded_as_completed_history_grows(self) -> None:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "large-history.json").read_text(encoding="utf-8")
        )
        self.write_item("ready", "test-00001", "test-journey", "integrated")
        current = journey("test-journey", "test-00001", target="integrated")
        registrations = [current]
        archived: list[dict] = []
        for index in range(fixture["completed_claims"]):
            journey_id = f"history-{index:05d}"
            work_item_id = f"done-{index:05d}"
            record = journey(journey_id, work_item_id)
            registrations.append(record)
            archived.append(record)
        self.write_sharded(None, [current], registered=registrations, archived=archived)
        result = self.run_cli("--adapter", "sharded", "--mode", "target", "--journey", "test-journey")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(len(result.stdout), fixture["target_output_max_bytes"])
        self.assertNotIn("history-00249", result.stdout)

    def test_validation_detects_archived_work_item_in_current_claim_set(self) -> None:
        self.write_item("archived", "test-00001", "test-journey", "staging_verified", complete=True)
        record = journey("test-journey", "test-00001")
        self.write_sharded(None, [record])
        result = self.run_cli("--adapter", "sharded")
        self.assertEqual(result.returncode, 1)
        self.assertIn("completed WorkItem remains in the current claim working set", result.stdout)

    def test_migration_preview_is_deterministic_and_non_mutating(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001")])
        before = self.snapshot()
        first = self.run_migration()
        second = self.run_migration()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertIn('"mode":"preview"', first.stdout)
        self.assertNotIn('"records":', first.stdout)

    def test_migration_preview_stays_compact_as_completed_history_grows(self) -> None:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "large-history.json").read_text(encoding="utf-8")
        )
        completed: list[dict] = []
        for index in range(fixture["completed_claims"]):
            journey_id = f"history-{index:05d}"
            work_item_id = f"done-{index:05d}"
            self.write_item("archived", work_item_id, journey_id, "staging_verified", complete=True)
            completed.append(journey(journey_id, work_item_id, current="staging_verified", evidence_class="staging_e2e"))
        self.write_manifest(None, completed)
        result = self.run_migration()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(len(result.stdout), fixture["target_output_max_bytes"])
        self.assertIn(f'"record_count":{2 + 2 * fixture["completed_claims"]}', result.stdout)
        self.assertIn(f"migrated suites is empty for {fixture['completed_claims']} journey(s)", result.stdout)

    def test_migration_writes_without_rewriting_source_and_archived_claims_leave_current_set(self) -> None:
        self.write_item("archived", "test-00001", "test-journey", "staging_verified", complete=True)
        self.write_manifest(None, [journey("test-journey", "test-00001", current="staging_verified", evidence_class="staging_e2e")])
        source = self.root / "_notes" / "delivery-spine.json"
        source_bytes = source.read_bytes()
        result = self.run_migration("--write")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(source_bytes, source.read_bytes())
        index = json.loads((self.root / "_notes" / "delivery-spine" / "claims" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([], index["claims"])
        self.assertTrue((self.root / "_notes" / "delivery-spine" / "archive" / "test-journey" / "test-00001.json").is_file())
        self.assertTrue((self.root / "_notes" / "delivery-spine" / "baselines" / "test-journey.json").is_file())
        validation = self.run_cli("--adapter", "sharded")
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)

    def test_migration_refuses_existing_destination(self) -> None:
        self.write_item("active", "test-00001", "test-journey", "staging_verified")
        self.write_manifest("test-journey", [journey("test-journey", "test-00001")])
        destination = self.root / "_notes" / "delivery-spine"
        destination.mkdir(parents=True)
        marker = destination / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        result = self.run_migration("--write")
        self.assertEqual(result.returncode, 1)
        self.assertEqual("keep", marker.read_text(encoding="utf-8"))
        self.assertIn("migration destination already exists", result.stdout)

    def test_sharded_adapter_and_migration_reject_boundary_escape(self) -> None:
        validation = self.run_cli("--adapter", "sharded", "--adapter-root", "../outside")
        self.assertEqual(validation.returncode, 1)
        self.assertIn("adapter root must be a relative POSIX path", validation.stdout)
        migration = self.run_migration("--adapter-root", "../outside")
        self.assertEqual(migration.returncode, 1)
        self.assertIn("adapter root must be a relative POSIX path", migration.stdout)


if __name__ == "__main__":
    unittest.main()
