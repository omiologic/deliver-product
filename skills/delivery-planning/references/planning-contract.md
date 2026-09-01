# Planning contract

This contract owns the guardrails shared by every planning type. A planning type may add relevant proposal fields, decomposition guidance, or verification considerations, but it must not weaken ownership, authority, evidence, or persistence boundaries.

## Required proposal content

A proposal should make these fields explicit when they apply:

- requested outcome and evidence of the current state;
- included and excluded scope;
- applicable constraints and governed context provenance;
- assumptions, unknowns, risks, and meaningful alternatives;
- acceptance criteria expressed as observable outcomes;
- verification needed to assess each criterion;
- ordered WorkItems with stable identifiers and dependencies; and
- the owner action required to select, approve, or persist the work.

Do not invent detail merely to fill a field. Mark a consequential unknown and identify its owner.

## WorkItem quality

Each WorkItem must represent one bounded result with explicit acceptance criteria. Dependencies describe real ordering or prerequisite state, not a preferred narrative sequence. Execution scope must be precise enough that the execution stage does not need to reinterpret intent or add authority.

## Replanning

Replanning begins from the reconciliation evidence. Identify the invalidated assumption, affected criteria, and smallest necessary scope change. Do not silently retry the same action, broaden scope, discard still-valid work, or replace canonical state.

## Persistence boundary

Planning is advisory by default and requires no local files. Persist only when the user explicitly requests it or an owner-produced workflow requires it and the necessary filesystem authority exists. Use the consumer-selected adapter and resolve its paths relative to the consumer root. A stored artifact remains a projection and does not become canonical runtime state.
