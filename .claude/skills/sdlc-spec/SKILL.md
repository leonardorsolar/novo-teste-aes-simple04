---
name: sdlc-spec
installer-group: factory
version: 1
description: >-
  Turns an accepted intent.md into a committed spec.md — requirements and
  design, with every unresolved conflict between policies/requirements
  flagged instead of silently decided. Second file in the ai-native-sdlc
  chain (intent.md -> spec.md -> plan.md).
---

# From intent to spec

Second file in the chain (`ai-native-sdlc`). Requirements and design used to
be separate phases; here it's one pass, and conflicts are surfaced instead of
quietly resolved.

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
1. `<slug>` é o mesmo do `intent.md` de origem — **nunca crie um slug novo**
   pro spec. Se houver ambiguidade (mais de um `intent.md` em
   `.aes/ai-native-sdlc/`), pare e peça esclarecimento (ou, em execução
   orquestrada pelo app, use o slug que o prompt já informou).
2. Leia `.aes/ai-native-sdlc/<slug>/intent.md`. Se não existir, isso é
   bloqueio evidenciado — avise que falta rodar `sdlc-intent` primeiro e pare,
   sem inventar um intent.

## What the spec contains

1. Leia `intent.md` e explore o código existente relevante, pra que o design
   seja deste codebase, não abstrato.
2. Produza a especificação de requisitos e design.
3. Inclua **obrigatoriamente** uma seção `## Pontos de atenção e conflitos`:
   liste cada lugar em que dois requisitos não podem ser satisfeitos juntos,
   cada incógnita ainda aberta (carregada do `intent.md` ou nova), e cada
   decisão que cabe a alguém que não está na sessão. **Nunca escolha um
   vencedor em silêncio** — uma seção vazia só é válida se você de fato
   comparou intent × código e não achou conflito algum (diga isso
   explicitamente, não deixe a seção simplesmente em branco).
4. Salve **obrigatoriamente** em `.aes/ai-native-sdlc/<slug>/spec.md`, ao
   lado do `intent.md`.

## Interactive run (default)

Quando há um humano na sessão: escreva o spec, releia com ele, resolva os
pontos de atenção com os donos de cada lado antes de considerar aceito.

## App-orchestrated run

Se o prompt já informar um slug, use exatamente esse slug, não derive outro.

Quando o prompt diz que a execução é orquestrada pelo app (sem humano
observando), decida você mesmo os pontos de atenção que tiverem base nos
insumos disponíveis (intent.md, código, `CLAUDE.md`/`AGENTS.md`); o que não
tiver base nenhuma entra na seção de conflitos como pendente, com o motivo —
nunca pare esperando resposta.

Faça só isto: grave `.aes/ai-native-sdlc/<slug>/spec.md` e PARE — não ative
`sdlc-plan`, não peça confirmação. O arquivo precisa existir de fato em disco
ao final — a fonte de verdade é o arquivo gravado, nunca um resumo na
resposta.

Termine a resposta com uma única linha:
`SPEC_RESULT: {"slug":"<slug>","openConflicts":<número de pontos de atenção/conflitos listados>,"note":"<resumo de uma linha>"}`

---

*Adaptado de `sdlc-spec` em plataforma-aes-learn, que segue o AI-native SDLC
descrito em Anthropic's "The AI-Native SDLC playbook". Unofficial; not
affiliated with or endorsed by Anthropic.*
