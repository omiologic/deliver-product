# Planning-type routing

Choose one planning type while keeping the shared [planning contract](planning-contract.md) authoritative.

## Selection precedence

1. Use the planning type explicitly selected by the user.
2. Otherwise use an exact type supplied by owner-produced planning state or a consumer planning contract.
3. Otherwise apply the relevant type-selection rule in the consumer's conventions.
4. Otherwise select a package type only when the requested outcome and current evidence make it clear.
5. Use [bounded outcome](planning-types/bounded-outcome.md) when no specialized type materially improves the proposal.

Do not infer approval, readiness, persistence, or canonical state from planning-type selection. If multiple types remain plausible, ask only when the choice would materially change commitment, decomposition, authority, or persistence. Otherwise use the bounded-outcome type and preserve the uncertainty.

## Scalable type library

Planning types belong under `references/planning-types/`. Add a type when it provides a materially different proposal shape or reasoning procedure for repeated cases. Each type should state when it applies, what it adds to the shared contract, and when not to use it.

Keep common guardrails in `planning-contract.md`. Do not duplicate authority rules, consumer state models, persistence policy, or general WorkItem quality rules in each type. Link a new type from this routing reference only when it contains working guidance and a decidable selection boundary.

Consumer-owned types do not need to be copied into this package. Follow them when an applicable owner-produced contract or convention makes the type available, subject to the shared planning contract and existing authority.

## Package types

Load only the selected type:

| Type | Decidable boundary |
| --- | --- |
| [bounded-outcome](planning-types/bounded-outcome.md) | No specialization materially improves one bounded proposal. |
| [feature-development](planning-types/feature-development.md) | The requested outcome is one independently testable product or system capability. |
| [sprint](planning-types/sprint.md) | An explicit or owner-produced time box governs the commitment and ordering. |
| [research](planning-types/research.md) | A durable question requires a retained method and evidence. |
| [phased-project](planning-types/phased-project.md) | The proposal coordinates exact related delivery Plans and is not executable itself. |

Treat the legacy `quick-task` identifier as an alias for `bounded-outcome`; it does not justify a duplicate procedure. Do not infer `sprint` merely from multiple WorkItems or `phased-project` merely from a large outcome.
