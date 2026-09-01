#!/usr/bin/env python3
"""Validate the Delivery skill workspace without third-party dependencies."""

from __future__ import annotations

import json
import hashlib
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORE_SKILLS = (
    "deliver-product",
    "delivery-planning",
    "delivery-execution",
    "delivery-reconciliation",
)
IMPORTED_SKILLS = ("delivery-spine",)
SKILLS = CORE_SKILLS + IMPORTED_SKILLS
ASSESSMENTS = (
    "SUCCESS",
    "PARTIAL",
    "FAILED",
    "BLOCKED",
    "STALE",
    "DIVERGED",
    "SUPERSEDED",
    "NEEDS_REPLAN",
)
LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")
DEFAULT_PLANNING_TYPE = "bounded-outcome"
GOVERNED_CONTEXT_RESPONSES = {
    "absent": ("proceed", "disclose-unavailable"),
    "applicable": ("proceed", "apply-with-provenance"),
    "conflicting": ("await-owner", "do-not-select-conflicting-context"),
    "blocking": ("blocked", "do-not-produce-ready-work"),
}
EXECUTION_ENVELOPE_FIELDS = (
    "exact_work_item_selected",
    "canonical_approval",
    "canonical_readiness",
    "immutable_scope",
    "acceptance_criteria_defined",
    "context_assigned",
    "capabilities_assigned",
)
RECONCILIATION_RECOMMENDATIONS = {
    "SUCCESS": "review-verified-outcome",
    "PARTIAL": "address-remaining-criteria",
    "FAILED": "review-failed-attempt",
    "BLOCKED": "resolve-blocker",
    "STALE": "refresh-execution-snapshot",
    "DIVERGED": "replan-affected-scope",
    "SUPERSEDED": "review-owner-replacement",
    "NEEDS_REPLAN": "replan-affected-scope",
}
SCENARIO_FIXTURES = (
    "execution_scenarios.json",
    "reconciliation_scenarios.json",
)
ROUTING_FIXTURES = (
    "routing_scenarios.json",
    "lifecycle_scenarios.json",
)
REPLAN_ASSESSMENTS = ("DIVERGED", "NEEDS_REPLAN")
REPRESENTATION_OPERATIONS = ("persist-projection", "validate-projection")
EXECUTION_INPUT_OWNERS = {
    "exact_work_item_selected": "WorkItem owner or responsible person",
    "canonical_approval": "canonical runtime or responsible person",
    "canonical_readiness": "canonical runtime or responsible person",
    "immutable_scope": "execution snapshot owner",
    "acceptance_criteria_defined": "execution snapshot owner",
    "context_assigned": "context owner",
    "capabilities_assigned": "capability owner",
    "intended_effects": "user, policy, or authorized operation",
}
PLANNING_REFERENCES = (
    "references/planning-contract.md",
    "references/planning-type-routing.md",
    "references/consumer-conventions.md",
    "references/planning-types/bounded-outcome.md",
    "references/planning-types/feature-development.md",
    "references/planning-types/sprint.md",
    "references/planning-types/research.md",
    "references/planning-types/phased-project.md",
    "references/adapters/repository-local-work-items.md",
    "references/adapters/repository-local/planning-profiles.md",
    "references/adapters/repository-local/work-item-conventions.md",
    "references/adapters/repository-local/work-item-lifecycle.md",
)
PLANNING_COMPATIBILITY_FILES = (
    "assets/task-template.md",
    "scripts/validate_plans.py",
)


