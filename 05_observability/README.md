# 05 — Observabilidade (LangSmith e Langfuse)

> Pré-requisitos: **não roda offline** — os dois scripts só fazem algo útil com um LLM.
> A parte central precisa de um LLM via `utils.llm_client` (Ollama local por padrão; veja
> [../LLM_SETUP.md](../LLM_SETUP.md)). Para que os traces cheguem às plataformas você também
> precisa de chaves: LangSmith (`LANGCHAIN_API_KEY`) e/ou Langfuse
> (`LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`). Sem LLM, os scripts degradam com mensagem
> instrutiva (não travam). O Langfuse ainda precisa do pacote `langfuse` instalado.

Observabilidade é como você enxerga o que um agente fez por dentro: qual passo rodou, quanto
tempo levou, quantos tokens gastou e onde errou. Este módulo mostra duas ferramentas que
instrumentam aplicações LLM — **LangSmith** (nativa do ecossistema LangChain) e **Langfuse**
(open-source, funciona com qualquer provedor) — rodando sobre a mesma base de CVEs dos outros
módulos.

## Por que importa

Em produção, uma resposta errada ou lenta de um agente é quase impossível de depurar sem
instrumentação. Observabilidade resolve isso dando visibilidade sobre:

- O fluxo de execução do agente (quais nós/passos rodaram e em que ordem)
- Falhas e gargalos (qual passo demorou ou estourou)
- Latência e uso de tokens (e, com isso, custo)
- Feedback do usuário (scores, anotações)
- Comparação entre versões (prompts, modelos, parâmetros)

## Conceitos

### Trace (rastro)
Uma execução completa do seu sistema, do input ao output final. Um trace agrupa vários spans.

```
User Query
    ↓ ┌─────────────────────── TRACE ──────────────────────┐
    ↓ │                                                      │
    ├─→ [Span 1: Parse Query]                               │
    │   ↓                                                    │
    ├─→ [Span 2: Search Vector DB]                          │
    │   ↓                                                    │
    ├─→ [Span 3: Call LLM with Context]                     │
    │   ↓                                                    │
    ├─→ [Span 4: Format Response]                           │
    ↓ │                                                      │
Final Output                                                │
    └──────────────────────────────────────────────────────┘
```

### Span (operação)
Uma operação dentro do trace, com seu próprio input, duração, output e status.

```
Span: "search_vector_db"
├─ Input: {"query": "SQL injection", "top_k": 5}
├─ Duration: 234ms
├─ Output: [{"id": "vuln_1", "score": 0.94}, ...]
└─ Status: Success
```

### Análise de latência
Somando a duração dos spans você vê onde está o gargalo — tipicamente a chamada ao LLM.

```
Total: 2.45s
├─ Vector DB Search: 234ms (10%)
├─ LLM Call: 1800ms (73%)  ← Gargalo!
├─ Post-processing: 120ms (5%)
└─ Network: 291ms (12%)
```

### Uso de tokens (e custo)
Tokens de entrada e de saída por trace; o custo sai de `tokens × preço por token` do provedor.

```
Input Tokens: 450
├─ System Prompt: 120
├─ Context (from DB): 180
└─ User Query: 150

Output Tokens: 320

Total: 770 tokens
```

