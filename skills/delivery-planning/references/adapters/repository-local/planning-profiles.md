# Repository-local planning profiles

`_notes/GOVERNANCE.md` may supply planning identity and organization for this compatibility adapter. Its presence does not select the adapter or grant persistence authority. Context Governance or another owner remains authoritative for governance-owned sections.

The adapter supports schema versions 1, 2, and 3 from the legacy contract. Schema v3 planning fields are:

```yaml
---
schema_version: 3
project_key: account-api
canonical_ids_from: "2026-08-24T12:00:00Z"
last_work_item_sequence: 0
profile: minimal
---
```

`project_key` is an immutable 2–16 character lowercase kebab slug. New IDs use `<project-key>-NNNNN`. `canonical_ids_from` is the RFC 3339 boundary after which new items must use that form. `last_work_item_sequence` is a monotonic high-water mark from `0` through `99999`; allocation uses the greater of this value and the highest visible canonical sequence, increments once, and advances the high-water mark in the same authorized change as the new item. Never reuse a number.

Schema v2 retains `qualified_ids_from` and supported project-qualified legacy IDs. Schema v1 and supported `work-*` items created before the applicable boundary remain legacy evidence. Upgrading identity never renames an artifact automatically.

Profiles are `minimal`, `phased`, `sprint`, `product`, or `custom`. `phased` requires `phase_id`; `sprint` requires `sprint_id`; `product` requires `feature_ids` and permits `epic_id`; `custom` declares enabled `phase`, `sprint`, `epic`, or `feature` dimensions as `required` or `optional`. Every enabled dimension has a catalog of unique lowercase kebab IDs with a title and decidable definition. Sprint catalog entries may add valid `starts_on` and `ends_on` dates.

Git Governance and Version Governance sections are opaque to this adapter. Preserve them byte-for-byte when an authorized planning edit changes the shared envelope, and route their interpretation or validation to Context Governance.
