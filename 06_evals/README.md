# 06 — Avaliação de LLM e Agentes (Evals)

> "Não dá pra melhorar o que não se mede." Os módulos anteriores *constroem*
> pipelines (RAG, agentes). Este módulo mostra como **medir se eles são bons** —
> a dobradinha natural da observabilidade (Módulo 05): tracing responde *o que
> aconteceu*; evals respondem *foi bom?*.

## Por que importa no mercado

Avaliar saída de LLM é um dos pontos mais cobrados em vagas de AI Engineering:
sem evals você não tem como comparar modelos, detectar regressão de prompt, nem
justificar uma mudança. Duas famílias se complementam e estão aqui:

| Abordagem | Precisa de LLM? | Determinística? | Para quê |
|-----------|-----------------|-----------------|----------|
| Métricas offline (reference-based) | Não | Sim | Avaliar *retrieval* (a metade RAG) de forma reproduzível |
| LLM-as-judge | Sim | Não (aproximada) | Avaliar *geração* quando não há label humano nem resposta exata |

A regra prática: use as métricas offline como piso confiável e o LLM-as-judge
para o que elas não alcançam (qualidade da redação, fidelidade semântica) —
sempre sanity-checando um contra o outro.

## Arquivos

### `rag_metrics.py` — métricas offline de retrieval (sem Ollama)
Mede a metade de *recuperação* do RAG com métricas determinísticas sobre o motor
híbrido do projeto (`create_search_engine('hybrid')`) e a base de CVEs:
- **precision@k**: dos top-k documentos retornados, quantos são realmente
  relevantes (ground truth derivado do próprio dataset).
- **groundedness proxy**: sinal barato e sem LLM de "a resposta é sustentada pelo
  contexto?" — fração dos termos de conteúdo da query cobertos pelos documentos
  recuperados. É um *proxy* (não entende significado), mas é instantâneo e pega o
  erro clássico de recuperar documento fora do tema.

Roda sem nenhum backend de LLM — mesma entrada, mesmo resultado.

### `llm_as_judge.py` — pontuar geração com um segundo LLM (precisa de Ollama)
Demonstra o padrão **LLM-as-judge** em dois passos:
1. **GENERATE**: pega 1-2 CVEs reais e pede ao LLM um resumo de segurança.
2. **JUDGE**: envia um *segundo* prompt (o juiz) com o contexto-fonte + o resumo
   candidato, pedindo nota 1-5 com justificativa em JSON estrito para três eixos:
   **groundedness** (toda afirmação tem suporte na fonte?), **completeness** (os
   fatos-chave estão presentes?) e **clarity** (está claro?).

Por que separar o juiz? O modelo que *escreve* é mau avaliador da própria
resposta no mesmo turno; isolar a avaliação num prompt com rubrica explícita e
saída legível por máquina é o cerne da técnica. As notas são aproximadas (o juiz
ainda é um LLM) — por isso o par com `rag_metrics.py`.

## Como rodar

```powershell
$env:PYTHONPATH = "."   # na raiz do projeto

# Métricas offline (não precisa de Ollama):
python -m 06_evals.rag_metrics

# LLM-as-judge (requer Ollama no ar + modelo baixado):
python -m 06_evals.llm_as_judge
```

Se o backend de LLM não estiver disponível, `llm_as_judge.py` falha com uma
mensagem instrutiva em vez de travar; `rag_metrics.py` roda de qualquer forma.