def validate_agent_view_policy() -> list[str]:
    """Validate retained benchmark evidence and auto-selection thresholds."""
    errors: list[str] = []
    root = ROOT / "skills" / "delivery-spine"
    policy_path = root / "references" / "agent-view-selection-policy.json"
    results_path = root / "references" / "agent-view-benchmark-results.json"
    fixture_path = root / "tests" / "fixtures" / "agent-view-workloads.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        results = json.loads(results_path.read_text(encoding="utf-8"))
        fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"delivery-spine agent views: cannot load policy evidence: {exc}"]
    if policy.get("schema_version") != 1 or results.get("schema_version") != 1:
        errors.append("delivery-spine agent views: policy and results must use schema version 1")
        return errors
    if fixture_hash != results.get("fixture_sha256") or fixture_hash != policy.get("benchmark", {}).get("fixture_sha256"):
        errors.append("delivery-spine agent views: benchmark fixture hash does not match retained evidence")
    try:
        compact_counts = [
            next(candidate["tokens"] for candidate in workload["candidates"] if candidate["candidate"] == "compact-json")
            for workload in results["results"]
        ]
        expected_floor = math.ceil(0.15 * statistics.median(compact_counts))
    except (KeyError, StopIteration, TypeError, statistics.StatisticsError):
        errors.append("delivery-spine agent views: benchmark results lack compact-JSON measurements")
        return errors
    if expected_floor != policy.get("thresholds", {}).get("absolute_floor_tokens"):
        errors.append("delivery-spine agent views: absolute token floor is not benchmark-derived")
    minimum_percent = policy.get("thresholds", {}).get("minimum_percent")
    if minimum_percent != 15:
        errors.append("delivery-spine agent views: minimum net savings must remain 15 percent")
    for workload in results.get("results", []):
        for candidate in workload.get("candidates", []):
            if candidate.get("available") and (
                not candidate.get("lossless") or not candidate.get("task_answer_parity")
            ):
                errors.append(
                    "delivery-spine agent views: eligible benchmark candidate failed "
                    f"reconstruction or answer parity: {candidate.get('candidate')}"
                )
    approved_candidates = policy.get("approved_candidates", [])
    aliases_approved = policy.get("property_aliases", {}).get("approved") is True
    if aliases_approved != ("header-json-aliases" in approved_candidates):
        errors.append("delivery-spine agent views: alias approval disagrees with approved candidates")
    for approved in approved_candidates:
        qualifying = False
        for workload in results["results"]:
            try:
                baseline = next(item for item in workload["candidates"] if item["candidate"] == "compact-json")
                candidate = next(item for item in workload["candidates"] if item["candidate"] == approved)
            except StopIteration:
                errors.append(f"delivery-spine agent views: approved candidate lacks measurements: {approved}")
                break
            if not candidate.get("lossless") or not candidate.get("task_answer_parity"):
                errors.append(f"delivery-spine agent views: approved candidate failed parity: {approved}")
                break
            saved = baseline["tokens"] - candidate["tokens"]
            qualifying = qualifying or (
                saved >= expected_floor and 100 * saved / baseline["tokens"] >= minimum_percent
            )
        if not qualifying:
            errors.append(f"delivery-spine agent views: approved candidate has no qualifying workload: {approved}")
    if aliases_approved:
        incremental_win = False
        for workload in results["results"]:
            plain = next(item for item in workload["candidates"] if item["candidate"] == "header-json")
            aliased = next(item for item in workload["candidates"] if item["candidate"] == "header-json-aliases")
            incremental_win = incremental_win or aliased["tokens"] < plain["tokens"]
        if not incremental_win:
            errors.append("delivery-spine agent views: approved aliases lack an incremental net win")
    return errors


def normalize_planning_type(value: str) -> str:
    """Preserve the legacy quick-task identifier without duplicating a procedure."""
    return DEFAULT_PLANNING_TYPE if value == "quick-task" else value


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    try:
        block = text.split("---\n", 2)[1]
    except IndexError:
        return {}
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def select_planning_type(
    *,
    explicit: str | None = None,
    owner_produced: str | None = None,
    consumer_convention: str | None = None,
    clear_inference: str | None = None,
    materially_ambiguous: bool = False,
) -> tuple[str | None, str]:
    """Model the documented planning-type precedence for contract fixtures."""
    for source, value in (
        ("explicit", explicit),
        ("owner-produced", owner_produced),
        ("consumer-convention", consumer_convention),
    ):
        if value:
            return normalize_planning_type(value), source
    if materially_ambiguous:
        return None, "unresolved"
    if clear_inference:
        return normalize_planning_type(clear_inference), "clear-inference"
    return DEFAULT_PLANNING_TYPE, "default"


