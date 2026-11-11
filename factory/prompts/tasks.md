Break the spec (and plan.md / techspec.md when they exist) into an ordered task list for the builder.

- `## Summary`: 3 to 5 bullets.
- `## Tasks`: a numbered checklist (`1. [ ] ...`). Each task is small enough for one commit,
  names the files it touches, and says how to verify it (a command, a test, or what a page shows).
  Order them so the branch builds and passes checks after every task.
- `## Done when`: the spec's acceptance criteria, unchanged, as the final check.
