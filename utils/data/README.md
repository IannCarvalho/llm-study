# Dados — Bases de CVEs (sintéticas)

> Pré-requisitos: só leitura de JSON. Carregar e validar as bases roda **sem
> LLM, sem Ollama, sem rede**. A avaliação de retrieval em
> `06_evals/rag_metrics_extended.py` usa os motores `semantic`/`hybrid`, que
> baixam um modelo de embeddings na primeira execução; o motor `bm25` continua
> offline.

Esta pasta guarda as bases de vulnerabilidades (CVEs) usadas pelos módulos do
repositório. **As duas bases são totalmente sintéticas** — servem para estudo de
busca e RAG, não representam vulnerabilidades reais.

## Por que importa

A base padrão tem só 3 registros. Com 3 documentos, métricas de retrieval como
`precision@k`, `recall@k` e MRR quase não distinguem BM25, busca semântica e
híbrida (RRF): todo mundo acerta. A base **estendida** acrescenta registros
sintéticos com **distratores de propósito**, de modo que os métodos passam a se
diferenciar e as métricas voltam a ter sinal.

## As duas bases

### `cves.json` — base padrão (NÃO MUDA)
3 registros (um RCE, uma SQL injection, uma fraqueza de criptografia). É a base
que `utils.data_loader.load_cves()` carrega e sobre a qual o comportamento e os
testes atuais do repositório dependem. **Não deve ser alterada.**

### `cves_extended.json` — base estendida (opt-in)
39 registros: **os 3 originais idênticos** aos de `cves.json` + **36 sintéticos**.
Carregada sob demanda por `utils.data_loader.load_cves_from(path)` — nunca
substitui a base padrão.

Características dos 36 sintéticos:

- **IDs no formato `CVE-2099-NNNN`.** O ano futuro deixa óbvio que são
  fabricados e evita colisão com CVEs reais.
- **Produtos fictícios** (ex.: `EdgeProxy`, `ShopCart`, `GateKeeper`).
- **Distribuídos por todos os tipos** do enum `VulnerabilityType`
  (`utils/models.py`): `rce`, `sql_injection`, `xss`, `csrf`, `auth_bypass`,
  `memory`, `crypto`, `other`; e por todos os níveis de `SeverityLevel`
  (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
- **Distratores propositais:**
  - *pares quase-duplicados* de tipo/produto — por exemplo duas RCEs no mesmo
    `EdgeProxy` (buffer overflow vs. desserialização), ou duas SQL injections no
    mesmo `ShopCart` (baseada em erro vs. cega);
  - *termos compartilhados com tipo diferente* — por exemplo um registro cujo
    nome de produto é `DataEncryption` mas cuja falha é de permissão de arquivo
    (não de criptografia), ou um que menciona "login form" sem ser SQL
    injection. Servem para punir retrievers que se apoiam só em palavra-chave.
- **`score` coerente com a `severity`** (faixas do CVSS v3.1): CRITICAL
  9.0–10.0, HIGH 7.0–8.9, MEDIUM 4.0–6.9, LOW 0.1–3.9, INFO 0.0.
- **`cvss_vector` plausível** para a severidade (não recalculado formalmente a
  partir do score).

> Observação: mesmo os IDs da base original (`CVE-2024-...`) são sintéticos para
> fins deste repositório. Um identificador desses pode, por coincidência,
> corresponder a uma CVE real de outro produto — não há relação.

## Esquema

Cada registro (nas duas bases) tem o mesmo conjunto de campos, consumido por
`utils.models.CVEData`:

| Campo               | Tipo              | Descrição                                                        |
| ------------------- | ----------------- | ---------------------------------------------------------------- |
| `id`                | `str`             | Identificador da CVE (ex.: `CVE-2099-0001`).                     |
| `severity`          | `str` (enum)      | Um valor de `SeverityLevel`.                                     |
| `score`             | `float` (0.0–10.0)| Pontuação CVSS, coerente com a severidade.                       |
| `description`       | `str` (não vazio) | Texto descritivo da vulnerabilidade.                             |
| `affected_versions` | `list[str]`       | Versões afetadas do produto.                                     |
| `cvss_vector`       | `str`             | Vetor CVSS v3.1 plausível.                                       |
| `vulnerability_type`| `str` (enum)      | Um valor de `VulnerabilityType`.                                 |

## Como usar a base estendida

A base padrão continua pelo caminho de sempre:

```python
from utils.data_loader import load_cves          # base padrão (cves.json)
cves = load_cves()
```

A estendida é carregada explicitamente por caminho, sem tocar na base padrão:

```python
from pathlib import Path
from utils.data_loader import load_cves_from

path = Path("utils/data/cves_extended.json")
cves_ext = load_cves_from(path)                   # 39 CVEData
```

`load_cves_from` usa exatamente a mesma construção de `CVEData` que `load_cves`,
mas lê de um caminho arbitrário e **não** é cacheada (trocar de base não exige
limpar cache).

A avaliação comparativa de retrieval sobre a base estendida está em
`../../06_evals/rag_metrics_extended.py` (caminho relativo a esta pasta):

```bash
# a partir da raiz do repositório, com PYTHONPATH=.
python -m 06_evals.rag_metrics_extended
```

Ela compara BM25, semântico e híbrido com documentos **crus** (sem as
palavras-chave injetadas por `get_cve_documents()`), usando consultas rotuladas
e imprimindo `precision@k`, `recall@k` e MRR numa tabela. Sem o modelo de
embeddings (offline), as linhas `semantic`/`hybrid` aparecem como puladas e o
BM25 ainda roda.

## Arquivos

- `cves.json` — base padrão de 3 CVEs (não alterar).
- `cves_extended.json` — base estendida de 39 CVEs (3 originais + 36 sintéticos).
- `README.md` — este arquivo.
