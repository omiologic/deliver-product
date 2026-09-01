# Assessment contract

## Assessments

| Assessment | Use when |
| --- | --- |
| `SUCCESS` | Every applicable criterion is supported by sufficient verification evidence and no material unintended effect remains. |
| `PARTIAL` | Some criteria are verified and some remain unsatisfied or unverified. |
| `FAILED` | The bounded attempt failed and the evidence does not indicate a prerequisite or staleness blocker. |
| `BLOCKED` | A required dependency, authority, capability, or external condition prevents assessment or progress. |
| `STALE` | Owner-produced scope, context, or prerequisites no longer match observed reality. |
| `DIVERGED` | The result materially differs from intended scope or has material unintended effects. |
| `SUPERSEDED` | An owner-produced replacement makes the assessed work no longer current. |
| `NEEDS_REPLAN` | Invalid assumptions or changed conditions require a bounded planning revision before more execution. |

`SUCCESS` requires criterion-level verification; execution success alone is insufficient. When multiple labels could apply, select the label that best determines the next owner action and describe secondary conditions in the evidence notes.

## Output

Provide:

1. one assessment;
2. each criterion and its supporting, contradicting, or missing evidence;
3. unintended effects, drift, and uncertainty;
4. a bounded recommendation and its owner; and
5. evidence references with enough provenance for review.

The output is advisory. It must not encode or perform a canonical WorkItem, Plan, or Execution transition.

