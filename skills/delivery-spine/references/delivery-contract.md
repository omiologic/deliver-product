# Delivery contract

Use this contract only for work to which Delivery Spine applies.

## Work-item section

Add this section after `Context` and before `Scope`:

```markdown
## Delivery spine

- Journey ID: identity-administration
- Target evidence: staging_verified
- Integration consumer: self
```

`Journey ID` must match `_notes/delivery-spine.json`. Use `none` only for source-only work that does not itself own a registered journey. `Integration consumer` is `self`, an exact work-item ID, or `none` when the source work has no downstream product journey.

Integrated and staging work also includes:

```markdown
## Integration preflight

- [ ] Required UI, identity, API, persistence, and configuration boundaries are identified or explicitly not applicable.
- [ ] Test identity or approved fixture authority is available without copying credentials into evidence.
- [ ] Required endpoints, secret references, migrations, deployment authority, and rollback baseline are resolved or recorded as blockers.
- [ ] Exact environment, deployable-unit, endpoint, artifact, applicable public-configuration, source, and retained deployment-receipt identities match before shared-environment user interaction.
- [ ] A reproducible real-journey verification route is defined.
```

Preflight is deliberately small. Check a line only when evidence exists; unresolved lines may remain visible while already-active work is blocked, but the `start` gate rejects them for a new transition.

## Blocker resolution

When any applicable check fails, retain this section before retrying or asking
for authority:

```markdown
## Blocker resolution

- State: detected | investigating | owner_assigned | waiting_for_human | implementation_pending | verified | resumed
- Class: missing_prerequisite | rollback | placeholder | stale_receipt | wrong_account | authority_required | source_defect
- Detected by: exact command or inspection and time
- Evidence: bounded non-secret observation
- Owner work items: exact IDs, or `unowned`
- Safe solution: smallest path that removes the blocker
- Human action: exact approval/action, or `none`
- Exit evidence: exact receipt, test, output, or state needed to resume
```

An unresolved record (`detected` through `implementation_pending`) bars a
successful archive. A staging item with a missing upstream producer returns to
backlog so another ready staging prerequisite can own the sole slot.

## Evidence rules

| Class | Proves | Maximum delivery level |
| --- | --- | --- |
| `component` | Unit, component, accessibility, or browser behavior with replaced boundaries | `source_complete` |
| `contract` | Request, response, schema, policy, or adapter agreement | `source_complete` |
| `integrated_local` | The journey crosses its named real local or isolated boundaries | `integrated` |
| `staging_e2e` | The journey crosses its deployed staging boundaries | `staging_verified` |

Fixtures may seed initial state. A fixture that replaces a claimed identity, transport, service, persistence, email, provider, or deployment boundary limits the evidence to `component` or `contract` for that boundary.

## Completion rules

Before a successful archive transition:

- every checkbox under `Acceptance criteria` and `Verification` is checked;
- `Result` and `Evidence` contain actual non-placeholder completion text;
- the manifest's current level reaches the work item's target level;
- the evidence class supports that level;
- deferred product criteria are removed from the claim and assigned to an explicit integration consumer or dependent item, not hidden in `Follow-ups`.

For a credentialed, destructive, or release-significant shared-environment journey, run the environment-qualified freshness preflight immediately before user interaction. A missing or mismatched receipt blocks current-source evidence. An explicitly requested stale-target diagnostic stays labeled diagnostic-only and cannot satisfy `integrated` or `staging_verified` evidence.

Cancellation and supersession are separate Context Governance outcomes and do not claim successful delivery.
