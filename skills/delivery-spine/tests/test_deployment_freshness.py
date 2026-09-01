from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "deployment_freshness.py"
SCHEMA = Path(__file__).parents[1] / "references" / "deployment-receipt.schema.json"


class DeploymentFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.artifact = self.root / "artifact"
        self.configuration = self.root / "configuration"
        self.source.mkdir()
        self.artifact.mkdir()
        self.configuration.mkdir()
        (self.source / "service.mjs").write_text("export const version = 1;\n", encoding="utf-8")
        (self.artifact / "bundle.mjs").write_text("export const bundled = 1;\n", encoding="utf-8")
        (self.configuration / "public.json").write_text('{"origin":"https://api.example.test"}\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def identity_arguments(self, environment: str, unit: str, endpoint: str, *, public_configuration: bool) -> list[str]:
        result = [
            "--environment", environment,
            "--deployable-unit", unit,
            "--endpoint", endpoint,
            "--artifact-path", str(self.artifact),
            "--source-path", str(self.source),
        ]
        if public_configuration:
            result.extend(["--public-config-path", str(self.configuration)])
        return result

    def emit(self, environment: str, unit: str, endpoint: str, *, public_configuration: bool) -> Path:
        receipt = self.root / "receipts" / f"{environment}-{unit}.json"
        completed = self.run_cli(
            "emit",
            *self.identity_arguments(environment, unit, endpoint, public_configuration=public_configuration),
            "--deployment-provider", "fixture-provider",
            "--deployment-receipt", f"receipt-{environment}-{unit}",
            "--observed-at", "2026-08-28T19:00:00Z",
            "--output", str(receipt),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return receipt

    def check(self, receipt: Path, environment: str, unit: str, endpoint: str, *, public_configuration: bool, diagnostic: bool = False) -> subprocess.CompletedProcess[str]:
        arguments = [
            "check",
            "--receipt", str(receipt),
            *self.identity_arguments(environment, unit, endpoint, public_configuration=public_configuration),
        ]
        if diagnostic:
            arguments.append("--stale-diagnostic")
        return self.run_cli(*arguments)

    def test_identity_organizations_and_wx_fixtures_match(self) -> None:
        cases = (
            ("development", "workspace-identity", "https://identity.example.test", False),
            ("development", "organizations-api", "https://organizations.example.test/api", False),
            ("staging", "wx-client", "https://wx.example.test", True),
        )
        for environment, unit, endpoint, public_configuration in cases:
            with self.subTest(unit=unit):
                receipt = self.emit(environment, unit, endpoint, public_configuration=public_configuration)
                completed = self.check(receipt, environment, unit, endpoint, public_configuration=public_configuration)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["state"], "FRESH")

    def test_artifact_change_invalidates_only_matching_unit_and_environment(self) -> None:
        identity_receipt = self.emit("development", "workspace-identity", "https://identity.example.test", public_configuration=False)
        wx_receipt = self.emit("staging", "wx-client", "https://wx.example.test", public_configuration=True)
        (self.artifact / "bundle.mjs").write_text("export const bundled = 2;\n", encoding="utf-8")

        stale = self.check(identity_receipt, "development", "workspace-identity", "https://identity.example.test", public_configuration=False)
        self.assertEqual(stale.returncode, 1)
        self.assertEqual(json.loads(stale.stdout)["reasons"], ["artifact_identity_mismatch"])

        (self.artifact / "bundle.mjs").write_text("export const bundled = 1;\n", encoding="utf-8")
        fresh = self.check(wx_receipt, "staging", "wx-client", "https://wx.example.test", public_configuration=True)
        self.assertEqual(fresh.returncode, 0)
        self.assertEqual(json.loads(fresh.stdout)["state"], "FRESH")

    def test_public_configuration_endpoint_and_environment_mismatches_are_stale(self) -> None:
        receipt = self.emit("staging", "wx-client", "https://wx.example.test", public_configuration=True)

        (self.configuration / "public.json").write_text('{"origin":"https://other.example.test"}\n', encoding="utf-8")
        config = self.check(receipt, "staging", "wx-client", "https://wx.example.test", public_configuration=True)
        self.assertEqual(config.returncode, 1)
        self.assertIn("public_configuration_identity_mismatch", json.loads(config.stdout)["reasons"])

        (self.configuration / "public.json").write_text('{"origin":"https://api.example.test"}\n', encoding="utf-8")
        endpoint = self.check(receipt, "staging", "wx-client", "https://other.example.test", public_configuration=True)
        self.assertEqual(endpoint.returncode, 1)
        self.assertIn("endpoint_mismatch", json.loads(endpoint.stdout)["reasons"])

        environment = self.check(receipt, "development", "wx-client", "https://wx.example.test", public_configuration=True)
        self.assertEqual(environment.returncode, 1)
        self.assertIn("environment_mismatch", json.loads(environment.stdout)["reasons"])

    def test_missing_receipt_is_unknown_and_explicit_diagnostic_stays_labeled(self) -> None:
        receipt = self.root / "missing.json"
        blocked = self.check(receipt, "staging", "wx-client", "https://wx.example.test", public_configuration=True)
        self.assertEqual(blocked.returncode, 2)
        self.assertEqual(json.loads(blocked.stdout)["state"], "UNKNOWN")

        diagnostic = self.check(receipt, "staging", "wx-client", "https://wx.example.test", public_configuration=True, diagnostic=True)
        self.assertEqual(diagnostic.returncode, 0)
        self.assertEqual(json.loads(diagnostic.stdout)["evidence_use"], "stale_diagnostic_only")

    def test_receipt_contains_hashes_not_selected_values(self) -> None:
        receipt = self.emit("staging", "wx-client", "https://wx.example.test", public_configuration=True)
        text = receipt.read_text(encoding="utf-8")
        data = json.loads(text)
        self.assertNotIn("api.example.test", text)
        self.assertEqual(data["artifact_identity"]["algorithm"], "sha256")
        self.assertIsInstance(data["public_configuration_identity"]["value"], str)
        self.assertEqual(len(data["public_configuration_identity"]["value"]), 64)

    def test_schema_is_bounded_to_the_runtime_contract(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertFalse(schema["properties"]["deployment"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
