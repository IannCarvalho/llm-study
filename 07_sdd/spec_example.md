# Spec: Análise de CVE

> Este arquivo é um **artefato legível por humanos**. É a mesma spec que o código
> em `spec_driven_analysis.py` representa como objeto estruturado (`CVEAnalysisSpec`).
> No fluxo do Kiro, um documento como este viveria em `.kiro/steering/` ou como a
> spec de uma feature, e seria a fonte de verdade que guia o agente — não um prompt
> digitado na hora.

---

## Tarefa

`analisar_cve` — dado um registro de CVE (ver `utils/data/cves.json`), produzir uma
análise de segurança estruturada, consumível por máquina, pronta para alimentar um
pipeline de triagem/relatório.

## Entrada

Um `CVEData` carregado via `get_cve_by_id(...)`:

| Campo               | Tipo    | Observação                                   |
| ------------------- | ------- | -------------------------------------------- |
| `id`                | str     | ex. `CVE-2024-1234`                          |
| `severity`          | enum    | CRITICAL / HIGH / MEDIUM / LOW / INFO        |
| `score`             | float   | CVSS 0.0–10.0                                |
| `description`       | str     | texto livre descrevendo a vulnerabilidade   |
| `cvss_vector`       | str     | ex. `CVSS:3.1/AV:N/AC:L/...`                 |
| `affected_versions` | list    | versões afetadas                             |

## Saída (OBRIGATÓRIA)

Formato: **JSON válido, e somente JSON** (sem cercas de markdown, sem texto fora do objeto).

Campos obrigatórios — todos devem estar presentes:

| Campo            | Tipo | Significado                                                      |
| ---------------- | ---- | --------------------------------------------------------------- |
| `id`             | str  | o identificador do CVE, ecoado da entrada                       |
| `severidade`     | str  | uma de: CRITICAL, HIGH, MEDIUM, LOW, INFO                       |
| `vetor_ataque`   | str  | como a falha é explorada (rede/local, pré-condições)            |
| `mitigacao`      | str  | ação concreta de remediação (patch, upgrade, config)           |
| `risco_negocio`  | str  | impacto em termos de negócio (dados, disponibilidade, compliance)|

## Restrições

1. A saída é **apenas** o objeto JSON — nada antes, nada depois.
2. Todos os cinco campos obrigatórios devem existir e ser não-vazios.
3. `severidade` deve ser um dos cinco rótulos canônicos (em caixa alta).
4. `id` deve ecoar exatamente o `id` do CVE de entrada.
5. Não inventar CVEs, versões ou vetores que não derivem da entrada.

## Critério de aceite

A saída passa se, e somente se:

- faz `json.loads(...)` sem erro, **e**
- contém as cinco chaves obrigatórias, **e**
- `severidade` ∈ {CRITICAL, HIGH, MEDIUM, LOW, INFO}.

É exatamente isso que o validador em `spec_driven_analysis.py` checa — a spec e o
código concordam por construção.
