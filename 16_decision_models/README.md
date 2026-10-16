# 16 — Modelos de decisão ("System One"): decisões tipadas e calibradas

> Pré-requisitos: a parte central (`decision_model`, `calibration`, `routing`) roda **sem LLM, sem rede e sem chave** — só `numpy`. O embedder padrão de `decision_model` usa `sentence-transformers` (baixa um modelo pequeno uma vez); nos testes e nos demos de `routing`/`calibration` um embedder falso determinístico substitui isso. O cliente real do Jev (`jev_client.py`) é opcional e só roda se você tiver uma chave da TypeSafe.

Um agente de verdade não é só um LLM gerando texto: ele toma **decisões** o tempo todo — qual rota seguir, se o resultado é confiável, se precisa buscar de novo. Este módulo mostra como tratar essas decisões como o que elas são: perguntas **tipadas** com respostas **tipadas e probabilidades calibradas**, em vez de forçar um modelo de texto a "responder em JSON".

## Por que importa

### System 1 vs System 2 dentro de um agente
A metáfora (de Kahneman) separa dois modos de pensar: o **System 2** é lento, deliberado, caro — é o LLM raciocinando passo a passo, gerando texto. O **System 1** é rápido, automático, barato — é a decisão instantânea "isso é perigoso?", "qual destes rótulos?". Num agente, a maior parte das decisões é System 1: elas não precisam de uma redação, precisam de **um rótulo e uma probabilidade**. Usar um LLM gerador para isso é usar o System 2 onde o System 1 bastaria — mais lento, mais caro e, pior, **sem uma noção honesta de incerteza**.

### Por que coagir um LLM a decidir via JSON é frágil
No [`10_structured_output`](../10_structured_output/README.md) a gente viu o padrão de pedir JSON ao LLM e **validar + repetir** (`retry_parser.py`) quando ele quebra o schema. Isso funciona, mas trata um sintoma: o LLM foi treinado para gerar texto plausível, não para produzir uma distribuição de probabilidade calibrada. O JSON pode vir bem-formado e ainda assim o modelo estar "chutando com confiança". Não há um número honesto de "quão certo eu estou" — a temperatura do sampling não é calibração.

