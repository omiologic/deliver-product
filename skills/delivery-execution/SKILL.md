---
name: delivery-execution
description: Carry out one exact owner-selected, approved, and canonically ready WorkItem within immutable scope and granted authority while capturing results and evidence. Use only when execution prerequisites are explicitly supplied.
---

# Delivery Execution

Perform one bounded execution without inferring readiness or completion.

## Require an execution envelope

Before acting, read [references/execution-contract.md](references/execution-contract.md). Require one exact owner-selected WorkItem, canonical approval and readiness, immutable execution scope, applicable context, assigned capabilities, and explicit authority for the intended effects.

If a required input is missing or contradictory, report the blocker to its owner. Do not manufacture readiness, reinterpret the WorkItem, or widen scope.

## Execute within scope

Use the appropriate operation, skill, or tool for the authorized effect. Preserve user changes and local repository instructions. Stop when the WorkItem's bounded action is performed, cannot safely continue, or would require new authority or scope.

Capture attempts, relevant results, changed targets, failures, blockers, and evidence references. Keep observations factual and distinguish a tool result from evidence that an acceptance criterion is satisfied.

## Hand off

Return bounded execution observations to the owning runtime and `delivery-reconciliation`. Do not mark a WorkItem complete, accept the result, mutate canonical lifecycle state, or claim that command success proves the intended outcome.

