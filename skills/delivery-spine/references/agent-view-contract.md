# Agent-view contract

Use agent views only after the bounded retrieval contract has selected and projected the records required by one operation. They are ephemeral agent input, not a projection format, structured-output contract, evidence record, or source of authority.

## Interface

`compact-json` is the stable default and fallback. `toon` and `safe-yaml` are explicit diagnostic or evaluation modes. `auto` may select only a candidate approved by [`agent-view-selection-policy.json`](agent-view-selection-policy.json). Retained release measurements live in [`agent-view-benchmark-results.json`](agent-view-benchmark-results.json).

Every view wraps the complete selected projection in `data` and declares an `agent_view` containing the view version, requested and selected encoding, encoding or profile version, tokenizer identity and version, selection-policy version and provenance, implementation identity and version, completeness, final estimated token count, and any fallback reason. A missing approved tokenizer is represented by `null` metadata and forces `auto` to compact JSON.

Token measurements include the complete serialized envelope: declarations, wrappers, alias dictionaries, and profile metadata. The renderer recomputes the count until the count embedded in the final view stabilizes.

## Candidate gates

Every candidate must decode to the exact selected JSON-shaped value. `auto` additionally requires the versioned representative evaluation to show the same expected task answers as compact JSON, at least 15 percent net token savings, and the frozen absolute token floor. Apply the policy thresholds consistently to every payload; do not tune them for an individual request.

TOON targets specification 4.1. Restricted safe YAML targets YAML 1.2 through the `delivery-spine-safe-yaml-1.2-v1` profile: safe construction only, duplicate keys rejected, aliases and anchors disabled, custom or application tags prohibited, string-only mapping keys, and exact parser version metadata. If the approved implementation or version is missing, unsupported, unsafe, or fails reconstruction, fall back to compact JSON.

Header-plus-rows JSON and property aliases are internal candidates unless the policy approves them. Alias overhead includes the complete dictionary, and aliases may ship only after demonstrating an incremental net win without task-answer regression.

## Boundaries

Rendering never changes schema-v1 or schema-v2 JSON files, stored property names, JSON Schemas, migration behavior, agent-generated structured output, gate results, or lifecycle state. Encoding selection grants no persistence, migration, deletion, evidence acceptance, deployment, release, completion, or transition authority.
