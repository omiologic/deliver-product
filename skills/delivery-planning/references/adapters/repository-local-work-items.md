# Repository-local work-item adapter

Load this adapter only when consumer conventions or an owner-produced contract selects the legacy `_notes/plans/**` projection. The adapter takes an explicit consumer root and resolves `_notes/GOVERNANCE.md`, `_notes/plans/`, and every artifact below them from that root. Reject absolute configured paths and paths that escape the consumer boundary.

The files are advisory planning projections. Their lifecycle directories describe local artifact state only; they do not create canonical Plan or WorkItem records, approval, readiness, execution scope, or transition authority. Persistence still requires an explicit request or owner-produced workflow and filesystem authority.

Read [planning profiles](repository-local/planning-profiles.md) when project identity or optional methodology dimensions affect an item. Read [work-item conventions](repository-local/work-item-conventions.md) before creating or editing a file. Read [work-item lifecycle](repository-local/work-item-lifecycle.md) before changing its directory or index entry.

Validate a selected projection with:

```text
python3 <skill-root>/scripts/validate_plans.py <consumer-root>
```

The command is explicit adapter selection. Advisory Planning must not run it merely because a consumer repository contains `_notes`.
