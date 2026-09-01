# Conventions

## Skill packages

- Name packages with lowercase kebab-case and keep the directory name equal to the `name` in `SKILL.md` frontmatter.
- Keep entrypoints short and procedural. Put detailed, stage-specific contracts in `references/` and link them from the entrypoint at the point of use.
- Use relative links within a package. Do not make an installed skill depend on files outside its own package.
- Include only directories with working content. Do not commit empty `scripts/`, `references/`, `assets/`, or placeholder examples.
- Keep automatic discovery enabled unless a user explicitly requests an explicit-only skill.

## Contract language

Use these terms consistently:

- **owner-produced**: supplied by the canonical runtime or responsible person, rather than inferred by Delivery;
- **canonical**: authoritative state owned outside these skills;
- **result**: the observable output of an execution attempt;
- **evidence**: material that can verify or falsify an acceptance criterion;
- **assessment**: Reconciliation's advisory comparison of criteria and evidence; and
- **transition**: a state change performed by the canonical owner.

Use `must` only for an invariant required by safety, authority, or a cross-stage contract. Use `should` for a strong default with legitimate exceptions and `may` for optional behavior.

## Imported packages

- Preserve a newly imported package byte-for-byte for its initial import and verify it against its source tree.
- Record known architectural compatibility gaps instead of silently rewriting imported behavior during the copy.
- After import, this repository becomes the package's source of truth. Later changes follow the same contract, test, and validation rules as other packages.

## Routing and ownership

- Express routing conditions in terms of explicit intent, owner-produced state, and evidence.
- Say which owner must supply missing state instead of fabricating a substitute.
- Do not encode consumer state machines, approval policy, provider behavior, or operational side effects in a Delivery skill.
- Do not use execution success, command exit status, or a generated artifact as a synonym for acceptance.
- Route invalid assumptions or material divergence to bounded replanning; do not silently retry with expanded scope.

## References and tests

- A reference has one contract owner and a clear reason to be loaded from `SKILL.md`.
- Cross-stage changes require atomic updates to affected entrypoints, references, fixtures, and validation.
- Prefer scenario fixtures that exercise observable routing and authority boundaries over tests that only match prose or headings.
- Keep validators dependency-free unless a dependency materially improves correctness and is documented.
- Use synthetic, public-safe fixture data. Consumer artifacts are compatibility evidence, not templates to copy.

## Documentation

- Keep `README.md` focused on users and repository status.
- Keep `ARCHITECTURE.md` authoritative for ownership, dependency direction, and lifecycle boundaries.
- Record contributor procedure in `AGENTS.md` and repository-wide authoring choices here.
- Update status claims when behavior becomes installable or validated; do not describe planned behavior as current.

## Terminal output policy

Use RTK for human-facing exploratory and verification commands, including `rtk read`, `rtk find`, `rtk git status`, `rtk git diff`, and `rtk test`. Use raw commands when exact machine-readable output is required. If RTK is unavailable, use the normal command and report the fallback.
