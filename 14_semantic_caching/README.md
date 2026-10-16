# 14 — Cache Semântico (Semantic Caching)

> Pré-requisitos: roda sem Ollama / sem LLM. Os embeddings vêm de
> `utils.semantic_embeddings.embed_text` (sentence-transformers, offline). Nenhum
> pacote novo além dos que o projeto já instala (`numpy`, `sentence-transformers`).

Cache de respostas de LLM por **similaridade de significado** da query, não por
chave exata. Serve para cortar **custo** e **latência**: se uma pergunta "nova"
é, no fundo, uma paráfrase de uma pergunta já respondida, devolvemos a resposta
guardada em vez de chamar o LLM de novo.

## Por que importa

Um cache tradicional (dict por string) só casa a chave **idêntica**:

- `"RCE no handler"` ≠ `"remote code execution in the request handler"` → MISS,
  mesmo sendo a mesma pergunta.

O cache semântico embeda a query num vetor e compara por **cosseno**. Perguntas
com o mesmo significado ficam próximas no espaço vetorial, então a paráfrase dá
**HIT** — e cada HIT é uma chamada cara ao LLM que você não precisou fazer.

## Conceitos

### Threshold — o tradeoff central

`SemanticCache(threshold=...)` é a similaridade mínima de cosseno para considerar
HIT:

- **Alto** (ex: `0.9`): mais preciso, menos hits. Só casa paráfrases muito
  próximas; evita servir resposta errada, mas aproveita menos o cache.
- **Baixo** (ex: `0.7`): mais hits, mais economia — porém com risco de casar
  perguntas que só *parecem* parecidas e servir uma resposta inadequada.

A escolha depende do custo de um erro vs. o custo de uma chamada ao LLM. O padrão
da classe é `threshold=0.85`; a demo usa `0.65` para que paráfrases entre idiomas
técnicos ainda casem.

### HIT por significado vs. exact-match

O `set(query, response)` guarda a query, seu embedding e a resposta. O `get(query)`
embeda a consulta, acha o vizinho mais próximo por cosseno (`_nearest`) e devolve a
resposta cacheada se a similaridade for `>= threshold` (HIT), senão `None` (MISS) —
sempre atualizando as métricas. O `lookup(query)` faz o mesmo mas **também** devolve
a similaridade do melhor candidato e **não** conta hit/miss (útil para demo/debug).

## Arquivos

- `semantic_cache.py` — a classe `SemanticCache` (`set` / `get` / `lookup`),
  `CacheEntry`, `CacheStats` (hits, misses, `hit_rate`) e uma demo em `main()`.
- `__init__.py` — torna a pasta um pacote.
- `README.md` — este arquivo.

## Como rodar

Da **raiz do repositório** (o nome da pasta começa com dígito, então use
`python -m`, não import direto).

**PowerShell:**
```powershell
$env:PYTHONPATH = "."
python -m 14_semantic_caching.semantic_cache
```

**Bash:**
```bash
export PYTHONPATH="."
python -m 14_semantic_caching.semantic_cache
```

A demo popula o cache com queries sobre CVEs, consulta paráfrases (HIT) e uma
pergunta de tópico distante (MISS), e imprime as métricas. Não precisa de Ollama
nem de chave de API.

## O que a demo mostra

Trecho real da saída (`threshold=0.65`, embeddings `all-MiniLM-L6-v2` offline):

```
Cache populado com 3 entradas.

[HIT ] sim=0.779  query='arbitrary code execution via the HTTP request handler'  (HIT esperado (parafrase de RCE no handler))
        -> Resposta cacheada: a RCE no handler permite executar codigo arbitrario; aplique o patch.
[HIT ] sim=0.723  query='injecting malicious SQL through the sign-in form'  (HIT esperado (parafrase de SQL injection no login))
        -> Resposta cacheada: use consultas parametrizadas para mitigar a SQL injection no login.
[MISS] sim=0.126  query='qual a receita de bolo de cenoura'  (MISS esperado (topico totalmente distante))

Metricas:
  consultas : 3
  hits      : 2
  misses    : 1
  hit_rate  : 66.7%
  chamadas de LLM evitadas: 2 (uma por HIT)
```

- **HIT** nas duas paráfrases (RCE no handler ≈ 0.78; SQL injection no login ≈ 0.72).
- **MISS** no tópico distante ("receita de bolo de cenoura" ≈ 0.13).
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

## Exercícios

1. Suba o `threshold` de `0.65` para `0.85` no `main()` e rode de novo: observe a
   segunda paráfrase (SQL injection, sim ≈ 0.72) virar **MISS**, derrubando o
   `hit_rate` — é o tradeoff precisão vs. cobertura na prática.
2. Acrescente ao `seed` uma entrada nova e uma paráfrase dela nos `probes`, e
   confira a similaridade que `lookup()` reporta antes de decidir o `threshold`.
3. Escreva a paráfrase de uma query do seed em **outra língua** (ex. a RCE em
   português) e veja a similaridade cair — comprova a nota sobre mistura de idioma
   do MiniLM.
4. Use `lookup()` em vez de `get()` numa consulta e confirme pelas métricas que ele
   **não** incrementa `hits`/`misses` (é o caminho de "espiar" sem contar).
5. Popule o cache com uma query repetida (mesmo texto em `set` duas vezes) e
   verifique que `len(cache)` cresce — o cache não deduplica, guarda cada entrada.

## Referências

- [Modelos do Ollama](https://ollama.com/library)
- [Documentação do LangChain](https://python.langchain.com/)
