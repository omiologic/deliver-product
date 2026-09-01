# Repository-local work-item conventions

Create an item from [the task template](../../../assets/task-template.md) and replace every placeholder. Name it `<work_item_id>.<short-kebab-title>.md`; preserve its ID and filename after creation.

Required frontmatter is `work_item_id`, `title`, `depends_on`, `target_paths`, `created_at`, and `updated_at`. Dependencies and target paths are YAML lists. Targets must be non-empty repository-relative paths that cannot escape the consumer root. Timestamps use RFC 3339. The first heading matches `title`.

Add `phase_id`, `sprint_id`, `epic_id`, or `feature_ids` only when enabled by the selected profile. Split an item across phase, sprint, or epic boundaries. Keep multiple features only when the item remains one atomic outcome with one dependency path and completion decision.

Do not add `status`; the containing directory is the local projection state. Do not add canonical model fields, execution attempts, or runtime state. A missing identity contract blocks new persisted items but does not block advisory Planning.
