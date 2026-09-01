# Deliver Product contributor instructions

## Required context

1. Read `ARCHITECTURE.md` and `CONVENTIONS.md` before changing behavior.
2. Read the affected `skills/*/SKILL.md` entrypoint and every reference it links for the behavior being changed.
3. Use the installed `skill-creator` guidance for Skill changes.

## Repository boundary

- Keep this repository reusable and safe for public distribution. Do not add private workspace paths, credentials, customer data, or consumer-specific policy.
- Treat the repository root as a package workspace, not as an installable Skill. Installable entrypoints live at `skills/<skill-name>/SKILL.md`.
- Preserve the dependency direction in `ARCHITECTURE.md`: Delivery may consume governed context, but Context Governance must not depend on Delivery.
- Consumer runtimes own canonical Plan, WorkItem, Execution, Context, Inbox, and Capability state. Repository-local artifacts are projections, not canonical runtime records.
- Skill instructions coordinate work; they never create filesystem, network, Git, deployment, approval, publication, or runtime-transition authority.

## Change rules

- Keep `deliver-product` a thin router. Put stage behavior in the applicable child skill.
- Treat `delivery-spine` as a specialized journey-evidence gate, not as a fifth lifecycle stage. Preserve its imported behavior until an intentional compatibility change updates its contract and tests together.
- Route only from explicit user intent, owner-produced state, or evidence. Never infer approval, readiness, success, verification, completion, or acceptance from conversation alone.
- Preserve the direct-answer lane for requests that do not need durable delivery work.
- Keep execution and reconciliation separate. A successful operation is a result, not proof that acceptance criteria are satisfied.
- Keep assessment terms advisory. Only the owning runtime or person may perform a canonical state transition.
- Add shared rules to one owning contract and link to them; do not duplicate policy across entrypoints.
- Add a fixture or test when changing routing, authority boundaries, stage inputs or outputs, or reconciliation classification.

## Verification

Run before handing off a material change:

```bash
rtk python3 scripts/validate.py
rtk python3 -m unittest discover -s tests -v
rtk python3 -m unittest discover -s skills/delivery-spine/tests -v
```

Also run the installed Skill validator against each changed `skills/*` package when it is available.
