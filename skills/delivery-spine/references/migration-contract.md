# Schema-v1 migration contract

Migration is a separately authorized persistence operation. Preview is the default and reports deterministic counts by record lifetime without enumerating the complete output tree:

```sh
python3 scripts/migrate_delivery_spine.py <consumer-root> \
  --manifest-path _notes/delivery-spine.json \
  --adapter-root _notes/delivery-spine
```

Add `--write` only with explicit filesystem authority. The migration:

- validates schema-v1 input before constructing output;
- resolves source and destination relative to the consumer root;
- refuses an existing destination rather than merging or overwriting;
- writes a complete temporary tree and atomically installs it;
- preserves the schema-v1 source byte-for-byte;
- registers every valid journey;
- maps non-archived owner-produced WorkItems to current claims;
- maps archived owner-produced WorkItems to an archived claim and compact baseline; and
- emits empty suite lists with warnings because schema v1 has no suite references.

Migration does not infer a missing WorkItem or lifecycle. Unresolved ownership, an archived active-staging pointer, invalid input, an unsafe path, or an existing destination stops before output is installed. Migration never deletes data or performs a canonical archive, completion, deployment, release, or acceptance transition.