def planning_response_to_governed_context(classification: str) -> tuple[str, str]:
    """Model Planning's response to an owner-produced context classification."""
    try:
        return GOVERNED_CONTEXT_RESPONSES[classification]
    except KeyError as exc:
        raise ValueError(f"unsupported governed-context classification: {classification}") from exc


def projection_persistence_allowed(
    *,
    adapter_selected: bool,
    explicit_or_owner_produced_intent: bool,
    filesystem_authority: bool,
) -> bool:
    """Model the three independent prerequisites for a planning projection write."""
    return adapter_selected and explicit_or_owner_produced_intent and filesystem_authority


def _execution_blockers(diagnostics: list[str]) -> list[dict[str, str]]:
    """Attach the responsible owner to execution-routing diagnostics."""
    blockers: list[dict[str, str]] = []
    for diagnostic in diagnostics:
        if diagnostic.startswith("missing required envelope input: "):
            field = diagnostic.rsplit(": ", 1)[1]
            owner = EXECUTION_INPUT_OWNERS.get(field, "execution owner")
        elif diagnostic.startswith("effect lacks explicit authority: "):
            owner = "user, policy, or authorized operation"
        elif diagnostic == "execution prerequisites are contradictory":
            owner = "canonical runtime or responsible person"
        elif diagnostic == "immutable execution scope is stale":
            owner = "execution snapshot owner"
        else:
            owner = "execution owner"
        blockers.append({"reason": diagnostic, "owner": owner})
    return blockers


def route_delivery_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Select one thin-router lane and preserve the selected stage's inputs."""
    request = scenario.get("request", {})
    owner_state = scenario.get("owner_state", {})
    evidence = scenario.get("evidence", {})
    operation = scenario.get("operation", {})
    if not all(isinstance(value, dict) for value in (request, owner_state, evidence, operation)):
        return {
            "lane": "blocked",
            "stage_inputs": None,
            "adapter_loaded": None,
            "blockers": [
                {"reason": "routing inputs must be objects", "owner": "request owner"}
            ],
        }

    blockers: list[dict[str, str]] = []
    has_unreconciled_evidence = any(
        evidence.get(field) is True
        for field in ("execution_results", "observed_changes", "verification_evidence")
    )
    if has_unreconciled_evidence:
        lane = "delivery-reconciliation"
        stage_inputs = scenario.get("reconciliation_inputs", {})
    elif (
        owner_state.get("reconciliation_complete") is True
        and owner_state.get("reconciliation_assessment") in REPLAN_ASSESSMENTS
    ):
        lane = "delivery-planning"
        stage_inputs = scenario.get("planning_inputs", {})
    elif request.get("durable_work_required") is False:
        lane = "direct-answer"
        stage_inputs = None
    elif request.get("durable_work_required") is not True:
        lane = "blocked"
        stage_inputs = None
        blockers = [
            {
                "reason": "missing explicit durable-work routing intent",
                "owner": "request owner",
            }
        ]
    elif request.get("work_defined") is False:
        lane = "delivery-planning"
        stage_inputs = scenario.get("planning_inputs", {})
    elif request.get("work_defined") is not True:
        lane = "blocked"
        stage_inputs = None
        blockers = [
            {
                "reason": "missing owner-produced work definition state",
                "owner": "WorkItem owner or responsible person",
            }
        ]
    else:
        envelope = owner_state.get("execution_envelope", {})
        disposition, diagnostics = evaluate_execution_scenario(
            {"envelope": envelope, "observation": None}
        )
        if disposition == "execute":
            lane = "delivery-execution"
            stage_inputs = scenario.get("execution_inputs", envelope)
        elif disposition == "reconcile":
            lane = "delivery-reconciliation"
            stage_inputs = scenario.get("reconciliation_inputs", {})
            blockers = _execution_blockers(diagnostics)
        else:
            lane = "blocked"
            stage_inputs = None
            blockers = _execution_blockers(diagnostics)

    adapter = owner_state.get("adapter")
    adapter_loaded: str | None = None
    operation_kind = operation.get("kind", "advisory")
    if lane == "delivery-planning" and operation_kind in REPRESENTATION_OPERATIONS:
        if not isinstance(adapter, dict) or adapter.get("selected") is not True:
            blockers.append(
                {"reason": "representation operation requires a selected adapter", "owner": "consumer owner"}
            )
        elif operation_kind == "validate-projection":
            adapter_loaded = adapter.get("name")
        elif projection_persistence_allowed(
            adapter_selected=True,
            explicit_or_owner_produced_intent=operation.get("persistence_intent") is True,
            filesystem_authority=operation.get("filesystem_authority") is True,
        ):
            adapter_loaded = adapter.get("name")
        else:
            blockers.append(
                {"reason": "projection persistence lacks intent or filesystem authority", "owner": "user or workflow owner"}
            )

    return {
        "lane": lane,
        "stage_inputs": stage_inputs,
        "adapter_loaded": adapter_loaded,
        "blockers": blockers,
    }