### O que muda com decisão tipada + probabilidade calibrada
Um **modelo de decisão** (System One) recebe um `state` + perguntas tipadas e devolve, para cada pergunta, a resposta **e** a distribuição de probabilidade sobre as opções, mais um `confidence` derivado dessa distribuição. Isso dá duas coisas que o JSON coagido não dá:
- **a forma da distribuição** diz se o modelo está decidido (massa numa opção) ou em cima do muro (massa espalhada);
- **calibração**: se o modelo diz "0.8", a resposta é certa ~80% das vezes — e isso é mensurável e corrigível (ver [Calibração](#calibração)).

Com isso o **código** volta a mandar: ele age sozinho quando a confiança é alta e escala para um LLM ou humano quando é baixa, com um limiar que você escolhe pelo risco.

## Conceitos

As três primitivas (perguntas), espelhando a API do Jev da TypeSafe:

| Primitiva | Pergunta | Devolve | Aplicada à base de CVEs |
| - | - | - | - |
| **Choice** | Escolher 1 opção de uma lista | `choice`, `probabilities`, `confidence` | **severidade** (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) |
| **Noul** | A afirmação é verdadeira? | `noul` (0 a 1) | **"é exploração remota?"** |
| **Score** | Pontuar o state numa rubrica ordenada | `score`, `probabilities`, `confidence` | **groundedness** 1–5, como o LLM-as-judge do [`06_evals`](../06_evals/README.md) — mas tipado e calibrado |

Várias perguntas vão numa **só chamada**, avaliadas em paralelo e isoladas contra o mesmo `state`. A doc da TypeSafe recomenda perguntas **atômicas** compostas em código (decompor e recombinar com a sua fórmula) — é o padrão de *composite scoring* abaixo.

### Confiança (`confidence`)
É um resumo 0–1 da forma da distribuição: **1** quando toda a massa está numa opção, **0** quando está espalhada igualmente. Para Choice e Score o baseline local usa **a mesma fórmula** documentada pela TypeSafe, então um resultado local é comparável a um resultado real do Jev. Noul não carrega `confidence` separado: a própria probabilidade já carrega a incerteza (perto de 0.5 = inseguro), e a "confiança" dele é a distância de 0.5.

### Padrões aplicados
- **Speculative fan-out**: manda várias perguntas (inclusive especulativas) numa chamada e deixa o código decidir o que importa.
- **Confidence-gated routing**: a resposta diz *o quê*; a confiança diz *se* você deve agir. Abaixo do limiar, escala.
- **Composite scoring**: quebra um julgamento complexo em `Score`/`Noul` atômicos e combina com **pesos que você controla no código**.
- **Intent routing**: classifica a requisição e manda para o handler certo (lógica determinística, LLM especialista ou humano).

## Arquivos

- [`decision_model.py`](./decision_model.py) — baseline **local** com o contrato System One (state + `Choice`/`Score`/`Noul` → respostas tipadas com probabilidades). Protótipos de embedding + softmax com temperatura; **embedder injetável** (padrão: `utils.semantic_embeddings.embed_texts`; nos testes, um falso determinístico — nunca baixa modelo nos testes).
- [`calibration.py`](./calibration.py) — Brier score, ECE, tabela de confiabilidade por faixa e ajuste de **temperatura** (temperature scaling) num split de calibração.
- [`routing.py`](./routing.py) — confidence-gated routing (agir se `p >= limiar`, senão escalar; curva **cobertura × acurácia** por limiar) e **composite scoring** (perguntas atômicas combinadas em código).
- [`jev_client.py`](./jev_client.py) — cliente **opcional** do Jev real (HTTP via `urllib`, sem dependência nova; import tardio; nunca usado nos testes). Verificado contra a doc oficial (ver [Referências](#referências)).
- [`labeled_cases.json`](./labeled_cases.json) — 32 casos rotulados **sintéticos** de vulnerabilidades (rótulos: `type` com `VulnerabilityType`, `severity` com `SeverityLevel`, `remote_exploit` sim/não).

## Como rodar

A partir da **raiz do repositório**, com `PYTHONPATH=.`:

```bash
# baseline local sobre um CVE real (usa o embedder de verdade; baixa um modelo pequeno 1x)
python -m 16_decision_models.decision_model

# calibração: um modelo superconfiante e o efeito do temperature scaling (offline)
python -m 16_decision_models.calibration

# roteamento por confiança + composite scoring (offline, embedder falso)
python -m 16_decision_models.routing

# cliente real do Jev — só roda se TYPESAFE_API_KEY estiver no ambiente
python -m 16_decision_models.jev_client
```

## O que a demo mostra

### `calibration.py` (saída real, offline)
Um modelo sintético **superconfiante** (temperatura 1.0) e o mesmo modelo após achar a temperatura que minimiza o Brier. A acurácia não muda (o scaling preserva o ranking); o Brier e o ECE despencam:

```
Before (temperature = 1.0):
  accuracy : 0.978
  Brier    : 0.2577
  ECE      : 0.4854

Fitted temperature: 0.25
After (temperature = 0.25):
  accuracy : 0.978  (unchanged -- scaling preserves ranking)
  Brier    : 0.0258
  ECE      : 0.0797
```

### `routing.py` (saída real, offline)
A curva **cobertura × acurácia**: subir o limiar de confiança age em menos casos, mas acerta mais entre os que age.

```
Coverage/accuracy as the confidence threshold rises:
  thr  coverage  accuracy  acted/total
  0.0      1.00      0.80  5/5
  0.1      0.80      1.00  4/5
  0.2      0.00      0.00  0/5
```

### `decision_model.py` (saída real, embedder de verdade)
```
severity (Choice): MEDIUM  confidence=0.02
    MEDIUM    0.262
    CRITICAL  0.254
    LOW       0.245
    HIGH      0.239
remote_exploit (Noul): P(yes)=0.504
groundedness (Score): 0.99 confidence=0.00
```

> **Leia a confiança baixa como o recado principal, não como um bug.** Este baseline usa um embedder genérico (`all-MiniLM-L6-v2`) + cosseno cru, sem nenhum treino para a tarefa — então as distribuições saem quase uniformes e o `confidence` sai perto de 0. É *justamente* por isso que calibração e confidence-gating existem: um modelo honesto que não sabe **diz** que não sabe (confiança baixa → escala), em vez de cravar um rótulo errado com cara de certeza. O Jev de verdade é um modelo **treinado** para decisão calibrada (RLCD, alegação do fornecedor abaixo); o baseline local demonstra o *contrato e os mecanismos*, não a qualidade de um modelo treinado.

## O Jev como produto (fatos datados; alegações marcadas)

- **Jev** é o modelo da **TypeSafe AI** e, segundo a empresa, o primeiro "System One model". Lançado em **15/09/2026**; proprietário.
- Um System One model **não gera texto**: recebe um `state` + perguntas tipadas e devolve resultados tipados com distribuições de probabilidade; Choice e Score devolvem `confidence`.
- **Endpoint/contrato** (lido na doc oficial): `POST https://api.typesafe.ai/v1/systemone`, auth `Authorization: Bearer <API_KEY>` (chave em `TYPESAFE_API_KEY`), corpo `{state, model, questions}`, resposta `{model, answers, usage}`. É o que `jev_client.py` fala — nada aqui foi inventado.
- Treino, **segundo o site**: "Reinforcement Learning for Calibrated Decisions (RLCD)".
- Preço no site: **US$ 42 por bilhão de tokens de entrada**. A cobertura do lançamento informa **saída gratuita** e **~100 ms por chamada**.
- *"Zero Hallucinations"* e *"193.6x faster, 444.6x cheaper"* são **alegações do fornecedor** — reproduzidas como alegação, não verificadas aqui.

## Ligações com outros módulos

- [`06_evals`](../06_evals/README.md): o `Score` de groundedness tipado é o LLM-as-judge **com um número de confiança calibrado**, não um juiz-LLM aproximado.
- [`09_guardrails`](../09_guardrails/README.md): um **classificador** calibrado (Noul/Choice) com limiar é mais robusto que regex para "isso é malicioso?" — e sabe dizer quando está em dúvida.
- [`10_structured_output`](../10_structured_output/README.md): a alternativa ao "coagir LLM a JSON + validar/retry" — aqui a saída tipada **é** o contrato.
- [`12_agentic_rag`](../12_agentic_rag/README.md): a decisão "buscar de novo?" vira um `Noul` com confidence-gating em vez de uma heurística/LLM.
- `15_token_economy` (custo): decisões System One são baratas e rápidas; roteamento por confiança usa o LLM caro só quando a confiança é baixa.

## Exercícios

1. Troque o embedder falso do demo de `routing.py` pelo `embed_texts` real e observe como a curva cobertura × acurácia muda. Onde você poria o limiar para severidade `CRITICAL` (ação cara) vs `LOW` (ação barata)?
2. Em `calibration.py`, implemente **Platt scaling** (sigmoide ajustada) como alternativa ao temperature scaling e compare Brier/ECE no mesmo split.
3. Monte um `composite_score` de "risco" a partir de três perguntas atômicas (`Choice` severidade, `Noul` remoto, `Score` facilidade de exploração) e justifique os pesos.
4. Use `coverage_accuracy_curve` sobre `labeled_cases.json` (com o embedder real) e escolha o limiar que dá ≥ 95% de acurácia nas ações automáticas; qual cobertura isso custa?
5. Com uma chave real, rode `jev_client.py` sobre 5 casos do `labeled_cases.json` e compare `confidence` do Jev com o do baseline local nos mesmos casos.

## Referências

- TypeSafe — Introduction: <https://docs.typesafe.ai/introduction>
- TypeSafe — Quick start (endpoint, auth, request/response): <https://docs.typesafe.ai/introduction/quickstart>
- TypeSafe — API reference (campos de request/response, erros): <https://docs.typesafe.ai/api.md>
- TypeSafe — Confidence (fórmulas de Choice/Score/Noul): <https://docs.typesafe.ai/confidence.md>
- TypeSafe — índice da doc: <https://docs.typesafe.ai/llms.txt>
- Site da TypeSafe: <https://typesafe.ai>
- Wikipedia — Jev (AI model), data de lançamento: <https://en.wikipedia.org/wiki/Jev_(AI_model)>
- Cobertura do lançamento (saída gratuita, ~100 ms, preço): <https://flaviocopes.com/jev/>
