# 08 — Working with Agentic Platforms (Kiro & Claude)

> Módulo **conceitual**. Enquanto os módulos 01–07 ensinam a *mecânica* de LLMs e
> agentes, aqui o foco é como você **trabalha com** plataformas de coding agents
> no dia a dia — a camada de *harness* que o mercado de 2025/26 valoriza tanto
> quanto a mecânica. Os conceitos são apresentados de forma neutra e ilustrados
> com Kiro e Claude Code.

## Modelo vs. Agente

- **Modelo** (ex: Mistral, GPT, Claude): gera texto a partir de um contexto. Sem estado, sem ação no mundo.
- **Agente**: um modelo dentro de um *loop* com **ferramentas**, **memória/contexto** e **guardrails** — ele age, observa o resultado e decide o próximo passo (é o padrão ReAct do Módulo 02, levado a produto).

## Os eixos de extensibilidade

Plataformas como Claude Code e Kiro expõem mecanismos parecidos para estender o
comportamento do agente sem reescrever o núcleo:

### 1. Skills
Procedimentos reutilizáveis empacotados como arquivos **`SKILL.md`** (instruções +
descrição + recursos de apoio). O agente **carrega a skill sob demanda** quando a
tarefa é relevante — transforma um generalista num especialista.
- **Problema que resolve:** *alinhamento* ("faça do nosso jeito") e *reuso* (não
  reexplicar o mesmo procedimento a cada sessão).
- Analogia direta: tanto o Kiro quanto o Claude usam skills baseadas em markdown
  em disco, descobertas e lidas quando casam com a tarefa.

### 2. Hooks
**Callbacks disparados por eventos do ciclo de vida do agente** — uma ferramenta
sendo chamada, uma sessão iniciando, a execução parando. Permitem automação
*determinística* (ex: rodar um formatador ao salvar, validar antes de um commit)
sem depender do modelo "lembrar" de fazer.
- **Problema que resolve:** garantir passos obrigatórios de forma confiável, fora
  do não-determinismo do LLM.

### 3. Specs / Steering (contexto persistente)
Dar ao agente **intenção e contexto antes de ele agir**: uma *spec* como artefato
prévio (ver Módulo 07 — SDD) ou arquivos de *steering*/instruções de projeto
(ex: `CLAUDE.md`, regras de projeto). É engenharia de contexto aplicada ao
workflow (Módulo 03.5).

### 4. MCP Tools
Como o agente ganha **capacidades novas** de forma padronizada (ver Módulo 02 —
MCP). Expor um sistema como MCP server dá ao agente ferramentas sem acoplar o
wiring a um projeto específico.

### 5. Subagents / Orquestração
**Delegar trabalho paralelo** a agentes auxiliares (ex: pesquisar, revisar e
implementar em paralelo), consolidando os resultados. Escala o que um único loop
sequencial não dá conta.

## Quando ensinar algo ao agente (skill) vs. criar outro agente (subagent)?

- **Skill**: é *conhecimento/procedimento* que o mesmo agente deve aplicar quando
  o assunto aparece. "Como fazer X do nosso jeito."
- **Subagent**: é *trabalho independente* que vale isolar — contexto próprio,
  pode rodar em paralelo, resultado volta consolidado. "Faça Y enquanto eu sigo."

## Por que isso importa no mercado

Saber *construir* um RAG é cada vez mais commodity. O diferencial sênior é saber
**operar agentes com disciplina**: alinhá-los com skills, torná-los confiáveis com
hooks, guiá-los com specs e escalá-los com subagents. É a diferença entre "usar IA
para autocompletar" e "engenheirar software com agentes".

## Referências (verificadas)

- Anthropic — Hooks (Agent SDK): https://platform.claude.com/docs/en/agent-sdk/hooks
- Anthropic — Agent Skills (SDK): https://platform.claude.com/docs/en/agent-sdk/skills
- Anthropic — Equipping agents with Agent Skills: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Material do curso Dev-IA (UFCG): https://joaoarthurbm.github.io/dev-ia/