def evaluate_execution_scenario(scenario: dict[str, Any]) -> tuple[str, list[str]]:
    """Evaluate an execution envelope without creating lifecycle state."""
    envelope = scenario.get("envelope", {})
    if not isinstance(envelope, dict):
        return "blocked", ["execution envelope must be an object"]
    observation = scenario.get("observation")
    diagnostics: list[str] = []

    for field in EXECUTION_ENVELOPE_FIELDS:
        if envelope.get(field) is not True:
            diagnostics.append(f"missing required envelope input: {field}")

    intended_effects = envelope.get("intended_effects")
    if not isinstance(intended_effects, list) or not intended_effects:
        diagnostics.append("missing required envelope input: intended_effects")
    else:
        for effect in intended_effects:
            name = (
                effect.get("name", "unnamed effect")
                if isinstance(effect, dict)
                else "unnamed effect"
            )
            if not isinstance(effect, dict) or effect.get("authorized") is not True:
                diagnostics.append(f"effect lacks explicit authority: {name}")

    if envelope.get("contradictory_prerequisites") is True:
        diagnostics.append("execution prerequisites are contradictory")

    if envelope.get("stale_scope") is True:
        diagnostics.append("immutable execution scope is stale")
        if len(diagnostics) == 1:
            return "reconcile", diagnostics

    if diagnostics:
        return "blocked", diagnostics

    if observation is None:
        return "execute", []
    if not isinstance(observation, dict):
        return "blocked", ["execution observation must be an object"]

    required_observation_fields = (
        "attempted_action",
        "result",
        "affected_targets",
        "evidence_references",
        "failures",
        "blockers",
    )
    for field in required_observation_fields:
        if field not in observation:
            diagnostics.append(f"execution observation missing field: {field}")
    if not observation.get("attempted_action"):
        diagnostics.append("execution observation requires an attempted action")
    for field in ("affected_targets", "evidence_references", "failures", "blockers"):
        if field in observation and not isinstance(observation[field], list):
            diagnostics.append(f"execution observation field must be a list: {field}")

    return ("blocked" if diagnostics else "handoff"), diagnostics


