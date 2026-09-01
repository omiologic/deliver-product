# Journey projection contract

Delivery Spine projections are optional operational views of important user journeys. They are not canonical runtime state, roadmaps, Plans, lifecycle records, deployment manifests, or sources of authorization. Consumers that do not use Delivery Spine need no projection.

## Supported adapters

The schema-v2 sharded adapter separates records by lifetime under a consumer-selected root:

```text
delivery-spine/
├── registry.json
├── claims/
│   ├── index.json
│   └── <journey-id>.json
├── baselines/
│   └── <journey-id>.json
└── archive/
    └── <journey-id>/
        └── <claim-id>.json
```

`_notes/delivery-spine` is a compatibility default, not a universal layout. Select it with `--adapter sharded` and override it with `--adapter-root <relative-path>`. Paths are resolved relative to the supplied consumer root and reject absolute paths, traversal, backslashes, and symlink escapes. Consumer conventions may select an adapter and arguments but grant no persistence, transition, deployment, or approval authority.

`_notes/delivery-spine.json` remains the default schema-v1 monolithic adapter selected by `--adapter v1`. Schema v1 remains readable throughout the schema-v2 support window. Removing it requires a separate intentional compatibility change after consumer migration and a supported migration window; schema-v2 introduction alone does not start or complete that removal.

## Projection lifetimes

### Stable registry

[`delivery-spine-registry.schema.json`](delivery-spine-registry.schema.json) owns stable journey identity, observable outcome, affected-path selectors, and suite references. Impact selection scans only this compact metadata and returns journey IDs with suites plus the IDs whose suite references are missing. A migrated schema-v1 journey has an empty suite list and a migration warning because schema v1 cannot supply that field.

### Current claims

[`delivery-spine-claim-index.schema.json`](delivery-spine-claim-index.schema.json) maps exact open WorkItems to journey claim files and retains the current staging-slot reference. [`delivery-spine-claim.schema.json`](delivery-spine-claim.schema.json) owns open delivery ownership, target and observed levels, current boundary observations, blockers, and current evidence references.

A completed WorkItem must not remain in the index or a current claim file. Removing it from the current projection is an owner-authorized persistence operation, not a consequence performed by a successful gate.

### Compact baselines

[`delivery-spine-baseline.schema.json`](delivery-spine-baseline.schema.json) retains the last supported level, boundary summary, and evidence references for one journey. A baseline is evidence context, not a current claim or proof that current source still matches the retained observation.

### Historical claims

Archived records use the claim schema under `archive/<journey-id>/<claim-id>.json`. They retain completed claim details outside routine context. Load them only by exact journey and claim, by an exact WorkItem dependency or evidence reference that resolves one claim, or for an explicit audit.

## Shared evidence rules

Boundary states are `missing`, `source_only`, `configured`, `deployed`, or `verified`. They describe evidence, not health or authorization. Evidence references must be repository-relative files, WorkItem IDs, or bounded non-secret operational identifiers. Never retain tokens, passwords, authorization codes, PKCE verifiers, MFA seeds, invitation links, raw claims, secret values, or personal email addresses.

At most one current claim may own the staging work-in-progress slot. Other dependency-ready release work remains ready; do not invent dependencies merely to serialize the slot.

The projection may reference deployment receipts but does not own receipt content or freshness comparison. Use the [environment-qualified deployment receipt](deployment-freshness.md) for that exact environment and deployable unit. A `deployed` or `verified` boundary without matching freshness evidence cannot prove current-source behavior.

Read the [retrieval contract](retrieval-contract.md) before selecting records. Read the [migration contract](migration-contract.md) before converting schema-v1 data.
