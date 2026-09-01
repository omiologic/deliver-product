from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_delivery_spine.py"


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
        self.assertIn("impacted journeys: first-journey", result.stdout)
        self.assertNotIn("second-journey,", result.stdout)


if __name__ == "__main__":
    unittest.main()