def assess_reconciliation_scenario(scenario: dict[str, Any]) -> tuple[str, list[str]]:
    """Classify criterion evidence and return diagnostics for an advisory assessment."""
    diagnostics: list[str] = []
    criteria = scenario.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return "BLOCKED", ["reconciliation requires at least one acceptance criterion"]

    supported = 0
    unresolved = 0
    for criterion in criteria:
        if not isinstance(criterion, dict) or not criterion.get("id"):
            diagnostics.append("criterion requires a stable id")
            unresolved += 1
            continue
        evidence = criterion.get("evidence")
        if not isinstance(evidence, dict):
            diagnostics.append(f"criterion {criterion['id']} requires attributable evidence")
            unresolved += 1
            continue
        supporting = evidence.get("supporting")
        contradicting = evidence.get("contradicting")
        missing = evidence.get("missing")
        if (
            not isinstance(supporting, list)
            or not isinstance(contradicting, list)
            or not isinstance(missing, bool)
        ):
            diagnostics.append(
                f"criterion {criterion['id']} evidence must classify supporting, contradicting, and missing"
            )
            unresolved += 1
            continue
        if missing and (supporting or contradicting):
            diagnostics.append(f"criterion {criterion['id']} cannot be missing and attributable")
            unresolved += 1
            continue
        if not missing and not supporting and not contradicting:
            diagnostics.append(f"criterion {criterion['id']} has no attributable evidence classification")
            unresolved += 1
            continue
        if supporting and not contradicting and not missing:
            supported += 1
        else:
            unresolved += 1

    facts = scenario.get("facts", {})
    if not isinstance(facts, dict):
        facts = {}
        diagnostics.append("reconciliation facts must be an object")
    if facts.get("superseded") is True:
        assessment = "SUPERSEDED"
    elif facts.get("diverged") is True or facts.get("material_unintended_effects") is True:
        assessment = "DIVERGED"
    elif facts.get("needs_replan") is True:
        assessment = "NEEDS_REPLAN"
    elif facts.get("stale") is True:
        assessment = "STALE"
    elif facts.get("blocked") is True:
        assessment = "BLOCKED"
    elif facts.get("attempt_failed") is True:
        assessment = "FAILED"
    elif supported == len(criteria) and unresolved == 0 and not diagnostics:
        assessment = "SUCCESS"
    elif supported > 0:
        assessment = "PARTIAL"
    else:
        assessment = "BLOCKED"

    recommendation = scenario.get("recommendation")
    if not isinstance(recommendation, dict) or not recommendation.get("owner"):
        diagnostics.append("recommendation requires an owner")
    elif recommendation.get("action") != RECONCILIATION_RECOMMENDATIONS[assessment]:
        diagnostics.append(
            f"assessment {assessment} requires bounded recommendation "
            f"{RECONCILIATION_RECOMMENDATIONS[assessment]}"
        )

    return assessment, diagnostics


