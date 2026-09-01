---
name: delivery-planning
description: Turn a requested outcome into bounded delivery proposals, plan guidance, and WorkItem definitions using applicable constraints and current-state evidence. Use before work is canonically approved and ready, or when reconciliation requires replanning.
---

# Delivery Planning

Prepare bounded work for an owner to review and adopt.

## Gather inputs

Use the requested outcome, current-state evidence, explicit constraints, applicable governed context when available, and the consumer's planning contract. State material assumptions and missing context. Context Governance is optional; when absent, rely on explicit user and repository constraints and disclose that governed context was unavailable.

## Prepare the proposal

Read [references/planning-contract.md](references/planning-contract.md) before defining durable work.

Offer alternatives only when they change a meaningful tradeoff. For the selected direction, define bounded scope, acceptance criteria, dependencies, risks, verification needs, and WorkItems small enough for exact execution. Preserve stable consumer identifiers and legacy `_notes/plans/**` compatibility when editing existing artifacts.

When replanning, retain still-valid evidence and change only the invalidated assumptions or affected scope.

## Preserve ownership

Produce advisory proposals, Plan draft guidance, WorkItem definitions, or supported repository-local planning artifacts. Do not approve a Plan, claim canonical readiness, create runtime records, or accept a durable Decision, Convention, or Constraint. Route governance acceptance to its owner.

Repository-local planning files are working projections, not canonical runtime state. Writing them requires the same filesystem authority as any other repository mutation.

