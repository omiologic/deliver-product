# Repository-local retrieval contract

Use this contract only after the repository-local work-item adapter is explicitly selected. Retrieval is read-only and grants no approval, readiness, persistence, transition, execution, deletion, or compaction authority.

## Modes

Select the narrowest mode supported by explicit intent and an exact selector:

| Mode | Required selector | Content boundary | Result |
| --- | --- | --- | --- |
| `target` | one WorkItem ID | selected item, transitive dependency closure, and summaries for selected compacted records | summary-first bounded WorkItem context |
| `lifecycle` | one of `backlog`, `ready`, `active`, or `archived` | paths and minimum identity, lifecycle, dependency, and cycle metadata only | compact lifecycle inventory |
| `cycle` | one exact phase, sprint, or compacted cycle ID | records belonging to that cycle and its summary when present | exact cycle context and compaction eligibility observations |
| `audit` | explicit audit request | intentional full projection content read | broad inspection result |
| `validation` | none | deterministic full projection scan | at most 100 ordered diagnostics plus an omitted count |

Metadata enumeration is not content loading. It may enumerate recognized paths and read frontmatter fields needed for identity, lifecycle, dependency closure, and cycle selection without loading Markdown bodies. Lifecycle scans stop at that metadata boundary.

## Retrieval order

For target retrieval:

1. Resolve the selected consumer-relative adapter path.
2. Enumerate recognized paths and minimum frontmatter metadata.
3. Resolve the exact target and its transitive dependency closure.
4. Read each applicable archived cycle summary.
5. Read only the selected dependency and target bodies.

An unresolved or duplicate identity, unresolved dependency, dependency cycle, unsafe path, or missing required archived summary is a bounded diagnostic. Do not broaden the read to search for a substitute.

Cycle retrieval selects only records attributable to the exact supplied cycle. Its compaction observations are advisory: eligibility requires a non-compacted selection containing no current items and no archived item with a placeholder, cancellation, or supersession result. An authorized compaction operation must still be explicitly requested and must preserve the lifecycle contract.

Run bounded retrieval with:

```text
python3 <skill-root>/scripts/retrieve_plans.py <consumer-root> \
  --mode target --work-item-id <work-item-id>
```

Use `--mode lifecycle --lifecycle <name>`, `--mode cycle --cycle-id <cycle-id>`, `--mode audit`, or `--mode validation` for the other explicit modes. Consumer-configured locations use the same `--plans-path` and `--profile-path` overrides as validation.

Deterministic validation may inspect every projection record, but compact diagnostics—not the inspected corpus—are the agent-facing result. Retrieval success and compaction eligibility are observations; they do not perform or authorize a lifecycle transition or filesystem mutation.
