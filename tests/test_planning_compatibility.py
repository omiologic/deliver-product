from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "skills" / "delivery-planning" / "scripts" / "validate_plans.py"
SPEC = importlib.util.spec_from_file_location("delivery_planning_validate_plans", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

PROFILE = '''---
schema_version: 3
project_key: catalog-api
canonical_ids_from: "2026-08-24T11:00:00Z"
last_work_item_sequence: 2
profile: minimal
git_governance:
  branch_strategy: deliberately-opaque
version_governance:
  current_version: deliberately-opaque
---

# Consumer-owned governance
'''


def item_text(
    work_id: str = "catalog-api-00002",
    *,
    depends_on: str = "[]",
    target: str = "src/catalog.py",
    created_at: str = "2026-08-24T10:00:00Z",
    result: str = "—",
) -> str:
    return f'''---
work_item_id: "{work_id}"
title: "Build catalog"
depends_on: {depends_on}
target_paths:
  - "{target}"
created_at: "{created_at}"
updated_at: "2026-08-24T10:00:00Z"
---

# Build catalog

## Completion record

- Result: {result}
'''


class PlanningCompatibilityTests(unittest.TestCase):
    def build(self, root: Path, mutation: str) -> None:
        plans = root / "_notes" / "plans"
        for lifecycle in ("backlog", "ready", "active", "archived"):
            (plans / lifecycle).mkdir(parents=True, exist_ok=True)
        (root / "_notes" / "GOVERNANCE.md").write_text(PROFILE, encoding="utf-8")

        lifecycle = "backlog" if mutation == "actionable-backlog" else "ready"
        work_id = {
            "wrong-project": "other-api-00002",
            "high-sequence": "catalog-api-00003",
            "late-legacy": "work-20260824-002",
        }.get(mutation, "catalog-api-00002")
        depends_on = "\n  - \"catalog-api-00001\"" if mutation == "missing-dependency" else "[]"
        target = "../outside" if mutation == "escaping-target" else "src/catalog.py"
        created_at = "2026-08-24T12:00:00Z" if mutation == "late-legacy" else "2026-08-24T10:00:00Z"
        filename = f"{work_id}.build-catalog.md"
        path = plans / lifecycle / filename
        path.write_text(
            item_text(work_id, depends_on=depends_on, target=target, created_at=created_at),
            encoding="utf-8",
        )
        sections = {"Backlog": [], "Ready": [], "Active": [], "Archived": []}
        sections[lifecycle.title()].append(f"- [Build catalog]({lifecycle}/{filename})")
        index = "# Plan\n\n" + "\n\n".join(
            f"## {name}\n\n" + ("\n".join(links) if links else "- None")
            for name, links in sections.items()
        ) + "\n"
        (plans / "PLAN.md").write_text(index, encoding="utf-8")

    def test_frozen_legacy_diagnostics(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "planning_compatibility.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.build(root, scenario["mutation"])
                observed = [item.message for item in VALIDATOR.validate_workspace(root)]
                self.assertEqual(scenario["expected"], observed)

    def test_missing_projection_does_not_affect_skill_package_validation(self) -> None:
        self.assertTrue((ROOT / "skills" / "delivery-planning" / "SKILL.md").is_file())
        with tempfile.TemporaryDirectory() as temp:
            diagnostics = VALIDATOR.validate_workspace(Path(temp))
        self.assertEqual(["missing _notes/plans directory"], [item.message for item in diagnostics])

    def test_opaque_governance_sections_do_not_change_planning_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "GOVERNANCE.md"
            path.write_text(PROFILE, encoding="utf-8")
            profile, diagnostics = VALIDATOR.parse_profile(path)
        self.assertEqual([], diagnostics)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual("catalog-api", profile.project_key)

    def test_next_id_uses_monotonic_high_water_mark(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "GOVERNANCE.md"
            path.write_text(PROFILE, encoding="utf-8")
            profile, diagnostics = VALIDATOR.parse_profile(path)
        self.assertEqual([], diagnostics)
        assert profile is not None
        self.assertEqual("catalog-api-00003", VALIDATOR.next_work_item_id(profile))
        self.assertEqual(
            "catalog-api-00010",
            VALIDATOR.next_work_item_id(profile, highest_visible_sequence=9),
        )
        profile.last_work_item_sequence = 99999
        with self.assertRaisesRegex(ValueError, "schema revision"):
            VALIDATOR.next_work_item_id(profile)

    def test_successful_archive_satisfies_ready_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build(root, "none")
            plans = root / "_notes" / "plans"
            ready = next((plans / "ready").glob("*.md"))
            ready.write_text(
                item_text(depends_on='\n  - "catalog-api-00001"'), encoding="utf-8"
            )
            archived = plans / "archived" / "catalog-api-00001.prepare.md"
            archived.write_text(
                item_text("catalog-api-00001", result="Prepared catalog inputs"),
                encoding="utf-8",
            )
            index = (plans / "PLAN.md").read_text(encoding="utf-8")
            index = index.replace(
                "## Archived\n\n- None",
                "## Archived\n\n- [Prepare](archived/catalog-api-00001.prepare.md)",
            )
            (plans / "PLAN.md").write_text(index, encoding="utf-8")

            diagnostics = VALIDATOR.validate_workspace(root)

        self.assertEqual([], diagnostics)


if __name__ == "__main__":
    unittest.main()
