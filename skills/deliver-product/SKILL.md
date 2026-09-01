---
name: deliver-product
description: Route delivery requests among planning, execution, reconciliation, or a direct-answer lane using explicit owner-produced state and evidence. Use for end-to-end delivery coordination; use a narrower Delivery skill when the stage is already known.
---

# Deliver Product

Coordinate one delivery stage without becoming a state owner.

## Route the request

Inspect explicit user intent, owner-produced state, and available evidence. Then select exactly one lane:

- Use the direct-answer or research lane when no durable delivery work is needed.
- Use `delivery-planning` when the outcome is not yet represented as bounded work.
- Use `delivery-execution` only when an owner has selected one exact WorkItem and supplied canonical approval, readiness, immutable scope, and authority.
- Use `delivery-reconciliation` when an execution has produced results, changes, or verification evidence that must be compared with expectations.
- Return to `delivery-planning` when reconciliation identifies invalid assumptions or a bounded need to replan.

Read [references/routing-contract.md](references/routing-contract.md) when multiple lanes appear plausible or required state is missing.

## Preserve boundaries

Do not infer approval, readiness, execution success, verification, completion, acceptance, or deployment success from conversation alone. Ask the responsible owner for missing canonical state.

Hand the selected stage only the inputs relevant to that stage. Do not reproduce child-skill procedure here. Skill selection does not authorize mutations or external effects.

## Report

State the selected lane and the explicit inputs passed to it. If routing is blocked, identify the missing owner-produced state and which owner must supply it.

