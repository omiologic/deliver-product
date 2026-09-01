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
RETRIEVER_PATH = ROOT / "skills" / "delivery-planning" / "scripts" / "retrieve_plans.py"
RETRIEVER_SPEC = importlib.util.spec_from_file_location(
    "delivery_planning_retrieve_plans", RETRIEVER_PATH
)
assert RETRIEVER_SPEC and RETRIEVER_SPEC.loader
RETRIEVER = importlib.util.module_from_spec(RETRIEVER_SPEC)
sys.modules[RETRIEVER_SPEC.name] = RETRIEVER
RETRIEVER_SPEC.loader.exec_module(RETRIEVER)

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


def cycle_item_text(
    work_id: str,
    cycle_id: str,
    *,
    result: str = "Completed",
) -> str:
    return item_text(work_id, result=result).replace(
        'target_paths:\n  - "src/catalog.py"',
        f'target_paths:\n  - "src/catalog.py"\nsprint_id: "{cycle_id}"',
    )


class PlanningCompatibilityTests(unittest.TestCase):
    def build(
        self,
        root: Path,
        mutation: str,
        *,
        plans_path: Path = VALIDATOR.DEFAULT_PLANS_PATH,
        profile_path: Path = VALIDATOR.DEFAULT_PROFILE_PATH,
    ) -> Path:
        plans = root / plans_path
        for lifecycle in ("backlog", "ready", "active", "archived"):
            (plans / lifecycle).mkdir(parents=True, exist_ok=True)
        profile = root / profile_path
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(PROFILE, encoding="utf-8")

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
        return plans

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

    def test_custom_consumer_relative_paths_validate(self) -> None:
        plans_path = Path("planning/work-items")
        profile_path = Path("config/planning-profile.md")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build(
                root,
                "none",
                plans_path=plans_path,
                profile_path=profile_path,
            )
            diagnostics = VALIDATOR.validate_workspace(
                root,
                plans_path=plans_path,
                profile_path=profile_path,
            )
        self.assertEqual([], diagnostics)

    def test_absolute_and_traversing_adapter_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scenarios = (
                {
                    "plans_path": root / "plans",
                    "profile_path": VALIDATOR.DEFAULT_PROFILE_PATH,
                    "expected": "plans path must be consumer-relative",
                },
                {
                    "plans_path": Path("../plans"),
                    "profile_path": VALIDATOR.DEFAULT_PROFILE_PATH,
                    "expected": "plans path escapes consumer root",
                },
                {
                    "plans_path": VALIDATOR.DEFAULT_PLANS_PATH,
                    "profile_path": root / "profile.md",
                    "expected": "profile path must be consumer-relative",
                },
                {
                    "plans_path": VALIDATOR.DEFAULT_PLANS_PATH,
                    "profile_path": Path("../profile.md"),
                    "expected": "profile path escapes consumer root",
                },
            )
            for scenario in scenarios:
                with self.subTest(expected=scenario["expected"]):
                    diagnostics = VALIDATOR.validate_workspace(
                        root,
                        plans_path=scenario["plans_path"],
                        profile_path=scenario["profile_path"],
                    )
                    self.assertEqual(
                        [scenario["expected"]],
                        [item.message for item in diagnostics],
                    )

    def test_symlinked_adapter_path_cannot_escape_consumer_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "consumer"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)

            plans_diagnostics = VALIDATOR.validate_workspace(
                root,
                plans_path=Path("linked/plans"),
            )
            profile_diagnostics = VALIDATOR.validate_workspace(
                root,
                profile_path=Path("linked/profile.md"),
            )

        self.assertEqual(
            ["plans path escapes consumer root"],
            [item.message for item in plans_diagnostics],
        )
        self.assertEqual(
            ["profile path escapes consumer root"],
            [item.message for item in profile_diagnostics],
        )

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
            plans = self.build(root, "none")
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

    def test_target_retrieval_reads_only_dependency_closure_in_large_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plans = self.build(root, "none")
            target = next((plans / "ready").glob("*.md"))
            target.write_text(
                item_text(depends_on='\n  - "catalog-api-00001"'), encoding="utf-8"
            )
            cycle = plans / "archived" / "history" / "sprint-one"
            cycle.mkdir(parents=True)
            dependency = cycle / "catalog-api-00001.prepare.md"
            dependency.write_text(
                item_text("catalog-api-00001", result="Prepared"), encoding="utf-8"
            )
            summaries = plans / "archived" / "summaries"
            summaries.mkdir()
            summary = summaries / "sprint-one.md"
            summary.write_text("# Sprint one summary\n", encoding="utf-8")
            unrelated = plans / "archived" / "history" / "old-cycle"
            unrelated.mkdir()
            for sequence in range(3, 53):
                path = unrelated / f"catalog-api-{sequence:05d}.old.md"
                path.write_text(
                    item_text(
                        f"catalog-api-{sequence:05d}",
                        result="Unrelated " + ("history " * 200),
                    ),
                    encoding="utf-8",
                )

            observed: list[tuple[str, Path]] = []
            result = RETRIEVER.retrieve_projection(
                root,
                "target",
                work_item_id="catalog-api-00002",
                trace=lambda operation, path: observed.append((operation, path)),
            )

        self.assertEqual([], result["diagnostics"])
        self.assertEqual(
            ["catalog-api-00001", "catalog-api-00002"],
            [record["work_item_id"] for record in result["records"]],
        )
        content_reads = [(operation, path.name) for operation, path in observed if operation != "metadata"]
        self.assertEqual(
            [("summary", "sprint-one.md"), ("body", dependency.name), ("body", target.name)],
            content_reads,
        )
        self.assertFalse(any(path.parent.name == "old-cycle" for operation, path in observed if operation == "body"))

    def test_lifecycle_retrieval_enumerates_metadata_without_loading_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build(root, "none")
            observed: list[str] = []
            result = RETRIEVER.retrieve_projection(
                root,
                "lifecycle",
                lifecycle="ready",
                trace=lambda operation, _path: observed.append(operation),
            )

        self.assertEqual([], result["diagnostics"])
        self.assertEqual(1, len(result["records"]))
        self.assertNotIn("content", result["records"][0])
        self.assertEqual(["metadata"], observed)

    def test_retrieval_rejects_path_escape_and_dependency_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "consumer"
            root.mkdir()
            escaped = RETRIEVER.retrieve_projection(
                root,
                "lifecycle",
                lifecycle="ready",
                plans_path=Path("../plans"),
            )
            outside = base / "outside"
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)
            symlinked = RETRIEVER.retrieve_projection(
                root,
                "lifecycle",
                lifecycle="ready",
                plans_path=Path("linked/plans"),
            )

            plans = self.build(root, "none")
            outside_item = outside / "catalog-api-00005.escape.md"
            outside_item.write_text(item_text("catalog-api-00005"), encoding="utf-8")
            (plans / "ready" / outside_item.name).symlink_to(outside_item)
            artifact_escape = RETRIEVER.retrieve_projection(
                root, "lifecycle", lifecycle="ready"
            )
            (plans / "ready" / outside_item.name).unlink()
            first = next((plans / "ready").glob("catalog-api-00002.*.md"))
            first.write_text(
                item_text(depends_on='\n  - "catalog-api-00001"'), encoding="utf-8"
            )
            second = plans / "archived" / "catalog-api-00001.cycle.md"
            second.write_text(
                item_text(
                    "catalog-api-00001",
                    depends_on='\n  - "catalog-api-00002"',
                    result="Prepared",
                ),
                encoding="utf-8",
            )
            cyclic = RETRIEVER.retrieve_projection(
                root, "target", work_item_id="catalog-api-00002"
            )

        self.assertEqual(
            ["plans path escapes consumer root"],
            [item["message"] for item in escaped["diagnostics"]],
        )
        self.assertEqual(
            ["plans path escapes consumer root"],
            [item["message"] for item in symlinked["diagnostics"]],
        )
        self.assertIn(
            "projection record escapes planning root",
            [item["message"] for item in artifact_escape["diagnostics"]],
        )
        self.assertIn(
            "dependency cycle detected",
            [item["message"] for item in cyclic["diagnostics"]],
        )

    def test_audit_explicitly_loads_every_work_item_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plans = self.build(root, "none")
            archived = plans / "archived" / "catalog-api-00001.prepare.md"
            archived.write_text(
                item_text("catalog-api-00001", result="Prepared"), encoding="utf-8"
            )
            observed: list[tuple[str, str]] = []
            result = RETRIEVER.retrieve_projection(
                root,
                "audit",
                trace=lambda operation, path: observed.append((operation, path.name)),
            )

        self.assertEqual([], result["diagnostics"])
        self.assertEqual(2, len(result["records"]))
        self.assertEqual(2, sum(operation == "body" for operation, _ in observed))

    def test_cycle_mode_bounds_compaction_scope_to_one_completed_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plans = self.build(root, "none")
            next((plans / "ready").glob("*.md")).unlink()
            selected_ids = ("catalog-api-00001", "catalog-api-00002")
            for identity in selected_ids:
                (plans / "archived" / f"{identity}.done.md").write_text(
                    cycle_item_text(identity, "sprint-one"), encoding="utf-8"
                )
            (plans / "archived" / "catalog-api-00003.other.md").write_text(
                cycle_item_text("catalog-api-00003", "sprint-two"), encoding="utf-8"
            )

            result = RETRIEVER.retrieve_projection(
                root, "cycle", cycle_id="sprint-one"
            )

            self.assertEqual([], result["diagnostics"])
            self.assertEqual(list(selected_ids), result["compaction"]["scope"])
            self.assertTrue(result["compaction"]["eligible"])
            self.assertEqual(
                list(selected_ids),
                [record["work_item_id"] for record in result["records"]],
            )

            active = plans / "active" / "catalog-api-00004.active.md"
            active.write_text(cycle_item_text("catalog-api-00004", "sprint-one"), encoding="utf-8")
            blocked = RETRIEVER.retrieve_projection(
                root, "cycle", cycle_id="sprint-one"
            )

        self.assertFalse(blocked["compaction"]["eligible"])
        self.assertEqual(
            ["catalog-api-00004"], blocked["compaction"]["blocking_current_items"]
        )
        self.assertNotIn("catalog-api-00003", blocked["compaction"]["scope"])

    def test_validation_mode_caps_full_projection_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plans = self.build(root, "none")
            for sequence in range(3, 108):
                identity = f"catalog-api-{sequence:05d}"
                (plans / "ready" / f"{identity}.invalid.md").write_text(
                    item_text(identity, depends_on='\n  - "missing-item"'),
                    encoding="utf-8",
                )

            result = RETRIEVER.retrieve_projection(root, "validation")

        self.assertEqual(RETRIEVER.MAX_DIAGNOSTICS, len(result["diagnostics"]))
        self.assertGreater(result["omitted_diagnostics"], 0)


if __name__ == "__main__":
    unittest.main()
