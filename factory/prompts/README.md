# Prompts das etapas

Cada arquivo aqui é o "o que fazer" de uma etapa. Ele é colado no pedido do agente ou da skill
da etapa, logo depois das linhas `Read:` e `Write:` que o motor monta. Edite à vontade: a próxima
etapa que rodar já usa o texto novo.

Para ligar um prompt a uma etapa, aponte `prompt:` dela em `factory/pipeline.yaml`:

```yaml
  prd:
    run: { agent: doc-writer, model: opus }
    prompt: factory/prompts/prd.md
```

Instruções só de uma tarefa não ficam aqui: vão em `factory/tasks/<KEY>.yaml` (campo `notes` da
etapa), que a tela grava em "Instruções extras".
