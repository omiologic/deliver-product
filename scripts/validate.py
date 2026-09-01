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


def validate() -> list[str]:
    errors: list[str] = []
    skill_root = ROOT / "skills"
    actual = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
    if actual != sorted(SKILLS):
        errors.append(f"skills: expected {sorted(SKILLS)}, found {actual}")

    texts: dict[str, str] = {}
    for name in SKILLS:
        entrypoint = skill_root / name / "SKILL.md"
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
        for target in LINK_PATTERN.findall(text):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (entrypoint.parent / target.split("#", 1)[0]).resolve()
            if not resolved.is_file():
                errors.append(f"{name}: unresolved link {target}")
            elif entrypoint.parent.resolve() not in resolved.parents:
                errors.append(f"{name}: package link escapes its installable directory: {target}")

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
