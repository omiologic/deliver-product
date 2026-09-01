from __future__ import annotations

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("delivery_validate", ROOT / "scripts" / "validate.py")
assert SPEC and SPEC.loader
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


class WorkspaceValidationTests(unittest.TestCase):
    def test_workspace_contracts_are_valid(self) -> None:
        self.assertEqual([], VALIDATE.validate())

    def test_all_packages_are_independently_installable(self) -> None:
        for name in VALIDATE.SKILLS:
            package = ROOT / "skills" / name
            self.assertTrue((package / "SKILL.md").is_file())
            for source in package.rglob("*.md"):
                text = source.read_text(encoding="utf-8")
                for target in VALIDATE.LINK_PATTERN.findall(text):
                    if "://" in target or target.startswith("#"):
                        continue
                    resolved = (source.parent / target.split("#", 1)[0]).resolve()
                    self.assertTrue(resolved.is_file(), f"{source}: {target}")
                    self.assertIn(package.resolve(), resolved.parents)

    def test_planning_type_routing_scenarios(self) -> None:
        fixtures = json.loads(
            (ROOT / "tests" / "fixtures" / "planning_type_routing.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in fixtures:
            with self.subTest(scenario=scenario["name"]):
                selected, source = VALIDATE.select_planning_type(**scenario["inputs"])
                self.assertEqual(scenario["expected_type"], selected)
                self.assertEqual(scenario["expected_source"], source)

    def test_governed_context_scenarios(self) -> None:
        fixtures = json.loads(
            (ROOT / "tests" / "fixtures" / "governed_context.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in fixtures:
            with self.subTest(scenario=scenario["name"]):
                action, handling = VALIDATE.planning_response_to_governed_context(
                    scenario["owner_classification"]
                )
                self.assertEqual(scenario["expected_action"], action)
                self.assertEqual(scenario["expected_handling"], handling)

    def test_unknown_governed_context_classification_is_not_inferred(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported governed-context classification"):
            VALIDATE.planning_response_to_governed_context("delivery-inferred")

    def test_projection_persistence_authority_scenarios(self) -> None:
        fixtures = json.loads(
            (ROOT / "tests" / "fixtures" / "persistence_authority.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in fixtures:
            with self.subTest(scenario=scenario["name"]):
                self.assertEqual(
                    scenario["expected"],
                    VALIDATE.projection_persistence_allowed(**scenario["inputs"]),
                )

    def test_reconciliation_has_closed_assessment_vocabulary(self) -> None:
        contract = (
            ROOT
            / "skills"
            / "delivery-reconciliation"
            / "references"
            / "assessment-contract.md"
        ).read_text(encoding="utf-8")
        observed = set(re.findall(r"\| `([A-Z_]+)` \|", contract))
        self.assertEqual(set(VALIDATE.ASSESSMENTS), observed)

    def test_execution_contract_scenarios(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "execution_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                disposition, diagnostics = VALIDATE.evaluate_execution_scenario(scenario)
                self.assertEqual(scenario["expected_disposition"], disposition)
                self.assertEqual(scenario["expected_diagnostics"], diagnostics)

    def test_stale_execution_scope_cannot_proceed(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "execution_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = next(item for item in scenarios if item["name"] == "stale scope is handed to reconciliation")
        disposition, _ = VALIDATE.evaluate_execution_scenario(scenario)
        self.assertEqual("reconcile", disposition)
        self.assertNotEqual("execute", disposition)

    def test_execution_observation_requires_separate_result_and_evidence_fields(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "execution_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = copy.deepcopy(
            next(item for item in scenarios if item["name"] == "successful result remains distinct from evidence")
        )
        del scenario["observation"]["evidence_references"]
        disposition, diagnostics = VALIDATE.evaluate_execution_scenario(scenario)
        self.assertEqual("blocked", disposition)
        self.assertIn("execution observation missing field: evidence_references", diagnostics)

    def test_reconciliation_contract_scenarios_cover_every_assessment(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "reconciliation_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        observed: set[str] = set()
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                assessment, diagnostics = VALIDATE.assess_reconciliation_scenario(scenario)
                self.assertEqual(scenario["expected_assessment"], assessment)
                self.assertEqual(scenario["expected_diagnostics"], diagnostics)
                observed.add(assessment)
        self.assertEqual(set(VALIDATE.ASSESSMENTS), observed)

    def test_successful_operation_without_verification_is_not_success(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "reconciliation_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = next(
            item
            for item in scenarios
            if item["name"] == "successful operation without verification is not success"
        )
        assessment, diagnostics = VALIDATE.assess_reconciliation_scenario(scenario)
        self.assertEqual([], diagnostics)
        self.assertEqual("BLOCKED", assessment)
        self.assertNotEqual("SUCCESS", assessment)

    def test_reconciliation_rejects_unattributable_evidence_and_unowned_recommendation(self) -> None:
        scenario = {
            "criteria": [{"id": "criterion-1", "evidence": {}}],
            "facts": {"blocked": True},
            "recommendation": {"action": "resolve-blocker"},
        }
        assessment, diagnostics = VALIDATE.assess_reconciliation_scenario(scenario)
        self.assertEqual("BLOCKED", assessment)
        self.assertIn(
            "criterion criterion-1 evidence must classify supporting, contradicting, and missing",
            diagnostics,
        )
        self.assertIn("recommendation requires an owner", diagnostics)

    def test_replan_assessments_use_bounded_advisory_recommendations(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "reconciliation_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        for expected in ("DIVERGED", "NEEDS_REPLAN"):
            scenario = next(item for item in scenarios if item["expected_assessment"] == expected)
            assessment, diagnostics = VALIDATE.assess_reconciliation_scenario(scenario)
            self.assertEqual(expected, assessment)
            self.assertEqual([], diagnostics)
            self.assertEqual("replan-affected-scope", scenario["recommendation"]["action"])

    def test_workspace_validator_executes_behavioral_fixtures(self) -> None:
        self.assertEqual([], VALIDATE.validate_scenario_fixtures())

    def test_thin_router_contract_scenarios(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "routing_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                self.assertEqual(
                    scenario["expected"], VALIDATE.route_delivery_scenario(scenario)
                )

    def test_unreconciled_evidence_precedes_additional_execution(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "routing_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = next(
            item
            for item in scenarios
            if item["name"] == "unreconciled result takes precedence over ready work"
        )
        routed = VALIDATE.route_delivery_scenario(scenario)
        self.assertEqual("delivery-reconciliation", routed["lane"])
        self.assertNotEqual("delivery-execution", routed["lane"])

    def test_router_names_owner_for_missing_canonical_readiness(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "routing_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = next(
            item
            for item in scenarios
            if item["name"] == "conversation claims do not supply readiness"
        )
        routed = VALIDATE.route_delivery_scenario(scenario)
        self.assertEqual("blocked", routed["lane"])
        self.assertTrue(
            all(
                blocker["owner"] == "canonical runtime or responsible person"
                for blocker in routed["blockers"]
            )
        )

    def test_router_passes_consumer_contract_without_selecting_planning_type(self) -> None:
        scenario = {
            "request": {"durable_work_required": True, "work_defined": False},
            "owner_state": {},
            "evidence": {},
            "operation": {"kind": "advisory"},
            "planning_inputs": {
                "consumer_conventions": {
                    "default_planning_type": "consumer-owned-special"
                },
                "consumer_contract": {"methodology": "consumer-owned"},
            },
        }
        routed = VALIDATE.route_delivery_scenario(scenario)
        self.assertIs(scenario["planning_inputs"], routed["stage_inputs"])
        self.assertEqual(
            "consumer-owned-special",
            routed["stage_inputs"]["consumer_conventions"]["default_planning_type"],
        )

    def test_adapter_loads_only_for_selected_representation_operation(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "routing_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        advisory = next(
            item
            for item in scenarios
            if item["name"] == "configured adapter stays unloaded for advisory planning"
        )
        validation = next(
            item
            for item in scenarios
            if item["name"] == "projection validation loads the selected adapter"
        )
        unauthorized = next(
            item
            for item in scenarios
            if item["name"] == "adapter selection alone cannot authorize persistence"
        )
        self.assertIsNone(VALIDATE.route_delivery_scenario(advisory)["adapter_loaded"])
        self.assertEqual(
            "repository-local-work-items",
            VALIDATE.route_delivery_scenario(validation)["adapter_loaded"],
        )
        unauthorized_result = VALIDATE.route_delivery_scenario(unauthorized)
        self.assertIsNone(unauthorized_result["adapter_loaded"])
        self.assertTrue(unauthorized_result["blockers"])

    def test_lifecycle_scenarios_cover_continuation_and_bounded_replanning(self) -> None:
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "lifecycle_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                lanes, diagnostics = VALIDATE.evaluate_lifecycle_scenario(scenario)
                self.assertEqual(scenario["expected_lanes"], lanes)
                self.assertEqual(scenario["expected_diagnostics"], diagnostics)

        replanning = next(
            item
            for item in scenarios
            if item["name"] == "divergence returns only affected scope to planning"
        )
        final_inputs = VALIDATE.route_delivery_scenario(replanning["steps"][-1])[
            "stage_inputs"
        ]
        self.assertEqual(
            ["catalog response serialization"], final_inputs["affected_scope"]
        )

    def test_workspace_validator_executes_routing_fixtures(self) -> None:
        self.assertEqual([], VALIDATE.validate_routing_fixtures())


if __name__ == "__main__":
    unittest.main()
