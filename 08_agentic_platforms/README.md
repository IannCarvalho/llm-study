# 08 — Plataformas agênticas (Kiro e Claude)

> Pré-requisitos: módulo **conceitual** — não tem código, não precisa de LLM nem de chave.
> Os exercícios usam o agente de sua preferência (Kiro, Claude Code ou outro).

Enquanto os módulos 01–07 ensinam a *mecânica* de LLMs e agentes, aqui o foco é como você
**trabalha com** plataformas de coding agents no dia a dia — a camada de *harness* que o mercado
de 2025/26 valoriza tanto quanto a mecânica. Os conceitos são apresentados de forma neutra e
ilustrados com Kiro e Claude Code.

## Por que importa

Saber *construir* um RAG é cada vez mais commodity. O diferencial sênior é saber
**operar agentes com disciplina**: alinhá-los com skills, torná-los confiáveis com hooks,
guiá-los com specs e escalá-los com subagents. É a diferença entre "usar IA para
autocompletar" e "engenheirar software com agentes".

## Conceitos

### Modelo vs. agente

- **Modelo** (ex.: Mistral, GPT, Claude): gera texto a partir de um contexto. Sem estado, sem
  ação no mundo.
- **Agente**: um modelo dentro de um *loop* com **ferramentas**, **memória/contexto** e
  **guardrails** — ele age, observa o resultado e decide o próximo passo (é o padrão ReAct do
  [módulo 02](../02_agentic_ai_basics/README.md), levado a produto).

### Os eixos de extensibilidade

Plataformas como Claude Code e Kiro expõem mecanismos parecidos para estender o comportamento
do agente sem reescrever o núcleo. Na documentação do Kiro eles aparecem como Specs, Steering,
Hooks, MCP, Skills e Sub-agents ([kiro.dev/docs](https://kiro.dev/docs/)).

#### 1. Skills
Procedimentos reutilizáveis empacotados como arquivos **`SKILL.md`** (instruções + descrição +
recursos de apoio). O agente **carrega a skill sob demanda** quando a tarefa é relevante —
transforma um generalista num especialista.
- **Problema que resolve:** *alinhamento* ("faça do nosso jeito") e *reuso* (não reexplicar o
  mesmo procedimento a cada sessão).
- Analogia direta: tanto o Kiro quanto o Claude usam skills baseadas em markdown em disco,
  descobertas e lidas quando casam com a tarefa.

#### 2. Hooks
**Callbacks disparados por eventos do ciclo de vida do agente** — uma ferramenta sendo chamada,
uma sessão iniciando, a execução parando. Permitem automação *determinística* (ex.: rodar um
formatador ao salvar, validar antes de um commit) sem depender do modelo "lembrar" de fazer.
- **Problema que resolve:** garantir passos obrigatórios de forma confiável, fora do
  não-determinismo do LLM.

#### 3. Specs / Steering (contexto persistente)
Dar ao agente **intenção e contexto antes de ele agir**: uma *spec* como artefato prévio (ver o
[módulo 07 — SDD](../07_sdd/README.md)) ou arquivos de *steering*/instruções de projeto (ex.:
`CLAUDE.md`, o steering do Kiro, regras de projeto). É engenharia de contexto aplicada ao
workflow (Day 3.5 — Context Engineering, no [roteiro do README raiz](../README.md#roteiro-de-estudo)).

#### 4. MCP Tools
Como o agente ganha **capacidades novas** de forma padronizada (o MCP também está no
[roteiro do README raiz](../README.md#roteiro-de-estudo)). Expor um sistema como MCP server dá
ao agente ferramentas sem acoplar o wiring a um projeto específico.

#### 5. Subagents / orquestração
**Delegar trabalho paralelo** a agentes auxiliares (ex.: pesquisar, revisar e implementar em
paralelo), consolidando os resultados. Escala o que um único loop sequencial não dá conta.

### Skill ou subagent?

Quando ensinar algo ao agente (skill) e quando criar outro agente (subagent):

- **Skill**: é *conhecimento/procedimento* que o mesmo agente deve aplicar quando o assunto
  aparece. "Como fazer X do nosso jeito."
- **Subagent**: é *trabalho independente* que vale isolar — contexto próprio, pode rodar em
  paralelo, resultado volta consolidado. "Faça Y enquanto eu sigo."

## Arquivos

| Arquivo | Conteúdo |
|---------|----------|
| [README.md](README.md) | Este texto. O módulo é só leitura, sem scripts. |

## Como rodar

Não há script neste módulo. Para os exercícios, abra um clone deste repositório num agente com
suporte a skills e hooks (Kiro, Claude Code ou equivalente).

## O que a demo mostra

Não há demo executável aqui. Os mecanismos discutidos aparecem em outros módulos do repo:

- o loop agente + ferramentas: [02_agentic_ai_basics](../02_agentic_ai_basics/README.md)
  (`tool_use.py`, `react_pattern.py`);
- a spec como artefato antes do código: [07_sdd](../07_sdd/README.md)
  (`spec_driven_analysis.py`, [spec_example.md](../07_sdd/spec_example.md));
- regras determinísticas fora do modelo: [09_guardrails](../09_guardrails/README.md).

## Exercícios

1. **Escreva uma skill.** Transforme as convenções do [CONTRIBUTING.md](../CONTRIBUTING.md) para
   criar um módulo novo num `SKILL.md`, com descrição e instruções. Que descrição faria o agente
   carregá-la só quando a tarefa for "criar um módulo"?
2. **Desenhe um hook.** Qual evento do ciclo de vida e qual comando garantiriam que
   `ruff check .` e `python -m pytest tests -q` rodem antes de o agente dar uma tarefa por
   concluída? Por que isso funciona melhor como hook do que como instrução no prompt?
3. **Skill, hook ou subagent?** Classifique e justifique: (a) revisar 10 PRs independentes;
   (b) aplicar o template de README a um módulo; (c) formatar o código toda vez que um arquivo é
   salvo; (d) pesquisar a documentação oficial de uma biblioteca antes de escrever sobre ela.
4. **Steering do repositório.** Escreva um arquivo de instruções de projeto (um `CLAUDE.md` ou
   um steering do Kiro) para este repo: como rodar os módulos (`PYTHONPATH`), por que os
   diretórios que começam com dígito não são importáveis com `import`, e a regra de que os
   testes não usam rede.
5. **Spec vs. steering.** No [spec_example.md](../07_sdd/spec_example.md) do módulo 07, separe o
   que é intenção de uma tarefa (spec) do que é regra permanente do projeto (steering).

## Referências

- [Anthropic — Hooks (Agent SDK)](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [Anthropic — Agent Skills (Agent SDK)](https://platform.claude.com/docs/en/agent-sdk/skills)
- [Anthropic — Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Kiro — Documentação (specs, steering, hooks, MCP, skills, sub-agents)](https://kiro.dev/docs/)
- [Material do curso Dev-IA (UFCG)](https://joaoarthurbm.github.io/dev-ia/)
