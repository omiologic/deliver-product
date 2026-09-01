---
name: delivery-reconciliation
description: Compare delivery expectations with execution results and verification evidence, classify the outcome, and recommend the next owner-controlled action. Use after an execution produces results, changes, failures, or evidence.
---

# Delivery Reconciliation

Determine what the evidence supports without changing canonical state.

## Gather the comparison set

Use the Plan and WorkItem expectations, immutable execution snapshot, attempts, results, observed changes, verification evidence, and relevant external evidence. Missing verification is meaningful; do not replace it with execution success.

## Assess

Read [references/assessment-contract.md](references/assessment-contract.md). Compare every applicable acceptance criterion with attributable evidence, note unintended effects and drift, and select one assessment: `SUCCESS`, `PARTIAL`, `FAILED`, `BLOCKED`, `STALE`, `DIVERGED`, `SUPERSEDED`, or `NEEDS_REPLAN`.

Choose the narrowest assessment supported by evidence. State uncertainty and conflicting evidence instead of resolving it by assumption.

## Recommend, do not transition

Return one assessment, criterion-level evidence, material gaps or unintended effects, and one bounded next-action recommendation. Only the owning runtime or person may accept the assessment and perform a WorkItem or Plan transition.

For invalid assumptions or material divergence, recommend `delivery-planning`. Do not silently retry execution or broaden its scope.

