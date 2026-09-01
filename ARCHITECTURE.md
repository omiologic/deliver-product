# Deliver Product Architecture

## Purpose

Deliver Product provides procedural intelligence for planning, executing, and reconciling bounded work. It connects user intent, applicable governance, owner-produced runtime state, operational effects, and verification evidence without becoming a canonical state owner.

The package is intentionally a family of skills rather than one broad skill. Planning, Execution, and Reconciliation require different inputs, reasoning, and outputs. The `deliver-product` skill remains a thin stage router over those narrower capabilities. `delivery-spine` is a specialized cross-stage evidence gate for registered user journeys; it is not a fifth lifecycle stage or a source of deployment authority.

## System position

```text
                         requested outcome
                                  │
                 governed context │ owner-produced state
                                  ▼
                    ┌────────────────────────┐
                    │        Delivery        │
                    │                        │
                    │ Planning               │
                    │      ▼                 │
                    │ Execution              │
                    │      ▼                 │
                    │ Reconciliation ───┐    │
                    │      ▲            │    │
                    │      └── replan ──┘    │
                    └───────────┬────────────┘
                                │ owner-controlled operations
                                ▼
             ┌─────────────────────────────────────────┐
             │ Consumer runtime and operational tools  │
             │ own state, effects, and evidence        │
             └─────────────────────────────────────────┘
```

Dependency direction is one-way:

```text
delivery-planning ──────► context-governance
delivery-execution ─────► context-governance when applicable
delivery-reconciliation ► context-governance when applicable

context-governance ──X──► delivery
```

Context Governance remains independently usable. Delivery must still operate when Context Governance is absent by relying on explicit user and repository constraints and by stating the missing governed context.

Delivery composes its procedure in this order:

```text
explicit request + owner-produced state
                  │
                  ▼
          thin stage router
                  │
                  ▼
           tiny stage skill
                  │
                  ▼
     consumer conventions/contracts
                  │
                  ▼
 optional consumer-relative adapter
```

The skills own thin, reusable guardrails. Consumer conventions and contracts customize terminology, planning-type preferences, decomposition rules, and local projections without replacing those guardrails. An adapter is loaded only when the selected work requires its representation or effect.

## Repository and skill boundaries

The repository boundary and the skill boundary serve different purposes:

| Boundary | Design reason |
| --- | --- |
| One `deliver-product` repository | Cross-stage contracts, compatibility, releases, and lifecycle tests change atomically. |
| Four core stage skills plus `delivery-spine` | Each stage loads bounded context; the spine loads only for applicable cross-boundary journey evidence. |

The repository root is not itself a skill. Each package entrypoint belongs at `skills/<skill-name>/SKILL.md` and must be independently discoverable and installable.

`delivery-planning` may grow a library of planning types under package-local references. Its entrypoint and shared planning contract remain small; it loads only the selected planning type. New planning types refine proposal shape and reasoning without duplicating authority, evidence, persistence, or ownership rules.

## Ownership model

| Layer | Owns | Does not own |
| --- | --- | --- |
| Context Governance | Durable Decisions, Conventions, Constraints, Git Governance, Version Governance, and bounded governance-context resolution | Delivery lifecycle or consumer runtime state |
| Delivery Planning | Outcome interpretation, planning-type selection, proposal preparation, decomposition, plan guidance, WorkItem definitions, dependencies, and replanning procedure | Consumer methodology policy, approval, canonical Plan state, or accepted governance records |
| Delivery Execution | Resolution and performance of exact ready work, bounded attempts, results, and evidence capture | Readiness inference, canonical Execution records, or WorkItem transitions |
| Delivery Reconciliation | Criteria-versus-evidence assessment, divergence detection, and next-action recommendation | Canonical completion, acceptance, Plan state, or WorkItem state |
| Delivery Spine | Registered journey shaping, integration preflight, impact selection, evidence-level validation, and deterministic gates | Roadmap direction, lifecycle transitions, deployment authority, or broad audit |
| Consumer runtime | Canonical Plan, WorkItem, Execution, Context, Inbox, and Capability records and transitions | General procedural guidance encoded by the skills |
| Operations and tools | Authorized Git, deployment, CI, filesystem, browser, provider, and other effects | Delivery approval or expanded authority |

For the first consumer, `agentic-wx` retains its existing domain ownership:

- Planning owns Plan structure, validation, readiness, approval, lifecycle, revision, cancellation, and supersession.
- Work Items owns WorkItem readiness, dependencies, attempts, results, verification, and Execution creation and lifecycle.
- Context owns bounded execution-scoped context and provenance.
- Inbox owns intake lifecycle and exact Plan references.
- Capability Management owns eligibility and collision resolution.

These are consumer contracts, not state machines to reproduce inside this repository.

## Routing contract

The `deliver-product` orchestrator selects a lane only from explicit intent and owner-produced state or evidence:

| Observed condition | Route |
| --- | --- |
| The request needs no durable delivery work | Direct answer or research lane outside the Delivery lifecycle |
| Work is not yet defined | `delivery-planning` |
| Exact approved and canonically ready work exists | `delivery-execution` |
| An execution produced results, evidence, or changes | `delivery-reconciliation` |
| Reconciliation finds divergence or invalid assumptions | `delivery-planning` for bounded replanning |

The router must not infer Plan approval, WorkItem readiness, execution success, verification, completion, acceptance, or deployment success from conversation alone.

## Skill contracts

### `deliver-product`

**Inputs:** user intent, available owner-produced state, and evidence references.

**Behavior:** determine whether Delivery applies, select one narrow stage, and preserve the direct-answer lane.

**Outputs:** the selected lane and the exact inputs handed to it, or a bounded statement of what owner-produced state is missing.

**Boundary:** contains minimal domain policy and does not recreate child-skill behavior.

### `delivery-planning`

**Inputs:** requested outcome, applicable governed context, current-state evidence, constraints, owner-produced planning state, and applicable consumer conventions or planning contracts.

**Behavior:** select one relative planning type from explicit intent, owner-produced state, consumer conventions, or clear outcome evidence; otherwise use the thin bounded-outcome default. Prepare bounded alternatives and assumptions, decompose selected work, define success criteria and dependencies, and represent blockers or replanning needs.

**Outputs:** a PlanningProposal, Plan draft guidance, WorkItem definitions, or repository-local planning artifacts supported by the consumer.

**Boundary:** planning types may refine procedure but cannot weaken the shared guardrails. Planning may identify a governance question but must route its acceptance to Context Governance or another owner. It does not approve plans, create canonical runtime state, or require a repository-local planning layout.

### `delivery-execution`

**Inputs:** one exact owner-selected WorkItem, canonical readiness, immutable Execution scope, applicable context, assigned capabilities, and authority.

**Behavior:** invoke the appropriate operation, skill, or tool; perform only authorized effects; and capture attempts, results, evidence, failures, and blockers.

**Outputs:** bounded execution observations suitable for the owning runtime and Reconciliation.

**Boundary:** successful tool or command completion is an execution result, not evidence by itself that acceptance criteria are satisfied.

### `delivery-reconciliation`

**Inputs:** Plan and WorkItem expectations, Execution snapshot, attempts, results, verification evidence, observed changes, and relevant external evidence.

**Behavior:** compare intended criteria with observed reality, detect unintended effects or drift, and recommend the next owner-controlled action.

**Outputs:** one assessment with evidence and a bounded recommendation. Initial assessment vocabulary is `SUCCESS`, `PARTIAL`, `FAILED`, `BLOCKED`, `STALE`, `DIVERGED`, `SUPERSEDED`, or `NEEDS_REPLAN`.

**Boundary:** assessments are not competing canonical statuses. Only the owning runtime or person may accept them and perform a state transition.

### `delivery-spine`

**Inputs:** one applicable registered journey, its bounded projection records, work-item delivery fields, changed paths, and retained integration or deployment evidence.

**Behavior:** shape the journey claim, retrieve only records required by the selected operation, preflight prerequisites, select impacted journey suites from compact registry metadata, and validate evidence-level or archive gates. Deterministic full validation may scan the complete projection while returning compact diagnostics.

**Outputs:** deterministic diagnostics, impacted journeys, evidence-level observations, and gate results.

**Boundary:** a gate result is evidence for an owner-controlled decision. It does not deploy, release, archive work, or replace Planning, Execution, or Reconciliation.

The package was initially imported unchanged from its system-local source. Its former Context-Governance-specific lifecycle wording was reconciled through the issue #5 compatibility change: start and archive now return read-only evidence for transitions controlled by the consumer runtime or responsible person.

## Evidence and completion

```text
attempt completed
      │
      ▼
result recorded ──X──► WorkItem complete
      │
      ▼
criteria compared with verification evidence
      │
      ├── satisfied ──► request owner-controlled completion or next work
      └── not satisfied ──► partial, blocked, divergent, or replan route
```