def evaluate_lifecycle_scenario(scenario: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Evaluate explicit lifecycle snapshots without synthesizing transitions."""
    steps = scenario.get("steps")
    if not isinstance(steps, list) or not steps:
        return [], ["lifecycle scenario requires at least one explicit step"]

    lanes: list[str] = []
    diagnostics: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            diagnostics.append(f"lifecycle step {index} must be an object")
            continue
        routed = route_delivery_scenario(step)
        lanes.append(routed["lane"])
        if routed["blockers"] != step.get("expected_blockers", []):
            diagnostics.append(f"lifecycle step {index} blockers differ from expectation")

        if routed["lane"] == "delivery-execution":
            execution_scenario = step.get("execution_scenario")
            if isinstance(execution_scenario, dict):
                disposition, execution_diagnostics = evaluate_execution_scenario(
                    execution_scenario
                )
                if disposition != step.get("expected_execution_disposition"):
                    diagnostics.append(
                        f"lifecycle step {index} execution disposition was {disposition}"
                    )
                if execution_diagnostics != step.get("expected_execution_diagnostics", []):
                    diagnostics.append(
                        f"lifecycle step {index} execution diagnostics differ from expectation"
                    )

        if routed["lane"] == "delivery-reconciliation":
            reconciliation_scenario = step.get("reconciliation_scenario")
            if isinstance(reconciliation_scenario, dict):
                assessment, reconciliation_diagnostics = assess_reconciliation_scenario(
                    reconciliation_scenario
                )
                if assessment != step.get("expected_assessment"):
                    diagnostics.append(
                        f"lifecycle step {index} reconciliation assessment was {assessment}"
                    )
                if reconciliation_diagnostics != step.get(
                    "expected_reconciliation_diagnostics", []
                ):
                    diagnostics.append(
                        f"lifecycle step {index} reconciliation diagnostics differ from expectation"
                    )

    return lanes, diagnostics


def validate_routing_fixtures() -> list[str]:
    """Validate thin-router decisions and cross-stage lifecycle composition."""
    errors: list[str] = []
    fixture_root = ROOT / "tests" / "fixtures"

    routing_path = fixture_root / ROUTING_FIXTURES[0]
    try:
        routing_scenarios = json.loads(routing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{routing_path.name}: cannot load scenarios: {exc}")
        routing_scenarios = []
    if not isinstance(routing_scenarios, list):
        errors.append(f"{routing_path.name}: fixture root must be a list")
        routing_scenarios = []

    observed_lanes: set[str] = set()
    observed_reconciliation_precedence = False
    observed_owned_blocker = False
    observed_consumer_passthrough = False
    observed_advisory_adapter_unloaded = False
    observed_representation_adapter_loaded = False
    observed_persistence_denied = False
    observed_conversation_claims_blocked = False
    for scenario in routing_scenarios:
        if not isinstance(scenario, dict):
            errors.append(f"{routing_path.name}: every scenario must be an object")
            continue
        name = scenario.get("name", "unnamed scenario")
        actual = route_delivery_scenario(scenario)
        expected = scenario.get("expected")
        observed_lanes.add(actual["lane"])
        if actual != expected:
            errors.append(
                f"{routing_path.name}: {name}: expected {expected}, observed {actual}"
            )
        request = scenario.get("request", {})
        owner_state = scenario.get("owner_state", {})
        evidence = scenario.get("evidence", {})
        operation = scenario.get("operation", {})
        envelope = owner_state.get("execution_envelope", {}) if isinstance(owner_state, dict) else {}
        if (
            actual["lane"] == "delivery-reconciliation"
            and isinstance(envelope, dict)
            and envelope.get("canonical_readiness") is True
            and isinstance(evidence, dict)
            and evidence.get("execution_results") is True
        ):
            observed_reconciliation_precedence = True
        if actual["lane"] == "blocked" and actual["blockers"] and all(
            blocker.get("owner") for blocker in actual["blockers"]
        ):
            observed_owned_blocker = True
        if isinstance(actual["stage_inputs"], dict) and any(
            field in actual["stage_inputs"]
            for field in ("consumer_conventions", "consumer_contract")
        ):
            selected_inputs = {
                "delivery-planning": scenario.get("planning_inputs"),
                "delivery-execution": scenario.get("execution_inputs"),
                "delivery-reconciliation": scenario.get("reconciliation_inputs"),
            }.get(actual["lane"])
            observed_consumer_passthrough = (
                observed_consumer_passthrough or actual["stage_inputs"] is selected_inputs
            )
        adapter = owner_state.get("adapter") if isinstance(owner_state, dict) else None
        operation_kind = operation.get("kind") if isinstance(operation, dict) else None
        if (
            isinstance(adapter, dict)
            and adapter.get("selected") is True
            and operation_kind == "advisory"
            and actual["adapter_loaded"] is None
        ):
            observed_advisory_adapter_unloaded = True
        if (
            operation_kind == "validate-projection"
            and isinstance(adapter, dict)
            and actual["adapter_loaded"] == adapter.get("name")
        ):
            observed_representation_adapter_loaded = True
        if (
            operation_kind == "persist-projection"
            and actual["adapter_loaded"] is None
            and actual["blockers"]
        ):
            observed_persistence_denied = True
        if (
            isinstance(request, dict)
            and request.get("conversation_claims")
            and actual["lane"] == "blocked"
        ):
            observed_conversation_claims_blocked = True

    required_lanes = {
        "direct-answer",
        "delivery-planning",
        "delivery-execution",
        "delivery-reconciliation",
        "blocked",
    }
    if observed_lanes != required_lanes:
        errors.append(
            f"{routing_path.name}: scenarios must cover exactly {sorted(required_lanes)}"
        )
    routing_coverage = {
        "reconciliation precedence over ready execution": observed_reconciliation_precedence,
        "owner-attributed missing-state blocker": observed_owned_blocker,
        "consumer convention or contract pass-through": observed_consumer_passthrough,
        "configured adapter unloaded for advisory work": observed_advisory_adapter_unloaded,
        "selected adapter loaded for a representation operation": observed_representation_adapter_loaded,
        "adapter selection denied as persistence authority": observed_persistence_denied,
        "conversation claims rejected as canonical state": observed_conversation_claims_blocked,
    }
    missing_routing_coverage = [
        description for description, observed in routing_coverage.items() if not observed
    ]
    if missing_routing_coverage:
        errors.append(
            f"{routing_path.name}: missing routing coverage: "
            + ", ".join(missing_routing_coverage)
        )

    lifecycle_path = fixture_root / ROUTING_FIXTURES[1]
    try:
        lifecycle_scenarios = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{lifecycle_path.name}: cannot load scenarios: {exc}")
        lifecycle_scenarios = []
    if not isinstance(lifecycle_scenarios, list):
        errors.append(f"{lifecycle_path.name}: fixture root must be a list")
        lifecycle_scenarios = []

    observed_sequences: set[tuple[str, ...]] = set()
    for scenario in lifecycle_scenarios:
        if not isinstance(scenario, dict):
            errors.append(f"{lifecycle_path.name}: every scenario must be an object")
            continue
        name = scenario.get("name", "unnamed scenario")
        lanes, diagnostics = evaluate_lifecycle_scenario(scenario)
        expected_lanes = scenario.get("expected_lanes")
        expected_diagnostics = scenario.get("expected_diagnostics", [])
        observed_sequences.add(tuple(lanes))
        if lanes != expected_lanes:
            errors.append(
                f"{lifecycle_path.name}: {name}: expected lanes {expected_lanes}, observed {lanes}"
            )
        if diagnostics != expected_diagnostics:
            errors.append(
                f"{lifecycle_path.name}: {name}: expected diagnostics "
                f"{expected_diagnostics}, observed {diagnostics}"
            )

    required_sequences = {
        (
            "delivery-planning",
            "delivery-execution",
            "delivery-reconciliation",
        ),
        (
            "delivery-execution",
            "delivery-reconciliation",
            "delivery-planning",
        ),
    }
    if observed_sequences != required_sequences:
        errors.append(
            f"{lifecycle_path.name}: scenarios must cover continuation and replanning loops"
        )
    return errors


def validate_scenario_fixtures() -> list[str]:
    """Run the public-safe behavioral fixtures as part of package validation."""
    errors: list[str] = []
    fixture_root = ROOT / "tests" / "fixtures"
    execution_dispositions: set[str] = set()
    execution_diagnostics: set[str] = set()
    observed_assessments: set[str] = set()
    observed_failure = False
    observed_blocker = False
    for filename in SCENARIO_FIXTURES:
        path = fixture_root / filename
        if not path.is_file():
            errors.append(f"scenarios: missing tests/fixtures/{filename}")
            continue
        try:
            scenarios = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{filename}: cannot load scenarios: {exc}")
            continue
        if not isinstance(scenarios, list):
            errors.append(f"{filename}: fixture root must be a list")
            continue
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                errors.append(f"{filename}: every scenario must be an object")
                continue
            name = scenario.get("name", "unnamed scenario")
            if filename == "execution_scenarios.json":
                actual, diagnostics = evaluate_execution_scenario(scenario)
                expected = scenario.get("expected_disposition")
                execution_dispositions.add(actual)
                execution_diagnostics.update(diagnostics)
                observation = scenario.get("observation")
                if isinstance(observation, dict):
                    observed_failure = observed_failure or bool(observation.get("failures"))
                    observed_blocker = observed_blocker or bool(observation.get("blockers"))
            else:
                actual, diagnostics = assess_reconciliation_scenario(scenario)
                expected = scenario.get("expected_assessment")
                observed_assessments.add(actual)
            if actual != expected:
                errors.append(f"{filename}: {name}: expected {expected}, observed {actual}")
            expected_diagnostics = scenario.get("expected_diagnostics", [])
            if diagnostics != expected_diagnostics:
                errors.append(
                    f"{filename}: {name}: expected diagnostics {expected_diagnostics}, "
                    f"observed {diagnostics}"
                )

    if execution_dispositions != {"execute", "blocked", "reconcile", "handoff"}:
        errors.append(
            "execution_scenarios.json: scenarios must cover execute, blocked, reconcile, and handoff"
        )
    required_execution_diagnostics = {
        *(f"missing required envelope input: {field}" for field in EXECUTION_ENVELOPE_FIELDS),
        "effect lacks explicit authority: publish release",
        "execution prerequisites are contradictory",
        "immutable execution scope is stale",
    }
    missing_diagnostics = sorted(required_execution_diagnostics - execution_diagnostics)
    if missing_diagnostics:
        errors.append(
            "execution_scenarios.json: missing envelope coverage: "
            + ", ".join(missing_diagnostics)
        )
    if not observed_failure or not observed_blocker:
        errors.append(
            "execution_scenarios.json: scenarios must capture representative failures and blockers"
        )
    if observed_assessments != set(ASSESSMENTS):
        errors.append(
            "reconciliation_scenarios.json: scenarios must cover exactly the closed assessment vocabulary"
        )
    errors.extend(validate_routing_fixtures())
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    skill_root = ROOT / "skills"
    actual = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
    if actual != sorted(SKILLS):
        errors.append(f"skills: expected {sorted(SKILLS)}, found {actual}")

    texts: dict[str, str] = {}
    for name in SKILLS:
        package = skill_root / name
        entrypoint = package / "SKILL.md"
        if not entrypoint.is_file():
            errors.append(f"{name}: missing SKILL.md")
            continue
        text = entrypoint.read_text(encoding="utf-8")
        texts[name] = text
        fields = frontmatter(text)
        if fields.get("name") != name:
            errors.append(f"{name}: frontmatter name must equal directory name")
        description = fields.get("description", "")
        if not description or len(description) > 1024:
            errors.append(f"{name}: description must contain 1-1024 characters")
        for source in package.rglob("*.md"):
            source_text = source.read_text(encoding="utf-8")
            for target in LINK_PATTERN.findall(source_text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (source.parent / target.split("#", 1)[0]).resolve()
                relative_source = source.relative_to(package)
                if not resolved.is_file():
                    errors.append(f"{name}: {relative_source} has unresolved link {target}")
                elif package.resolve() not in resolved.parents:
                    errors.append(
                        f"{name}: {relative_source} link escapes its installable directory: {target}"
                    )

    planning_package = skill_root / "delivery-planning"
    for relative in PLANNING_REFERENCES:
        if not (planning_package / relative).is_file():
            errors.append(f"delivery-planning: missing {relative}")
    for relative in PLANNING_COMPATIBILITY_FILES:
        if not (planning_package / relative).is_file():
            errors.append(f"delivery-planning: missing {relative}")

    router = texts.get("deliver-product", "")
    for lane in CORE_SKILLS[1:]:
        if lane not in router:
            errors.append(f"deliver-product: missing route to {lane}")

    execution = texts.get("delivery-execution", "").lower()
    if "canonical approval and readiness" not in execution or "immutable execution scope" not in execution:
        errors.append("delivery-execution: missing explicit readiness or immutable-scope boundary")

    reconciliation_path = (
        skill_root / "delivery-reconciliation" / "references" / "assessment-contract.md"
    )
    if reconciliation_path.is_file():
        reconciliation = reconciliation_path.read_text(encoding="utf-8")
        for assessment in ASSESSMENTS:
            if f"`{assessment}`" not in reconciliation:
                errors.append(f"delivery-reconciliation: missing {assessment} assessment")
        if "execution success alone is insufficient" not in reconciliation.lower():
            errors.append("delivery-reconciliation: success must require verification evidence")
    else:
        errors.append("delivery-reconciliation: missing assessment contract")

    errors.extend(validate_scenario_fixtures())
    errors.extend(validate_agent_view_policy())

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(SKILLS)} Delivery skill packages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
