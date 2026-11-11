Turn spec.md into a technical design the builder can follow without guessing.

- `## Summary`: 3 to 5 bullets.
- `## Approach`: the design in a few paragraphs, and why it beats the obvious alternative.
- `## Changes`: per file or module (cite real paths), what changes and why.
- `## Data`: schema, storage or API contract changes. Write "None." when there are none.
- `## Risks`: what could break, and how the change avoids or detects it.
- `## Test plan`: which tests to add or change, mapped to the spec's acceptance criteria.

Follow the repo's existing patterns (AGENTS.md / CLAUDE.md and the neighbouring code).
Don't add options, fallbacks or extras the spec doesn't ask for.
