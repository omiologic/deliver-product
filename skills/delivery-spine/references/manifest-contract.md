# Journey manifest contract

`_notes/delivery-spine.json` is a compact operational projection of important user journeys. It is not a roadmap, Plan, lifecycle record, deployment manifest, or source of authorization.

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
