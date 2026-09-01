from __future__ import annotations

import json
import hashlib
import math
import statistics
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import delivery_spine_agent_view as AGENT_VIEW  # noqa: E402
from delivery_spine_projection import ShardedAdapter  # noqa: E402
from validate_delivery_spine import sharded_selection  # noqa: E402


TOKENIZER = {"implementation": "test-tokenizer", "version": "1", "encoding": "characters"}


def policy() -> dict:
    value = AGENT_VIEW.load_policy()
    value["tokenizer"] = TOKENIZER
    return value


class AgentViewTests(unittest.TestCase):
    def test_compact_json_envelope_is_lossless_and_declares_required_metadata(self) -> None:
        data = {"mode": "target", "journey": {"journey_id": "test-journey", "suites": []}}
        rendered = AGENT_VIEW.render_agent_view(
            data,
            "compact-json",
            policy=policy(),
            token_counter=len,
            tokenizer=TOKENIZER,
        )
        envelope = AGENT_VIEW.decode_agent_view(rendered.text, "compact-json")
        self.assertEqual(data, envelope["data"])
        metadata = envelope["agent_view"]
        self.assertEqual("compact-json", metadata["encoding"])
        self.assertEqual("RFC8259", metadata["encoding_version"])
        self.assertEqual(len(rendered.text), metadata["estimated_token_count"])
        self.assertTrue(metadata["complete"])
        self.assertIn("selection_policy", metadata)
        self.assertIn("implementation", metadata)

    def test_auto_selects_header_rows_for_large_uniform_payload(self) -> None:
        data = {
            "mode": "impact",
            "impacted": [
                {"journey_id": f"journey-{index:05d}", "suites": [f"tests/journey-{index:05d}.test"]}
                for index in range(80)
            ],
            "missing_suite_references": [],
        }
        rendered = AGENT_VIEW.render_agent_view(
            data,
            "auto",
            policy=policy(),
            token_counter=len,
            tokenizer=TOKENIZER,
        )
        self.assertEqual("header-json", rendered.encoding)
        self.assertEqual(data, AGENT_VIEW.decode_agent_view(rendered.text, rendered.encoding)["data"])

    def test_auto_keeps_compact_json_for_nested_irregular_payload(self) -> None:
        data = {
            "mode": "target",
            "journey": {"journey_id": "test", "suites": ["a"]},
            "claim": {"boundaries": [{"name": "a"}, {"different": {"nested": [1, {"x": True}]}}]},
        }
        rendered = AGENT_VIEW.render_agent_view(
            data,
            "auto",
            policy=policy(),
            token_counter=len,
            tokenizer=TOKENIZER,
        )
        self.assertEqual("compact-json", rendered.encoding)

    def test_unavailable_explicit_codec_falls_back_to_compact_json(self) -> None:
        data = {"mode": "target", "journey": {"journey_id": "test"}}
        with mock.patch.object(
            AGENT_VIEW,
            "_toon_codec",
            side_effect=AGENT_VIEW.AgentViewError("required implementation is unavailable: toon-format"),
        ):
            rendered = AGENT_VIEW.render_agent_view(
                data,
                "toon",
                policy=policy(),
                token_counter=len,
                tokenizer=TOKENIZER,
            )
        self.assertEqual("compact-json", rendered.encoding)
        self.assertEqual("toon", rendered.requested_encoding)
        self.assertIsNotNone(rendered.fallback_reason)

    def test_missing_tokenizer_for_auto_falls_back_to_compact_json(self) -> None:
        data = {"mode": "impact", "impacted": [{"journey_id": "test", "suites": []}] * 100}
        with mock.patch.object(
            AGENT_VIEW,
            "policy_token_counter",
            side_effect=AGENT_VIEW.AgentViewError("required implementation is unavailable: tiktoken"),
        ):
            rendered = AGENT_VIEW.render_agent_view(data, "auto", policy=policy())
        self.assertEqual("compact-json", rendered.encoding)
        self.assertIsNone(rendered.estimated_token_count)
        self.assertIn("tiktoken", rendered.fallback_reason)

    def test_encoder_failure_falls_back_to_compact_json(self) -> None:
        def failed_encode(value):
            raise ValueError("synthetic encoder failure")

        with mock.patch.object(
            AGENT_VIEW,
            "_toon_codec",
            return_value=(failed_encode, lambda text: {}, "0.9.0b1"),
        ):
            rendered = AGENT_VIEW.render_agent_view(
                {"mode": "target"},
                "toon",
                policy=policy(),
                token_counter=len,
                tokenizer=TOKENIZER,
            )
        self.assertEqual("compact-json", rendered.encoding)
        self.assertIn("synthetic encoder failure", rendered.fallback_reason)

    def test_unapproved_external_implementation_falls_back(self) -> None:
        try:
            AGENT_VIEW._toon_codec()
        except AGENT_VIEW.AgentViewError:
            self.skipTest("optional TOON implementation is unavailable")
        selected_policy = policy()
        selected_policy["candidate_implementations"]["toon"] = {
            "implementation": "toon-format",
            "version": "unapproved",
        }
        rendered = AGENT_VIEW.render_agent_view(
            {"mode": "target"},
            "toon",
            policy=selected_policy,
            token_counter=len,
            tokenizer=TOKENIZER,
        )
        self.assertEqual("compact-json", rendered.encoding)
        self.assertIn("unapproved", rendered.fallback_reason)

    def test_restricted_yaml_rejects_unsafe_features(self) -> None:
        try:
            _, decode, _ = AGENT_VIEW._yaml_codec()
        except AGENT_VIEW.AgentViewError:
            self.skipTest("optional YAML implementation is unavailable")
        invalid = (
            "key: one\nkey: two\n",
            "key: &anchor one\ncopy: *anchor\n",
            "key: !application/object value\n",
            "1: value\n",
        )
        for document in invalid:
            with self.subTest(document=document), self.assertRaises((AGENT_VIEW.AgentViewError, Exception)):
                decode(document)

    def test_alias_candidate_includes_dictionary_and_round_trips(self) -> None:
        data = {
            "claims": [
                {"journey_id": f"journey-{index}", "work_item_id": f"item-{index}", "evidence": []}
                for index in range(20)
            ]
        }
        rendered = AGENT_VIEW.render_candidate(
            data,
            "header-json-aliases",
            "header-json-aliases",
            policy(),
            token_counter=len,
            tokenizer=TOKENIZER,
        )
        self.assertIn("$delivery_spine_aliases", rendered.text)
        self.assertEqual(data, AGENT_VIEW.decode_agent_view(rendered.text, rendered.encoding)["data"])

    def test_target_selection_reads_only_exact_claim_and_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter_root = root / "_notes" / "delivery-spine"
            (adapter_root / "claims").mkdir(parents=True)
            (adapter_root / "baselines").mkdir()
            registry = {
                "schema_version": 2,
                "journeys": [
                    {"journey_id": name, "outcome": name, "affected_paths": [f"services/{name}"], "suites": [f"tests/{name}.test"]}
                    for name in ("first", "second")
                ],
            }
            index = {
                "schema_version": 2,
                "active_staging_slice": None,
                "claims": [
                    {"journey_id": name, "work_item_id": f"item-{name}", "claim_path": f"claims/{name}.json"}
                    for name in ("first", "second")
                ],
            }
            (adapter_root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            (adapter_root / "claims" / "index.json").write_text(json.dumps(index), encoding="utf-8")
            for name in ("first", "second"):
                claim = {
                    "schema_version": 2,
                    "claim_id": f"claim-{name}",
                    "journey_id": name,
                    "work_item_id": f"item-{name}",
                    "target_level": "source_complete",
                    "current_level": "source_complete",
                    "boundaries": [{"name": "source", "owner": f"services/{name}", "target": "local", "state": "verified"}],
                    "evidence": [{"class": "component", "reference": f"tests/{name}", "observed_at": "2026-09-01T00:00:00Z"}],
                    "blockers": [],
                }
                (adapter_root / "claims" / f"{name}.json").write_text(json.dumps(claim), encoding="utf-8")
            adapter = ShardedAdapter(root, "_notes/delivery-spine")
            observed: list[str] = []
            original = adapter.read

            def recording_read(relative: str):
                observed.append(relative)
                return original(relative)

            adapter.read = recording_read  # type: ignore[method-assign]
            result, selected, diagnostics = sharded_selection(
                adapter,
                "target",
                journey_id="second",
                work_item_id=None,
                claim_id=None,
                evidence_reference=None,
                dependency=None,
                changed_paths=[],
            )
            self.assertEqual([], diagnostics)
            self.assertEqual("second", selected)
            self.assertEqual("second", result["claim"]["journey_id"])
            self.assertNotIn("claims/first.json", observed)
            self.assertNotIn("baselines/first.json", observed)

            observed.clear()
            result, selected, diagnostics = sharded_selection(
                adapter,
                "work-item",
                journey_id=None,
                work_item_id="item-first",
                claim_id=None,
                evidence_reference=None,
                dependency=None,
                changed_paths=[],
            )
            self.assertEqual([], diagnostics)
            self.assertEqual("first", selected)
            self.assertEqual("first", result["claim"]["journey_id"])
            self.assertNotIn("claims/second.json", observed)
            self.assertNotIn("baselines/second.json", observed)

    def test_selection_policy_matches_retained_benchmark_evidence(self) -> None:
        selected_policy = AGENT_VIEW.load_policy()
        results_path = SKILL_ROOT / "references" / "agent-view-benchmark-results.json"
        results = json.loads(results_path.read_text(encoding="utf-8"))
        fixture_path = SKILL_ROOT / "tests" / "fixtures" / "agent-view-workloads.json"
        fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
        self.assertEqual(fixture_hash, results["fixture_sha256"])
        self.assertEqual(fixture_hash, selected_policy["benchmark"]["fixture_sha256"])
        compact_counts = [
            next(candidate["tokens"] for candidate in workload["candidates"] if candidate["candidate"] == "compact-json")
            for workload in results["results"]
        ]
        expected_floor = math.ceil(0.15 * statistics.median(compact_counts))
        self.assertEqual(expected_floor, results["absolute_floor_tokens"])
        self.assertEqual(expected_floor, selected_policy["thresholds"]["absolute_floor_tokens"])
        for approved in selected_policy["approved_candidates"]:
            qualifying = False
            for workload in results["results"]:
                baseline = next(item for item in workload["candidates"] if item["candidate"] == "compact-json")
                candidate = next(item for item in workload["candidates"] if item["candidate"] == approved)
                self.assertTrue(candidate["lossless"])
                self.assertTrue(candidate["task_answer_parity"])
                saved = baseline["tokens"] - candidate["tokens"]
                qualifying |= saved >= expected_floor and 100 * saved / baseline["tokens"] >= 15
            self.assertTrue(qualifying, f"approved candidate lacks a qualifying representative workload: {approved}")


if __name__ == "__main__":
    unittest.main()
