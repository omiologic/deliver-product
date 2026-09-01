# Journey manifest contract

The journey manifest is an optional operational projection of important user journeys. It is not canonical runtime state, a roadmap, Plan, lifecycle record, deployment manifest, or source of authorization. Consumers that do not use Delivery Spine need no manifest.

`_notes/delivery-spine.json` remains the default compatibility path. Consumers may select another path with `--manifest-path <relative-path>`; the validator resolves it relative to the supplied consumer root and rejects absolute paths, traversal, backslashes, and symlink escapes. Consumer conventions may select applicability and this invocation argument without being parsed or owned by Delivery Spine. Selecting a path or adapter grants no persistence, transition, deployment, or approval authority, and the validator remains read-only.

A valid manifest is required only when an applicable Spine operation needs journey registration, impact mapping, or start/archive gate evidence. Keep it separate from general Delivery configuration; do not introduce `_notes/DELIVERY.md` for journey evidence.

The authoritative structural shape is [delivery-spine.schema.json](delivery-spine.schema.json). Keep one entry per journey and only the fields required to answer:

- what observable outcome the user is trying to complete;
- which work item currently owns the delivery claim;
- what evidence level is targeted and currently supported;
- which real boundaries participate and their observed state;
- which retained evidence supports the current level;
- what blocks the next level;
- which repository paths invalidate the journey evidence when changed.

Boundary states are `missing`, `source_only`, `configured`, `deployed`, or `verified`. They describe evidence, not health or authorization.

`active_staging_slice` is a journey ID or `null`. At most one registered journey may own the staging work-in-progress slot. Other dependency-ready release work remains `ready`; do not invent dependencies merely to serialize the slot.

Evidence references must be repository-relative files, work-item IDs, or bounded non-secret operational identifiers. Never retain tokens, passwords, authorization codes, PKCE verifiers, MFA seeds, invitation links, raw claims, secret values, or personal email addresses.

The manifest may reference bounded deployment receipt evidence, but it does not own receipt content or freshness comparison. Use the [environment-qualified deployment receipt](deployment-freshness.md) and deterministic preflight helper for that exact environment and deployable unit. A `deployed` or `verified` boundary without matching freshness evidence may describe previously observed provider state, but cannot prove current-source behavior.
