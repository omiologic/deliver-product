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

## Repository search and context hygiene

- Use supplied paths and exact owner-produced references before searching repository text.
- Search only when a required repository location is unknown; batch related discovery where practical and keep output bounded.
- Do not use `rg` or another text search to manufacture missing approval, readiness, completion, acceptance, verification, or other canonical state. Report missing owner-produced state to its owner.
- Prefer bounded deterministic adapters and changed-path inputs over broad textual discovery when they are available.
- Keep searches within the authorized consumer or repository boundary and exclude generated, vendor, and unrelated workspace content unless explicitly in scope.
- Treat search results as observations, not authority or evidence until the owning contract makes them attributable.

## Planning types and consumer conventions

- Keep universal planning guardrails in the shared planning contract. A planning type may refine proposal shape, decomposition, or verification guidance but must not duplicate or weaken those guardrails.
- Store substantial planning types under `delivery-planning/references/planning-types/` and load only the selected type.
- Select a planning type from explicit user intent, owner-produced planning state, applicable consumer conventions, or clear outcome evidence, in that order. Use the bounded-outcome default when no specialized type materially improves the proposal.
- Ask about the type only when ambiguity would materially change commitment, decomposition, authority, or persistence.
- Treat consumer `CONVENTIONS.md` or an equivalent owner-produced contract as the home for methodology preferences, terminology, type-selection rules, decomposition thresholds, and adapter choices.
- Do not turn one consumer's convention into a package-wide default.

## Consumer-relative artifacts

- Advisory Delivery requires no repository-local configuration or planning tree.
- Persist only after an explicit request and within granted filesystem authority.
- Resolve adapter paths relative to the consumer root, never the installed skill package, and reject paths that escape the consumer boundary.
- Treat `_notes/plans/**` as a compatibility projection, not a universal layout or canonical runtime state.
- Do not require `_notes/DELIVERY.md`; prefer consumer conventions for ordinary customization and introduce structured configuration only for a demonstrated machine-readable need.
- Keep Delivery Spine projections separate from general configuration because they retain optional operational journey evidence. Their existence must remain conditional on Delivery Spine use, and routine retrieval must not load completed history.

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
