---
name: sdlc-plan
installer-group: factory
version: 1
description: >-
  Writes a committed plan.md from intent.md + spec.md before any code is
  generated — which files change, in what order, and what proves each step
  worked. Third file in the ai-native-sdlc chain (intent.md -> spec.md ->
  plan.md), and the last one before implementation.
---

# Plan first

Third file in the chain (`ai-native-sdlc`). Left implicit, the approach lives
in one person's head and the first reviewable thing is a finished diff. A
plan moves that decision to when it's still a document edit.

## Quando chamada pela fábrica (factory/pipeline.yaml)

Se o pedido começa com `Job: ... Job folder: ...` e traz as linhas `Step:`, `Read:` e `Write:`,
esta skill está rodando como uma etapa da fábrica. Nesse caso, e só nesse:

- leia os arquivos de `Read:` e grave **apenas** o arquivo de `Write:`, ambos na pasta do job
  (`Job folder:`), em vez de `.aes/ai-native-sdlc/<slug>/`;
- a 1ª linha do arquivo é o veredito: `VERDICT: DONE`, ou `VERDICT: BLOCKED` com uma seção `## Blocked` quando uma decisão que só uma pessoa pode tomar impede o documento;
- não pare para perguntar: registre as decisões em `## Assumptions`;
- blocos `Step instructions` / `Task instructions` do pedido complementam esta skill.

Sem essas linhas, siga o fluxo abaixo normalmente.

## Onde salvar (obrigatório)

```
.aes/ai-native-sdlc/<slug>/
├── intent.md
├── spec.md
└── plan.md
```

0. Confirme a raiz do projeto: o diretório que contém `AGENTS.md`,
   `CLAUDE.md` ou `.cursorrules`.
1. `<slug>` é o mesmo de `intent.md`/`spec.md` — **nunca crie um slug novo**.
   Se houver ambiguidade, pare e peça esclarecimento (ou, em execução
   orquestrada pelo app, use o slug que o prompt já informou).
2. Leia `intent.md` e `spec.md` de `.aes/ai-native-sdlc/<slug>/`. Se algum dos
   dois não existir, isso é bloqueio evidenciado — avise qual falta e pare.

## What the plan names

```markdown
# Plan: <nome da feature> (from intent.md <data>)

## Files that change
<lista de arquivos, novos marcados como (new)>

## Order of work
1. <passo> — [ ]
2. <passo> — [ ]

## Risks
<o que pode quebrar>

## Proof
<como cada passo se prova — testes, comando de verificação>

## Verificação: <comando único de build+teste, descoberto em package.json/Makefile/CLAUDE.md/AGENTS.md — nunca inventado>
```

A barra: **alguém que nunca viu a conversa conseguiria implementar a mudança
só com o plano.** Cada passo de "Order of work" precisa de um item de
checklist `- [ ]` e de uma prova (não é opcional — um plano sem prova
checável não fecha o próprio loop).

## Interactive run (default)

Quando há um humano na sessão: interrogue o próprio plano (o que pode
quebrar, passo mais arriscado, alternativas descartadas) antes de considerar
aceito.

## App-orchestrated run

Se o prompt já informar um slug, use exatamente esse slug, não derive outro.

Quando o prompt diz que a execução é orquestrada pelo app (sem humano
observando), rode você mesmo o interrogatório e registre as respostas no
`plan.md` — nunca pare esperando resposta.

Faça só isto: grave `.aes/ai-native-sdlc/<slug>/plan.md` e PARE — não escreva
nem edite código do projeto, não comece a implementação. O arquivo precisa
existir de fato em disco ao final — a fonte de verdade é o arquivo gravado,
nunca um resumo na resposta.

Termine a resposta com uma única linha:
`PLAN_RESULT: {"slug":"<slug>","steps":<número de passos em Order of work>,"note":"<resumo de uma linha>"}`

---

*Adaptado de `sdlc-plan` em plataforma-aes-learn, que segue o AI-native SDLC
descrito em Anthropic's "The AI-Native SDLC playbook". Unofficial; not
affiliated with or endorsed by Anthropic.*
