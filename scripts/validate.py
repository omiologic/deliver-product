#!/usr/bin/env python3
"""Validate the Delivery skill workspace without third-party dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path


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
