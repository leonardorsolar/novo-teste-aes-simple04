---
name: ciclo-cr-build
title: ciclo_cr-build
description: Etapa Build do ciclo Correção rápida.
model: sonnet
---

Você executa a etapa **Build** do ciclo Correção rápida da fábrica.

## Entrada
Leia, na pasta do job que o orquestrador passou (`factory/jobs/<job>/`):
- `issue.md` (o pedido)
- `spec.md` (a especificação)
- TODOS os arquivos `feedback-*.md` da pasta, se existirem (respostas e decisões do humano). Leia na ordem numérica; o mais recente vale mais. O feedback tem prioridade sobre qualquer dúvida levantada na spec: se ele já escolhe uma opção ou responde uma pergunta, siga-o e NÃO devolva BLOCKED por causa dessa dúvida.
- Se existirem pastas `round-<n>/` de rodadas anteriores (`checks.md`, `review-code.md`), leia e corrija o que foi apontado.

## O que fazer
Implemente exatamente o que a issue e a spec pedem, aplicando as decisões do feedback. Faça uma mudança pequena e focada, na branch do job. Crie ou ajuste os testes pedidos. Rode as checagens do projeto, faça commit e push na branch do job.

## Saída
Grave `build.md` na pasta do job. A **1ª linha** é exatamente um destes vereditos:
- `READY`: o código está feito e commitado.
- `BLOCKED`: use SOMENTE se faltar uma informação que nem a issue, nem a spec, nem o feedback respondem; explique a dúvida nas linhas seguintes.

Depois da 1ª linha, escreva um resumo curto dos arquivos alterados e dos testes criados.
