#!/usr/bin/env python3
"""Benchmark complete Delivery Spine agent views on public-safe workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from delivery_spine_agent_view import (
    AgentViewError,
    INTERNAL_CANDIDATES,
    decode_agent_view,
    load_policy,
    policy_token_counter,
    render_candidate,
)


DEFAULT_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "agent-view-workloads.json"


def materialize(specification: dict[str, Any]) -> dict[str, Any]:
    generator = specification["generator"]
    count = specification.get("count", 0)
    if generator == "large-uniform-history":
        claims = []
        for index in range(count):
            suffix = f"{index:05d}"
            claims.append(
                {
                    "schema_version": 2,
                    "claim_id": f"claim-{suffix}",
                    "journey_id": f"history-{suffix}",
                    "work_item_id": f"done-{suffix}",
                    "target_level": "staging_verified",
                    "current_level": "staging_verified",
                    "boundaries": [
                        {"name": "browser", "owner": "interfaces/web", "target": "staging", "state": "verified"}
                    ],
                    "evidence": [
                        {
                            "class": "staging_e2e",
                            "reference": f"tests/evidence/history-{suffix}.json",
                            "observed_at": "2026-08-31T00:00:00Z",
                        }
                    ],
                    "blockers": [],
                }
            )
        return {"mode": "history", "journey_id": "benchmark-history", "claims": claims}
    if generator == "uniform-impact":
        return {
            "mode": "impact",
            "impacted": [
                {"journey_id": f"journey-{index:05d}", "suites": [f"tests/journey-{index:05d}.test"]}
                for index in range(count)
            ],
            "missing_suite_references": [],
        }
    if generator == "nested-irregular-target":
        return {
            "mode": "target",
            "journey": {
                "journey_id": "identity-administration",
                "outcome": "An administrator safely manages one identity.",
                "affected_paths": ["interfaces/admin", "services/identity"],
                "suites": ["tests/identity-administration.test"],
            },
            "claim": {
                "schema_version": 2,
                "claim_id": "identity-00008",
                "journey_id": "identity-administration",
                "work_item_id": "identity-00008",
                "target_level": "integrated",
                "current_level": "source_complete",
                "boundaries": [
                    {"name": "browser", "owner": "interfaces/admin", "target": "local", "state": "verified"},
                    {"name": "identity-provider", "owner": "services/identity", "target": "isolated", "state": "missing"},
                ],
                "evidence": [],
                "blockers": ["identity-provider configuration is missing"],
            },
            "baseline": {
                "schema_version": 2,
                "journey_id": "identity-administration",
                "claim_id": "identity-00007",
                "current_level": "source_complete",
                "boundaries": [{"name": "browser", "owner": "interfaces/admin", "target": "local", "state": "verified"}],
                "evidence": [
                    {
                        "class": "component",
                        "reference": "tests/evidence/identity-baseline.json",
                        "observed_at": "2026-08-30T00:00:00Z",
                    }
                ],
            },
            "active_staging_slice": None,
        }
    raise ValueError(f"unknown workload generator: {generator}")


def answer(data: Any, path: list[Any]) -> Any:
    selected = data
    for segment in path:
        selected = selected[segment]
    return selected


def run(fixture_path: Path) -> dict[str, Any]:
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes)
    policy = load_policy()
    counter, tokenizer = policy_token_counter(policy)
    results: list[dict[str, Any]] = []
    compact_counts: list[int] = []
    for workload in fixture["workloads"]:
        data = materialize(workload)
        expected = {question["id"]: question["expected"] for question in workload["questions"]}
        candidates: list[dict[str, Any]] = []
        for candidate in INTERNAL_CANDIDATES:
            try:
                rendered = render_candidate(
                    data,
                    candidate,
                    candidate,
                    policy,
                    token_counter=counter,
                    tokenizer=tokenizer,
                )
                reconstructed = decode_agent_view(rendered.text, candidate)["data"]
                metadata = decode_agent_view(rendered.text, candidate)["agent_view"]
                observed = {question["id"]: answer(reconstructed, question["path"]) for question in workload["questions"]}
                record = {
                    "candidate": candidate,
                    "available": True,
                    "bytes": len(rendered.text.encode("utf-8")),
                    "tokens": rendered.estimated_token_count,
                    "lossless": reconstructed == data,
                    "task_answer_parity": observed == expected,
                    "encoding_version": metadata["encoding_version"],
                    "implementation": metadata["implementation"],
                }
                if candidate == "compact-json":
                    compact_counts.append(rendered.estimated_token_count or 0)
            except (AgentViewError, ImportError, TypeError, ValueError) as exc:
                record = {"candidate": candidate, "available": False, "reason": str(exc)}
            candidates.append(record)
        results.append({"workload": workload["name"], "candidates": candidates})
    floor = math.ceil(0.15 * statistics.median(compact_counts))
    return {
        "schema_version": 1,
        "fixture": str(fixture_path),
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "tokenizer": tokenizer,
        "absolute_floor_tokens": floor,
        "floor_derivation": "ceil(15% of representative compact-JSON median)",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.fixture)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
