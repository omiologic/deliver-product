# Bounded retrieval contract

Select the smallest mode supported by explicit intent and exact owner-produced identifiers:

| Mode | Required selector | Records loaded or scanned | Result |
| --- | --- | --- | --- |
| `target` | one journey ID | registry, current-claim index, exact claim, exact baseline | one compact journey view |
| `work-item` | one WorkItem ID | registry and current-claim index, then exact claim and baseline | one compact current claim view |
| `impact` | changed paths | registry only | affected journey IDs, suites, and IDs missing suite references |
| `validation` | none | deterministic full projection scan | compact diagnostics only |
| `history` | journey plus exact claim, WorkItem dependency, or evidence reference | exact journey archive | one exact historical chain |
| `audit` | explicit audit request | intentional broad projection read | broad inspection result |

Target, WorkItem, preflight, and archive-gate operations must not return unrelated registrations, claims, baselines, or history. Preflight means the start-gate operation using WorkItem retrieval, not a separate retrieval mode. Validation may scan every record in deterministic code, but it emits at most 100 ordered diagnostics plus an omitted count so the full corpus is not injected into model context.

Schema-v1 target, WorkItem, impact, validation, and audit operations remain available through the compatibility reader. Schema v1 has no separate history projection, so `history` returns a bounded unsupported-mode diagnostic rather than treating current manifest content as archived evidence.

Retrieval and successful validation are read-only observations. They never persist, compact, migrate, transition, deploy, release, approve, complete, or accept work.

After selection and operation-specific projection, structured results may use the [agent-view contract](agent-view-contract.md). Rendering must not cause additional records to be loaded. Compact JSON is the default; alternate input encodings remain ephemeral and benchmark-gated.
