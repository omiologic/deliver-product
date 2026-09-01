from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
