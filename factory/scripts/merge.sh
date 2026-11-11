#!/usr/bin/env bash
# Merge: atualiza a branch com a base, roda o gate de novo e faz o merge pelo GitHub.
# Quem roda: factory/bin/job run <job>, na worktree do job, com JOB_ID, BRANCH, BASE, PR,
# MERGE_METHOD e REPO no ambiente. Saída 0 = MERGED; outra = FAIL (o job vai para um humano).
# Com GitHub: nunca faz merge local na base, nunca --force, nunca --admin.
# Modo local (LOCAL=1, tarefa iniciada sem GitHub): traz a base para a branch, roda o gate de novo e
# avança a base local só por fast-forward (nunca reescreve histórico).
set -euo pipefail

if [ "${LOCAL:-}" = "1" ]; then
  if ! git merge --no-edit "$BASE"; then
    git merge --abort || true
    echo "A branch tem conflito com $BASE." >&2
    exit 1
  fi
  "$REPO/factory/bin/gate" "$JOB_ID" --merge
  head=$(git rev-parse HEAD)
  old=$(git -C "$REPO" rev-parse "refs/heads/$BASE")
  git merge-base --is-ancestor "$old" "$head" || { echo "$BASE andou durante o merge; rode de novo." >&2; exit 1; }
  if [ "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)" = "$BASE" ]; then
    # a base está aberta no checkout principal: fast-forward pelo git, que recusa se pisar em alterações suas
    git -C "$REPO" merge --ff-only "$head"
  else
    git -C "$REPO" update-ref "refs/heads/$BASE" "$head" "$old"
  fi
  echo "MERGED"
  exit 0
fi

[ -n "${PR:-}" ] || { echo "O job não tem PR; a etapa pr precisa rodar antes." >&2; exit 1; }

state=$(gh pr view "$PR" --json state -q .state)
if [ "$state" = "MERGED" ]; then echo "PR #$PR já estava mergeado."; exit 0; fi

git fetch origin "$BASE"
if ! git merge --no-edit "origin/$BASE"; then
  git merge --abort || true
  echo "A branch tem conflito com $BASE." >&2
  exit 1
fi
"$REPO/factory/bin/gate" "$JOB_ID" --merge
git push origin "$BRANCH"
if [ "$(gh pr view "$PR" --json isDraft -q .isDraft)" = "true" ]; then gh pr ready "$PR"; fi
gh pr merge "$PR" "--$MERGE_METHOD"
git push origin --delete "$BRANCH" >/dev/null 2>&1 || true   # o GitHub pode já ter apagado
echo "MERGED"
