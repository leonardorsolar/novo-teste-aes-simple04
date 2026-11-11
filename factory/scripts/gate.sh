#!/usr/bin/env bash
# Gate: as checagens do projeto. Saída 0 = segue para a revisão; outra saída = volta ao build com este log.
# Quem roda: factory/bin/gate (etapa gate) e o hook do builder, com a worktree do job como diretório.
# Regras: rápido, sem perguntas, sem modo watch, nada que reescreva arquivos (sem --fix).
# Troque a detecção automática abaixo pelos comandos reais do projeto quando quiser.
set -euo pipefail

ran=0

# Node: roda os scripts que existirem no package.json, nesta ordem.
if [ -f package.json ]; then
  has() { node -e "const s=require('./package.json').scripts||{}; process.exit(s['$1']?0:1)" 2>/dev/null; }
  if [ -f package-lock.json ]; then npm ci --prefer-offline --no-audit --no-fund; fi
  for s in lint typecheck test build; do
    if has "$s"; then echo "▶ npm run $s"; CI=1 npm run "$s"; ran=1; fi
  done
fi

# Python: pytest, se houver.
if { [ -f pyproject.toml ] || [ -f requirements.txt ]; } && command -v pytest >/dev/null 2>&1; then
  echo "▶ pytest"; pytest -q; ran=1
fi

if [ "$ran" = 0 ]; then
  echo "Nenhuma checagem encontrada (package.json com lint/typecheck/test/build, ou pytest)." >&2
  echo "Edite factory/scripts/gate.sh com os comandos de teste deste projeto." >&2
  exit 1
fi
echo "GATE: PASS"