> Os números acima são **ilustrativos** (exemplos didáticos de leitura de um dashboard), não a
> saída dos scripts deste módulo. Preços variam por provedor e modelo — consulte a página de
> preços oficial (ex.: [OpenAI Pricing](https://openai.com/api/pricing/)).

### LangSmith × Langfuse

| | LangSmith | Langfuse |
|---|-----------|----------|
| Integração | Automática com LangChain/LangGraph | OpenAI-compatível e qualquer stack |
| Código | Zero instrumentação extra (liga por env var) | Wrapper/decorador, mais controle manual |
| Hospedagem | SaaS (dados vão para servidores LangChain) | Cloud **ou** self-hosted (open-source) |
| Feedback | Sim | Sim (scores/evaluators explícitos) |
| Trade-off | Simples, mas vendor lock-in | Flexível, mas setup maior se self-hosted |

## Arquivos

### `langsmith_demo.py` — tracing automático do LangChain
Monta uma chain LCEL simples (`ChatPromptTemplate | llm`) com o modelo de chat de
`utils.llm_client` e o template `ASSISTANT_QA_SYSTEM` de `utils.prompts`, e roda os exemplos de
`utils.agentic_utils.get_cve_qa_examples()` (um por CVE da base). Quando o tracing do LangSmith
está ligado, **cada `chain.invoke` é rastreado automaticamente** — nenhuma instrumentação no
código. O script imprime os valores de `LANGCHAIN_TRACING_V2`/`LANGCHAIN_PROJECT` que leu do
ambiente e, no fim, diz se o tracing está ligado (`LANGCHAIN_TRACING_V2=true`) ou não.

O gatilho do tracing é a função `tracing_enabled()`, que só retorna `True` quando
`LANGCHAIN_TRACING_V2` vale exatamente `"true"`.

### `langfuse_demo.py` — experimento com evaluators (Langfuse)
Usa o **SDK moderno do Langfuse** (v3+): `get_client()` para o cliente e
`langfuse.openai.OpenAI` como wrapper drop-in que transforma cada chamada de completion em uma
*generation* no dashboard. O cliente aponta para o endpoint do `.env` (Ollama por padrão), então
o mesmo switch de provedor dos outros módulos vale aqui.

A demo monta um dataset local a partir de `get_cve_qa_examples()` (campos `input`/`expected`) e
roda `langfuse_client.run_experiment(...)` com dois evaluators de item:

- `evaluate_accuracy`: a resposta contém a palavra-chave esperada? (score 0/1)
- `evaluate_response_length`: o tamanho da resposta está na faixa aceitável?

e dois run-evaluators de agregação (`evaluate_average_accuracy`,
`evaluate_average_response_length`). No fim chama `langfuse_client.flush()` para garantir que
traces e scores sejam enviados antes do processo terminar.

> Os dois scripts têm `def main()` e `if __name__ == "__main__": main()` — **nada roda no
> import**, então você pode importá-los nos testes sem disparar chamadas de rede.

## Como rodar

A partir da raiz do repositório, com o `PYTHONPATH` apontando para a raiz:

**PowerShell (Windows):**
```powershell
$env:PYTHONPATH = "."
python -m 05_observability.langsmith_demo
python -m 05_observability.langfuse_demo
```

**Bash (Linux/macOS):**
```bash
export PYTHONPATH="."
python -m 05_observability.langsmith_demo
python -m 05_observability.langfuse_demo
```

Setup de provedor de LLM (Ollama / LM Studio / OpenAI): [../LLM_SETUP.md](../LLM_SETUP.md).

### Configuração do LangSmith
O LangSmith liga por variáveis de ambiente, lidas direto pela biblioteca (não passam pelo
`utils.config.Settings`). Coloque-as no `.env`:

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=sua-chave
LANGCHAIN_PROJECT=llm-study
```

> O código deste módulo lê `LANGCHAIN_TRACING_V2`/`LANGCHAIN_PROJECT`. A documentação atual da
> LangChain usa os nomes `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT`; os
> nomes antigos `LANGCHAIN_*` continuam funcionando. Crie a conta e a chave em
> [smith.langchain.com](https://smith.langchain.com).

### Configuração do Langfuse
O pacote `langfuse` já vem no `requirements.txt`. Configure as credenciais no `.env`:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com   # região EU; US: https://us.cloud.langfuse.com
```

- **Cloud:** crie a conta em [cloud.langfuse.com](https://cloud.langfuse.com) e copie as chaves.
- **Self-hosted (open-source):** veja o guia oficial em
  [langfuse.com/self-hosting](https://langfuse.com/self-hosting). O `LANGFUSE_BASE_URL` aponta
  para a sua instância.
- O SDK ainda aceita o nome antigo `LANGFUSE_HOST`, marcado como obsoleto em favor de
  `LANGFUSE_BASE_URL`.

## O que a demo mostra

Nesta máquina o Ollama estava **desligado** e sem chaves configuradas. As saídas abaixo são as
execuções reais (exit=0 nos dois casos — os scripts degradam, não quebram).

### `langsmith_demo.py`
Sem LLM, cada chamada da chain falha com erro de conexão, e o script reporta que o tracing está
desligado:

```
LangSmith Integration with Local LLM

LANGCHAIN_TRACING_V2: None
LANGCHAIN_PROJECT: None

================================================================================
Processing 3 examples...

(1) Remote code execution vulnerability in WebServer v2.1. An unauthenticated attack...
    Error: Connection error.

(2) SQL injection vulnerability in AuthService v1.5 authentication module. The vulne...
    Error: Connection error.

(3) Cryptographic weakness in DataEncryption library v3.2. The implementation uses a...
    Error: Connection error.

================================================================================
Tracing is OFF: set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in .env.
```

Com o Ollama ligado, as linhas `Error: Connection error.` dão lugar ao início da resposta do
modelo (truncada em 80 caracteres); com `LANGCHAIN_TRACING_V2=true` e a chave, cada execução
aparece como um trace no painel do LangSmith.

### `langfuse_demo.py`
O experimento processa os 3 exemplos; sem LLM, não há saída para avaliar, então o resultado fica
vazio (e o agregado dispara erros de score, porque a média de uma lista vazia é `None`):

```
Running Langfuse Experiment with Evaluators

Testing 3 queries with mistral + Evaluators

  Processing: Remote code execution vulnerability in WebServer v...
  Processing: SQL injection vulnerability in AuthService v1.5 au...
  Processing: Cryptographic weakness in DataEncryption library v...

================================================================================
Experiment with Evaluators completed!

No experiment results to display.

================================================================================
Results sent to Langfuse (see the experiment in your project).
```

O stderr mostra que os run-evaluators tentaram enviar um score `None` e o Langfuse recusou
(`CreateScoreRequest` exige número): consequência direta de rodar sem LLM. Com o modelo ligado, cada pergunta é respondida, os evaluators são aplicados a cada resposta e o
`result.format()` imprime a tabela de scores.

## Exercícios

1. **Ligue o tracing sem rodar o LLM remoto.** Defina `LANGCHAIN_TRACING_V2=true` no ambiente e
   rode `langsmith_demo.py` com o Ollama **desligado**. Observe que `tracing_enabled()` passa a
   `True` e a mensagem final muda, mesmo com as chamadas ainda falhando por conexão. Qual é a
   consequência de ter tracing ligado mas o LLM indisponível?
2. **Adicione um evaluator ao Langfuse.** Escreva um novo evaluator de item em `langfuse_demo.py`
   (ex.: `evaluate_mentions_cve` que dá 1.0 se a resposta cita um identificador `CVE-`) e some-o
   à lista `evaluators=[...]` de `run_experiment`. O SDK chama cada evaluator de item com
   argumentos nomeados, então use a assinatura `def evaluate_mentions_cve(*, input, output,
   expected_output=None, metadata=None, **kwargs)`. Rode com o Ollama ligado e veja o novo score
   na tabela de `result.format()`.
3. **Explique o resultado vazio.** A partir do código de `evaluate_average_accuracy`, explique
   por que, sem LLM, o experimento imprime `No experiment results to display` e os
   run-evaluators disparam erro de validação de score. Que guarda você adicionaria para que uma
   execução sem respostas não gere o erro?
4. **Troque o provedor.** Aponte `OLLAMA_BASE_URL` para o LM Studio (porta `1234`) ou para a
   OpenAI e confirme que os **dois** scripts passam a chamar o novo endpoint sem mudar código —
   só o `.env`. Veja [../LLM_SETUP.md](../LLM_SETUP.md).
5. **Compare as duas abordagens.** Rode os dois scripts com tracing/credenciais configurados e
   compare: no LangSmith o trace nasce automático da chain LCEL; no Langfuse ele nasce do wrapper
   `langfuse.openai.OpenAI` + `run_experiment`. Qual exige menos código? Qual dá mais controle
   sobre o que vira span?

## Referências

Fontes oficiais lidas ao escrever este README:

- [Trace LangChain applications — LangSmith](https://docs.smith.langchain.com/observability/how_to_guides/trace_with_langchain)
- [Experiments via SDK — Langfuse](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [Setup do SDK Python — Langfuse](https://langfuse.com/docs/observability/sdk/python/setup)
- [Documentação do LangSmith](https://docs.smith.langchain.com/)
- [Documentação do Langfuse](https://langfuse.com/docs)
- [Self-hosting do Langfuse](https://langfuse.com/self-hosting)
