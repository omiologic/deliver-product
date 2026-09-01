# Repository-local work-item lifecycle

The compatibility projection uses `backlog`, `ready`, `active`, and `archived` directories below the selected planning root, `_notes/plans/` by default. `PLAN.md` is a navigational index, not a second status source. Compacted immutable records may live below `archived/history/<cycle-id>/` with one matching `archived/summaries/<cycle-id>.md` index entry.

An item is locally ready only when every dependency is archived with a non-placeholder result other than cancellation or supersession. An item with no dependencies is ready immediately. Keep open items with missing, active, cancelled, superseded, or ambiguous dependencies in backlog. Never infer canonical readiness from this classification.

For an authorized lifecycle change, re-read the profile, index, and affected item; move the file and reconcile exactly one relative index link in the same change. Reconcile affected open dependents after creation, completion, cancellation, supersession, restoration, or dependency changes. Never move an active item automatically.

Preserve all four index headings and use an empty placeholder only for an empty section. Every current item must be indexed exactly once, every link must resolve, every compacted cycle must have one indexed summary, and relative links inside moved items must remain valid.

Archive rather than delete by default. Compaction and deletion require explicit requests. A completion record is evidence in the projection, not proof of canonical acceptance or authority to perform another effect.
