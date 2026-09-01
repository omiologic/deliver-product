---
name: delivery-spine
description: Shape, preflight, and validate repository delivery slices from one primary user journey through real integration evidence. Use for cross-boundary integration, release, promotion, or changes to registered shell, authentication, routing, or configuration paths; not for roadmap direction, ordinary component work, standalone testing, or deployment authorization.
---

# Delivery Spine

Keep product delivery centered on one observable journey without turning source work into release bureaucracy.

## Route the request

Choose the smallest applicable operation:

- **Shape** when planning applicable work: name one primary journey, its integration consumer, target evidence level, real boundaries, and prerequisites.
- **Preflight** before starting integrated or staging work: verify the journey manifest, prerequisites, exact environment inputs, and staging work-in-progress slot.
- **Impact** after cross-cutting source changes: map changed paths to registered journeys and select only the affected real-journey suites.
- **Complete** before a successful archive claim: distinguish source, integrated, and staging evidence and run the deterministic archive gate.
- **Resolve blocker** when a shared-environment preflight, deployment, receipt,
  account identity, required configuration, or real-journey check fails. Trace
  the first missing producer to an exact work item, record the safe solution,
  human action, and exit evidence, then stop retries until that path changes.

Read [delivery contract](references/delivery-contract.md) for shaping or completion. Read [manifest contract](references/manifest-contract.md) when creating, selecting, or changing a journey manifest.

Before a credentialed, destructive, or release-significant journey against a shared environment, read [deployment freshness](references/deployment-freshness.md). Require one retained receipt whose exact environment, deployable unit, endpoint, artifact, applicable public configuration, and source identities match the target under review. Stop on `STALE` or `UNKNOWN` unless the user explicitly requests a stale-target diagnostic; that diagnostic never raises the supported delivery level or proves current source. The check does not apply to source-only, component, contract, or local-loopback evidence and never authorizes deployment.

## Preserve owner boundaries

- Roadmaps own intended outcomes and confidence, not runtime evidence.
- The consumer runtime or responsible person owns Plan and WorkItem lifecycle state and every transition. Delivery Spine supplies read-only evidence for a prospective transition; it never activates, completes, or archives work itself.
- System DevOps owns environment configuration, promotion, rollback, and deployment readiness. Validation never authorizes a deployment.
- System Audit owns broad gap analysis. Delivery Spine reviews only the selected journey and task-affected paths.
- Documentation Maintenance owns the bounded completion-time documentation check.
- Knowledge Consolidation may optionally distill reusable meaning after delivery evidence is complete. It is downstream, non-authorizing work and never a preflight, evidence, or archive gate.

Do not retrieve secrets, invent identities, infer external approval, weaken an owning service's authorization, or treat a manifest as runtime authority.

## Use the evidence ladder

Use exactly these delivery levels:

- `source_complete`: implementation or documentation is internally valid.
- `integrated`: the primary journey crosses its named real local or isolated boundaries.
- `staging_verified`: the primary journey crosses the deployed staging boundaries with retained evidence.

Use `component`, `contract`, `integrated_local`, and `staging_e2e` as evidence classes. A mock, intercepted request, injected token, fixture repository, or synthetic provider may prove a component or contract, but it cannot prove the boundary it replaces.

## Apply only where useful

An applicable work item claims integrated or staging behavior, introduces a deployable consumer path, or changes a registered journey's shell, authentication, routing, or configuration. Add the exact `## Delivery spine` and, when needed, `## Integration preflight` sections defined in the delivery contract.

Ordinary source-only work stays lightweight. If it contributes to a registered journey, name the downstream integration consumer; otherwise do not manufacture a journey.

Consumers that do not use Delivery Spine need no manifest. Require a valid manifest only when an applicable Spine operation needs journey registration, impact mapping, or gate evidence. Consumer conventions may select applicability and the `--manifest-path` argument; Delivery Spine does not parse or own those conventions, and their selection grants no persistence or transition authority.

## Run deterministic gates

From the repository root:

```bash
python3 skills/delivery-spine/scripts/validate_delivery_spine.py .
python3 skills/delivery-spine/scripts/validate_delivery_spine.py . --transition start --work-item <id>
python3 skills/delivery-spine/scripts/validate_delivery_spine.py . --transition archive --work-item <id>
python3 skills/delivery-spine/scripts/validate_delivery_spine.py . --changed-path <path> [--changed-path <path> ...]
python3 skills/delivery-spine/scripts/validate_delivery_spine.py . --manifest-path <consumer-relative-path>
python3 skills/delivery-spine/scripts/deployment_freshness.py check --receipt <path> --environment <name> --deployable-unit <name> --endpoint <https-url> --artifact-path <path> --source-path <path>
```

Run the start gate before the owning runtime or person considers moving applicable work from `ready` to `active`. Run the archive gate after completion evidence is written and before the owner considers moving it from `active` to `archived`. Both gates are read-only: success is evidence for a prospective owner-controlled transition, while failure is evidence against it. Neither result mutates a record or implies activation, archival, completion, deployment, release, or approval.

For a blocker, inspect account/region, stack state, required non-placeholder
configuration, exact receipt identities, and upstream plan ownership. Do not
replace a missing staging producer with a development endpoint or an inferred
ARN. A blocker record is evidence and a handoff, never deployment authority.

## Handoff

Report the journey, target and observed evidence levels, real boundaries exercised or replaced, impacted suites, blockers, and exact gate result. Keep source completion, integration, deployment, and release claims visibly distinct.
