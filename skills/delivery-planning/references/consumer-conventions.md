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

## Suggested introduction

A consumer may document only the choices it needs:

```markdown
## Delivery conventions

- Default planning type: feature-development
- Use research planning for durable questions that require retained evidence.
- Use bounded-outcome planning when no specialized type materially improves the proposal.
- Local planning projection: markdown-work-items
- Planning root: _notes/plans
- Delivery Spine applies to registered cross-boundary journeys.
- Delivery Spine manifest: _notes/delivery-spine.json
```

These values are examples, not package defaults. Omitted choices use the skill's thin guardrails and require no local configuration.

## Adapter boundary

Persistence requires an explicit request or owner-produced workflow plus filesystem authority. Resolve every configured path relative to the consumer root, reject path traversal outside that boundary, and never resolve consumer artifacts relative to the installed skill package.

`_notes/plans/**` is a supported legacy projection when selected by the consumer. Preserve stable consumer identifiers and compatibility when editing existing artifacts. Do not create that tree merely because planning was requested.

`_notes/DELIVERY.md` is not required. A consumer may introduce structured Delivery configuration for a demonstrated machine-readable need, but ordinary customization belongs in its conventions. Delivery Spine manifests remain separate optional operational projections rather than general Delivery configuration.
