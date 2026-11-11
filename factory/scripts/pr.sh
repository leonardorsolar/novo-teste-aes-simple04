#!/usr/bin/env bash
# PR: abre o PR em rascunho da branch do job (ou reaproveita o que já existe).
# Quem roda: factory/bin/job run <job>, na worktree do job, com JOB_ID, BRANCH, BASE, ISSUE,
# TITLE, JOB_DIR e OUT no ambiente. Saída 0 = PASS; outra = FAIL (o job vai para um humano).
# Imprime `PR: <número>` e `PR_URL: <url>`: o motor guarda os dois no job.
# Modo local (LOCAL=1, tarefa iniciada sem GitHub): não há PR; a branch fica pronta para o merge local.
set -euo pipefail

if [ -n "$(git status --porcelain)" ]; then
  echo "A worktree tem alterações sem commit; o build precisa commitar antes do PR." >&2
  exit 1
fi
if [ "${LOCAL:-}" = "1" ]; then
  echo "Modo local (sem GitHub): sem PR. A branch $BRANCH fica pronta para o merge local em $BASE."
  exit 0
fi
git push -u origin "$BRANCH"

if ! gh pr view "$BRANCH" --json number >/dev/null 2>&1; then
  summary=""
  if [ -f "$JOB_DIR/build.md" ]; then
    summary=$(awk '/^## Summary/{on=1; next} /^## /{on=0} on' "$JOB_DIR/build.md")
  fi
  title=$(head -1 "$JOB_DIR/spec.md" 2>/dev/null | sed 's/^# *//' || true)
  gh pr create --draft --base "$BASE" --head "$BRANCH" --title "${title:-$TITLE}" \
    --body "$(printf 'Closes #%s\n\n%s\n' "$ISSUE" "$summary")" >/dev/null
fi
echo "PR: $(gh pr view "$BRANCH" --json number -q .number)"
echo "PR_URL: $(gh pr view "$BRANCH" --json url -q .url)"
