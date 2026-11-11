---
name: sdlc-intent
installer-group: factory
version: 1
description: >-
  Captures an idea, ticket or issue as a committed intent.md file — the
  problem, the proposed outcome, who and what it touches, the constraints,
  and what's still open. First file in the ai-native-sdlc chain
  (intent.md -> spec.md -> plan.md).
---

# Capture the intent

First file in the chain (`ai-native-sdlc`). It exists so that an idea stops
waiting on someone with the right job title to write it up, and so what
reaches implementation still resembles what the originator actually meant.

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

Todos os artefatos da cadeia vivem em **`.aes/ai-native-sdlc/<slug>/`** na raiz
do projeto — nunca no root do repositório:

```
.aes/ai-native-sdlc/<slug>/
├── intent.md
├── spec.md
└── plan.md
```

0. Confirme a raiz do projeto: o diretório que contém `AGENTS.md`,
   `CLAUDE.md` ou `.cursorrules` (em workspaces com `backend/`/`frontend/`,
   fica um nível acima, nunca dentro deles). Só se nenhum marcador existir,
   use o diretório que já contém `.aes/`; se nem isso existir, trate o
   diretório atual como raiz.
1. `<slug>` é o identificador da feature, em kebab-case, derivado do nome da
   feature ou da issue (ex.: `issue-42-registro-usuario`). Se
   `.aes/ai-native-sdlc/<slug>/` já existir, reutilize o slug.
2. Crie o diretório se faltar e salve o arquivo **obrigatoriamente** em
   `.aes/ai-native-sdlc/<slug>/intent.md`.

## The file

Cinco seções, nesta ordem — nada além do que ganha espaço de verdade:

```markdown
# Intent: <nome da feature>
Author: <quem pediu>. Status: draft.
## Problem
<o que não funciona hoje, com evidência>
## Proposed outcome
<o que fica diferente depois>
## Affected users and systems
<quem e o que é afetado>
## Constraints
<restrições conhecidas>
## Open questions
<o que ainda não foi decidido>
```

Leave open questions unresolved quando possível — resolvê-las aqui enterra
uma decisão que `sdlc-spec` deveria sinalizar deliberadamente.

## Interactive run (default)

Quando há um humano na sessão: descreva o problema, faça as perguntas de
escopo/usuários/restrições/sucesso, rascunhe o `intent.md`, releia com o
autor, corrija o que foi mal entendido, e só então grave o arquivo.

## App-orchestrated run

Se o prompt já informar um slug (de uma triagem anterior desta mesma issue),
use exatamente esse slug — nunca derive outro a partir do título. Isso é o
que mantém `triage.md` e `intent.md` da mesma issue na mesma pasta
`.aes/ai-native-sdlc/<slug>/`.

Quando o prompt diz que a execução é orquestrada pelo app (sem humano
observando), não faça a entrevista: responda você mesmo cada pergunta com a
melhor base disponível (título/corpo da issue, código existente,
`CLAUDE.md`/`AGENTS.md`, docs do repo). O que não puder ser decidido vai para
`## Open questions`, com a suposição adotada marcada como `(suposição)` —
nunca fica implícito. Nunca pare esperando resposta.

Faça só isto: grave `.aes/ai-native-sdlc/<slug>/intent.md` e PARE — não ative
`sdlc-spec` nem `sdlc-plan`, não peça confirmação, não comente na issue.

Termine a resposta com uma única linha:
`INTENT_RESULT: {"slug":"<slug>","title":"<título curto>","openQuestions":<número de perguntas em aberto>,"note":"<resumo de uma linha>"}`

---

*Adaptado de `sdlc-intent` em plataforma-aes-learn, que segue o AI-native SDLC
descrito em Anthropic's "The AI-Native SDLC playbook". Unofficial; not
affiliated with or endorsed by Anthropic.*