Reconciliation must detect more than command failure. It covers missing verification, partial implementation, stale assumptions, repository or environment drift, external dependency changes, unintended effects, and mismatch with user intent.

## Local artifacts and runtime state

Delivery requires no repository-local configuration or planning files for advisory work. The skills supply safe defaults; consumers should place methodology preferences, planning-type rules, and adapter choices in their own `CONVENTIONS.md` or equivalent owner-produced contract.

Persistence is a separate, authorized operation. When requested, Delivery uses the consumer-selected adapter and resolves configured paths relative to the consumer root. A path must not be invented, interpreted relative to the skill package, or allowed to escape the consumer boundary.

Repository-local `_notes/plans/**` files are one supported compatibility projection. They are planning artifacts and human or agent working projections, not canonical runtime state or a required layout. The extraction must preserve current `project_key` and legacy plan compatibility before attempting broader identity changes.

`_notes/DELIVERY.md` is not a required target. A consumer may adopt an optional structured Delivery configuration only when its conventions cannot express a machine-readable need. Its presence never creates authority or canonical state.

Delivery Spine projections remain separate because they retain optional operational journey evidence rather than general Delivery configuration. The schema-v2 sharded adapter separates stable registration, open claims, compact baselines, and archived claims so completed history leaves routine context while journeys remain available for impact selection. `_notes/delivery-spine` is its thin default root. The schema-v1 `_notes/delivery-spine.json` monolith remains readable through the schema-v2 support window. Both are consumer-relative adapter defaults, not universal layouts, and consumers that do not use Delivery Spine need no projection.

After bounded selection and operation-specific field projection, Delivery Spine may render an ephemeral agent-input view. Compact JSON is the stable default and fallback; alternate encodings require versioned benchmark evidence for lossless reconstruction, task-answer parity, and material net token savings. Agent views never redefine persisted JSON, stored property names, schemas, agent-generated structured output, or owner-controlled lifecycle state.

Target, WorkItem, and preflight retrieval load the compact registry and current-claim index plus only the exact claim and baseline. Impact scans registry metadata only. History requires an exact journey plus a claim, WorkItem dependency, or evidence reference; broad archived evidence requires an explicit audit request. Migration is a separate authorized operation that preserves its source, refuses an existing destination, and never performs a lifecycle transition.

## Event-compatible vocabulary

Delivery should use event-friendly language without acting as an event store. Candidate integration terms include:

```text
delivery.requested       planning.proposed       planning.selected
plan.ready               plan.approved           workitem.ready
execution.created        execution.started       execution.resulted
reconciliation.started   reconciliation.verified reconciliation.blocked
reconciliation.diverged  workitem.completed      plan.completed
replan.requested
```

These names remain conceptual until an owning runtime adopts an explicit event contract.

## Migration constraints

1. Establish and test the four contracts before moving behavior.
2. Port planning behavior and fixtures behind the thin planning contract without running two authoritative validators.
3. Preserve legacy `_notes/plans/**` inputs as an optional compatibility adapter until the Delivery validator reads them safely.
4. Keep temporary Context Governance compatibility as delegation, never duplicated policy.
5. Remove the compatibility route only after consumer migration and one supported migration window.

The first migration target is `agentic-wx`. Its Planning, Work Items, Context, Inbox, and Capability Management domains must remain authoritative throughout the transition.

## Validation architecture

The completed repository should expose one package-level validation entrypoint covering:

| Layer | Required proof |
| --- | --- |
| Package structure | All four skills have valid metadata, bounded routing, and resolvable links. |
| Planning-type routing | Explicit selection, owner-produced type, consumer convention, clear inference, material ambiguity, and bounded default cases preserve the documented precedence. |
| Planning compatibility | Representative legacy Context Governance plans retain equivalent validation behavior. |
| Stage contracts | Missing governance, conflicting governance, blocked constraints, immutable execution scope, and authority boundaries are handled explicitly. |
| Reconciliation | Every assessment class is tested, and execution success without verification cannot complete work. |
| Lifecycle integration | Successful continuation and reconciliation-driven replanning both work against current consumer contracts. |

Validation proves package consistency and observable behavior. It never grants approval, mutation authority, publication authority, or release authority.

## Non-goals for the first release

The first release will not implement automatic model routing, arbitrary subagent spawning, operational Git or deployment effects, provider-specific adapters, or skill-local replacements for consumer runtime domains. Scheduling, portfolio management, knowledge consolidation, and context ranking also remain outside this repository.
