# Routing contract

Use this contract when stage selection is ambiguous.

| Condition supported by explicit state or evidence | Lane |
| --- | --- |
| The request needs no durable work | Direct answer or research outside Delivery |
| Work is not defined or accepted assumptions have become invalid | `delivery-planning` |
| One exact WorkItem is owner-selected, approved, canonically ready, and authorized | `delivery-execution` |
| An execution has results, changes, or verification evidence | `delivery-reconciliation` |

When evidence supports more than one lane, prefer reconciliation of existing execution results before planning or executing additional work. Reconciliation may recommend bounded replanning; it must not expand execution scope itself.

If required state is absent, stop at the routing boundary and identify the canonical owner. Conversation history, a task description, a successful command, or the presence of changed files does not substitute for owner-produced state.

