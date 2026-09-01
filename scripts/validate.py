#!/usr/bin/env python3
"""Validate the Delivery skill workspace without third-party dependencies."""

from __future__ import annotations

import json
import re
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
