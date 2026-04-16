<!-- SPECKIT:START -->
# Speckit Instructions

These instructions are for AI assistants working in this project.

Always open `@/.specify/memory/constitution.md` and relevant files in `@/specs/` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use the Speckit workflow to drive spec-first delivery:
- `/speckit.specify` to create or update the feature specification
- `/speckit.plan` to generate implementation design artifacts
- `/speckit.tasks` to generate dependency-ordered implementation tasks
- `/speckit.implement` to execute approved tasks

Keep this managed block so Speckit tooling can refresh the instructions.

<!-- SPECKIT:END -->
