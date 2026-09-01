# Deliver Product

Deliver Product is the repository for a coordinated family of independently installable delivery skills:

| Skill                     | Responsibility                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------- |
| `deliver-product`         | Route a request to the correct delivery stage using explicit state and evidence.       |
| `delivery-planning`       | Turn a requested outcome into bounded proposals, plans, and work-item definitions.     |
| `delivery-execution`      | Carry out exact approved and ready work within its authority and immutable scope.      |
| `delivery-reconciliation` | Compare intended criteria with observed results and determine what should happen next. |
| `delivery-spine`          | Gate cross-boundary delivery claims against one user journey and integration evidence. |

The four core skills live in one repository because they form one lifecycle, share cross-stage contracts, and need atomic compatibility and integration testing. `delivery-spine` is a specialized cross-stage evidence gate rather than another lifecycle stage. All remain separate skills so an agent can load only the procedural context needed for the current request.

## Ecosystem installation

Each installable package begins at its own repository directory:

| Package | Source directory |
| --- | --- |
| `deliver-product` | `skills/deliver-product/` |
| `delivery-planning` | `skills/delivery-planning/` |
| `delivery-execution` | `skills/delivery-execution/` |
| `delivery-reconciliation` | `skills/delivery-reconciliation/` |
| `delivery-spine` | `skills/delivery-spine/` |

Install the five directories side by side through the consumer runtime's supported Skill installation mechanism for the expected Delivery ecosystem behavior. Preserve each package directory, including its `SKILL.md` and linked resources; the repository root is not an installable Skill.

The packages remain independently installable so a consumer can load or invoke only the procedural context needed for a bounded task. However, a complete installation ensures that `deliver-product` can route across the full lifecycle, stage handoffs resolve consistently, reconciliation can return work to planning, and applicable cross-boundary delivery claims can use the Delivery Spine gates.

Context Governance is a complementary but optional installation. When present, Delivery consumes its bounded governed context. When absent, Delivery relies on explicit user and repository constraints and reports that governed context was unavailable.

The skills own thin default guardrails and use the consumer's conventions and contracts for planning preferences, terminology, and local adapters. Advisory Delivery requires no `_notes/DELIVERY.md` or `_notes/plans/**` tree. When persistence is explicitly requested, configured paths are resolved relative to the consumer, and repository-local records remain projections rather than canonical runtime state.

Delivery Planning is designed to scale through selectively loaded planning-type references. Explicit user choice, owner-produced planning state, and consumer conventions take precedence; otherwise a clearly applicable type may be selected from the outcome, with a bounded-outcome fallback when no specialization is needed.

Validate the complete source workspace with `python3 scripts/validate.py`. Validate an independently installed package with the installed Skill validator against that package directory. The repository-local planning validator is separate and runs only after selecting that adapter: `python3 <delivery-planning-root>/scripts/validate_plans.py <consumer-root>`.

## Status

The repository contains the first contract scaffold for all four core skills and an unchanged import of `delivery-spine` from its original system-local package. Delivery Planning provides thin planning-type routing, selectively loaded feature, sprint, research, and coordination procedures, and an optional consumer-relative repository-local adapter with dependency-free validation and legacy `_notes/plans/**` defaults. `scripts/validate.py` verifies package metadata, package-local links, planning compatibility resources, core routing coverage, and public-safe behavioral scenarios for the complete Execution and Reconciliation contracts. Broader consumer integration, installation tooling, and migration from Context Governance remain future work.

The imported `delivery-spine` contract still reflects its original consumer's current Context Governance ownership language. That compatibility gap is intentionally recorded rather than rewritten during the byte-for-byte import; it must be reconciled before the package is presented as fully aligned with this repository's target ownership model.

The extraction was initiated by Context Governance work item [`ctxgov-00003`](https://github.com/omiologic/context-governance/blob/main/_notes/plans/backlog/ctxgov-00003.extract-delivery-skill-family.md). That work separates delivery-oriented procedure from durable governance concerns.

## Architectural invariant

> Governance constrains Delivery. Delivery coordinates work. Runtime domains own state. Evidence closes the loop.

Delivery may consume applicable governed context, but it does not own durable Decisions, Conventions, or Constraints. It may call owner-controlled runtime operations, but it does not infer or duplicate canonical Plan, WorkItem, Execution, Context, Inbox, or Capability state.

## Lifecycle

```text
requested outcome
      │
      ▼
   Planning
      │ proposed and owner-approved work
      ▼
   Execution
      │ attempts, results, and evidence
      ▼
 Reconciliation ── divergence or invalidated assumptions ──► Planning
      │ verified criteria
      ▼
owner-controlled next work or completion transition
```

A finished or technically successful execution never implies that a WorkItem is complete. Reconciliation must compare the intended acceptance criteria with verification evidence, and the owning runtime decides any canonical state transition.

## Boundaries

| Concern                                                         | Authority                                                      |
| --------------------------------------------------------------- | -------------------------------------------------------------- |
| Durable rules, decisions, conventions, and constraints          | Context Governance or another governance owner                 |
| Delivery-stage procedure and routing                            | The applicable Delivery skill                                  |
| Plan, WorkItem, Execution, Context, Inbox, and Capability state | The consumer runtime that owns each domain                     |
| Git, deployment, CI, browser, filesystem, and provider effects  | Dedicated operations and tools acting under granted authority  |
| Completion and acceptance                                       | The owning runtime or person, based on reconciliation evidence |

Delivery instructions never create authority to mutate a repository, runtime, or external system.

## Intended repository structure

```text
deliver-product/
├── README.md
├── ARCHITECTURE.md
├── AGENTS.md
├── CONVENTIONS.md
├── scripts/
├── tests/
└── skills/
    ├── deliver-product/
    │   └── SKILL.md
    ├── delivery-planning/
    │   ├── SKILL.md
    │   └── references/
    ├── delivery-execution/
    │   ├── SKILL.md
    │   └── references/
    ├── delivery-reconciliation/
    │   ├── SKILL.md
    │   └── references/
    └── delivery-spine/
        ├── SKILL.md
        ├── agents/
        ├── references/
        ├── scripts/
        └── tests/
```

Each current package contains an entrypoint and its working contract reference. Avoid empty scaffolding and duplicate implementations during extraction.

## Validation

From the repository root, run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/delivery-spine/tests -v
```

## Initial delivery sequence

1. Define the four skill contracts and architecture tests.
2. Extract planning behavior from Context Governance behind the thin planning contract while preserving optional local-projection compatibility.
3. Narrow Context Governance to durable governance and bounded context resolution.
4. Add Execution and Reconciliation, then build the thin `deliver-product` orchestrator.
5. Migrate the first consumer and remove the temporary planning compatibility route after its supported window.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for ownership, routing, contracts, migration constraints, and validation expectations.
