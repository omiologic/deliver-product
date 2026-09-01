# Consumer conventions and adapters

Read this reference only when consumer customization affects the proposal or the user requests a repository-local projection.

## Convention boundary

The skill owns thin defaults. A consumer's `CONVENTIONS.md` or equivalent owner-produced contract may define:

- preferred planning types and decidable selection rules;
- methodology terminology and proposal fields;
- decomposition thresholds or verification expectations;
- a consumer-owned planning contract or type reference;
- a local projection adapter and consumer-relative storage paths; and
- when specialized gates such as Delivery Spine apply.

Consumer conventions refine reusable procedure for that consumer. They cannot grant approval, readiness, persistence, execution, or transition authority, and they cannot weaken the shared planning contract.

Explicit user intent and exact owner-produced planning state take precedence over a convention. When two applicable conventions conflict materially, preserve the conflict and request owner resolution rather than choosing one. Omitted values use package defaults; do not invent terminology, proposal fields, decomposition thresholds, verification gates, adapters, or paths to fill the gap.

## Suggested introduction

A consumer may document only the choices it needs:

```markdown
## Delivery conventions

- Default planning type: feature-development
- Use research planning for durable questions that require retained evidence.
- Use bounded-outcome planning when no specialized type materially improves the proposal.
- Local planning projection: repository-local-work-items
- Planning root: _notes/plans
- Delivery Spine applies to registered cross-boundary journeys.
- Delivery Spine manifest: _notes/delivery-spine.json
```

These values are examples, not package defaults. Omitted choices use the skill's thin guardrails and require no local configuration.

## Adapter boundary

Persistence requires an explicit request or owner-produced workflow plus filesystem authority. Resolve every configured path relative to the consumer root, reject path traversal outside that boundary, and never resolve consumer artifacts relative to the installed skill package.

Selecting an adapter in conventions does not invoke it. Pass the consumer root and any configured relative paths only when the adapter is explicitly used for authorized persistence or validation. Do not scan for `_notes`, infer adapter selection from existing files, or turn a path value into mutation authority.

`_notes/plans/**` is a supported legacy projection when selected by the consumer. Preserve stable consumer identifiers and compatibility when editing existing artifacts. Do not create that tree merely because planning was requested.

When the selected projection is the package's repository-local work-item adapter, read [repository-local work items](adapters/repository-local-work-items.md). Its default compatibility paths are `_notes/plans` and `_notes/GOVERNANCE.md`; a consumer may override either with a relative path. Other adapters remain consumer-owned and do not need to be copied into this package.

For repository-local retrieval, pass an exact WorkItem, lifecycle, or cycle selector from the consumer when available. The adapter first enumerates minimum metadata, resolves the selector and dependency closure, reads applicable archived summaries, and only then loads selected bodies. Use broad audit or full validation modes only when explicitly requested by their operation; adapter selection alone does not authorize either.

`_notes/DELIVERY.md` is not required. A consumer may introduce structured Delivery configuration for a demonstrated machine-readable need, but ordinary customization belongs in its conventions. Delivery Spine manifests remain separate optional operational projections rather than general Delivery configuration.
