# 14 — Cache Semântico (Semantic Caching)

Cache de respostas de LLM por **similaridade de significado** da query, não por
chave exata. Serve para cortar **custo** e **latência**: se uma pergunta "nova"
é, no fundo, uma paráfrase de uma pergunta já respondida, devolvemos a resposta
guardada em vez de chamar o LLM de novo.

Roda **sem Ollama / sem LLM**: os embeddings vêm de
`utils.semantic_embeddings.embed_text` (sentence-transformers, offline).

## Por que similaridade e não exact-match

Um cache tradicional (dict por string) só casa a chave **idêntica**:

- `"RCE no handler"` ≠ `"remote code execution in the request handler"` → MISS,
  mesmo sendo a mesma pergunta.

O cache semântico embeda a query num vetor e compara por **cosseno**. Perguntas
com o mesmo significado ficam próximas no espaço vetorial, então a paráfrase dá
**HIT**.

## Threshold — o tradeoff central

`SemanticCache(threshold=...)` é a similaridade mínima para considerar HIT:

- **Alto** (ex: `0.9`): mais preciso, menos hits. Só casa paráfrases muito
  próximas; evita servir resposta errada, mas aproveita menos o cache.
- **Baixo** (ex: `0.7`): mais hits, mais economia — porém com risco de casar
  perguntas que só *parecem* parecidas e servir uma resposta inadequada.

A escolha depende do custo de um erro vs. o custo de uma chamada ao LLM.

## Arquivos

- `semantic_cache.py` — classe `SemanticCache` (`get`/`set`/`lookup`),
  `CacheEntry`, `CacheStats` (hits, misses, `hit_rate`) e uma demo `__main__`.
- `__init__.py` — torna a pasta um pacote.
- `README.md` — este arquivo.

## Como rodar

Da **raiz do repositório** (o nome da pasta começa com dígito, então use
`python -m`, não import direto):

```bash
python -m 14_semantic_caching.semantic_cache
```

A demo popula o cache com queries sobre CVEs, consulta paráfrases (HIT) e uma
pergunta de tópico distante (MISS), e imprime as métricas. Não precisa de Ollama
nem de chave de API.

## O que a demo mostra

- **HIT** em `"arbitrary code execution via the HTTP request handler"`
  (paráfrase de *remote code execution in the request handler*) — sim ≈ 0.78.
- **HIT** em `"injecting malicious SQL through the sign-in form"` (paráfrase de
  *SQL injection in the login form*) — sim ≈ 0.72.
- **MISS** em `"qual a receita de bolo de cenoura"` (tópico distante) — sim ≈ 0.13.
- Métricas finais: `hits=2`, `misses=1`, `hit_rate=66.7%` e 2 chamadas de LLM
  evitadas (uma por HIT).

> As paráfrases ficam na **mesma língua** do item cacheado de propósito: o modelo
> `all-MiniLM-L6-v2` é sensível a mistura de idioma e a abreviações, então um
> teste justo do mecanismo usa uma reescrita honesta do mesmo significado.

## Uso programático

```python
from importlib import import_module

semantic_cache = import_module("14_semantic_caching.semantic_cache")
SemanticCache = semantic_cache.SemanticCache

cache = SemanticCache(threshold=0.85)
cache.set("remote code execution in the request handler", "...resposta cara do LLM...")

hit = cache.get("arbitrary code execution via the request handler")  # paráfrase -> resposta cacheada
print(cache.stats.hit_rate)            # fração de consultas servidas pelo cache
```

> O `import_module` é necessário porque `14_semantic_caching` começa com dígito
> e não pode ser importado com `import 14_semantic_caching` diretamente.

## Dependências

Apenas `numpy` e `sentence-transformers` (já presentes no projeto). Nenhuma
dependência nova.
