from __future__ import annotations

import importlib.util
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
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            for target in VALIDATE.LINK_PATTERN.findall(text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (package / target.split("#", 1)[0]).resolve()
                self.assertIn(package.resolve(), resolved.parents)

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
