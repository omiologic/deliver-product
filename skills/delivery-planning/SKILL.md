---
name: delivery-planning
description: Turn a requested outcome into bounded delivery proposals, plan guidance, and WorkItem definitions using applicable constraints and current-state evidence. Use before work is canonically approved and ready, or when reconciliation requires replanning.
---

# Delivery Planning

Prepare bounded work for an owner to review and adopt.

## Gather inputs

Use the requested outcome, current-state evidence, explicit constraints, owner-produced planning state, applicable governed context when available, and the consumer's conventions or planning contract. State material assumptions and missing context. Context Governance is optional; when absent, rely on explicit user and repository constraints and disclose that governed context was unavailable.

## Select the planning type

Read [planning-type routing](references/planning-type-routing.md). Use an explicit user type first, then an owner-produced type, then an applicable consumer convention. Otherwise select the type clearly supported by the outcome and evidence. Ask only when ambiguity would materially change the commitment, decomposition, authority, or persistence; use the bounded-outcome default when no specialization is needed. Load only the selected package type; a consumer-owned type remains external to this package.

## Prepare the proposal

Read [references/planning-contract.md](references/planning-contract.md) before defining durable work.

Offer alternatives only when they change a meaningful tradeoff. For the selected direction, define bounded scope, acceptance criteria, dependencies, risks, verification needs, and WorkItems small enough for exact execution. A planning type may refine this procedure but cannot weaken the shared contract.

When replanning, retain still-valid evidence and change only the invalidated assumptions or affected scope.

## Preserve ownership

Produce advisory proposals, Plan draft guidance, WorkItem definitions, or supported repository-local planning artifacts. Do not approve a Plan, claim canonical readiness, create runtime records, or accept a durable Decision, Convention, or Constraint. Route governance acceptance to its owner.

Advisory Planning requires no repository-local configuration or planning tree. When the user requests persistence or supplies a custom planning contract, read [consumer conventions and adapters](references/consumer-conventions.md). Load the [repository-local work-item adapter](references/adapters/repository-local-work-items.md) only when the consumer selects that compatibility projection. Repository-local planning files are optional working projections, not canonical runtime state. Writing them requires the same filesystem authority as any other repository mutation.
