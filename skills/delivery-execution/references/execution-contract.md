# Execution contract

## Required envelope

Execution requires:

| Input | Source |
| --- | --- |
| Exact WorkItem selection | Canonical owner or responsible person |
| Approval and readiness | Canonical runtime or responsible person |
| Immutable scope and acceptance criteria | Owner-produced execution snapshot |
| Applicable context and assignments | Owning context and capability domains when present |
| Authority for each intended effect | User, policy, or authorized operation boundary |

Skill invocation alone supplies none of these inputs.

## Observation record

Capture the attempted action, result, affected targets, evidence location, and any failure or blocker. Preserve enough provenance for reconciliation to compare observations with each acceptance criterion.

A zero exit status, successful API response, generated artifact, or completed tool call is a result. It becomes verification evidence only when it materially supports an explicit acceptance criterion.

If scope, assumptions, or prerequisites become stale, stop and hand the observation to reconciliation. Do not silently retry with different scope or authority.

