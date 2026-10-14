# 10 — Saída Estruturada Confiável (Structured Output)

> "O modelo retorna JSON... quase sempre." Esse *quase* é o que derruba pipeline
> em produção. Este módulo mostra o padrão que transforma "quase sempre" em
> "sempre": **forçar o formato + VALIDAR contra um schema + RE-TENTAR com o erro
> de volta no prompt**.

## O problema

Pedir JSON a um LLM funciona na maioria das vezes. A minoria é o que quebra:
uma frase extra antes do objeto, uma cerca Markdown ` ```json `, uma vírgula
sobrando, um valor de enum inventado (`"teal"` num campo que só aceita três
cores), um número fora da faixa (`exploitability: 42` quando o contrato é 1-10).
Confiar só no prompt ("responda APENAS com JSON") é fé — o modelo escorrega e o
código que faz `json.loads(...)` estoura em runtime.

## As três camadas (e por que todas importam)

| Camada | O que faz | Garante sozinha? |
|--------|-----------|------------------|
| **JSON mode / prompt** | Pede ao modelo para emitir JSON e dá o shape exato | Não — reduz o erro, não elimina |
| **Validação (Pydantic)** | Rejeita o que não bate com o schema: tipo errado, enum inválido, número fora da faixa, campo faltando | Detecta o erro, mas sozinha só te dá uma exceção |
| **Retry com feedback** | Re-pede ao modelo injetando *por que* a tentativa anterior falhou, até N vezes | Fecha o ciclo: o modelo se autocorrige em vez de você rezar |

A ideia-chave é a última linha: a mensagem de erro da validação **vira parte do
próximo prompt** ("sua saída falhou porque o campo 'exploitability' precisa ser
<= 10; corrija"). O modelo passa de "chutador cego" para "corretor guiado". É
exatamente isso que impede o clássico "às vezes retorna JSON inválido".

## Por que isso importa no mercado

Qualquer feature que *consome* a saída do LLM programaticamente (extração de
campos, roteamento por categoria, tool-calling, preenchimento de formulário)
depende de saída estruturada confiável. Em vaga de AI Engineering, saber montar
o laço parse→validate→retry (em vez de só `json.loads` com `try/except` e torcer)
é a diferença entre um protótipo e algo que aguenta produção.

## Arquivos

### `retry_parser.py` — o motor genérico (sem LLM, determinístico)
Helper autocontido com a lógica reutilizável:
- `strip_code_fences` / `extract_json_block`: tiram a cerca ` ```json ` e isolam
  o objeto `{...}` quando o modelo embrulha o JSON em prosa.
- `parse_with_retry(model_cls, generator, max_attempts)`: recebe um modelo
  Pydantic e uma **função-geradora** `fn(feedback) -> str`. Chama o gerador,
  valida; se falhar, chama de novo passando o erro como `feedback`, até
  `max_attempts`. Devolve um `ParseResult` com a instância validada, o número de
  tentativas e os erros coletados.

O gerador ser abstrato é o truque: o mesmo motor roda com um LLM real
(`schema_extraction.py`) e com stubs determinísticos no bloco `__main__` deste
arquivo — que prova o parser **sem Ollama**, cobrindo quatro casos: JSON válido
na primeira, JSON dentro de cerca + prosa, inválido→corrigido ao longo das
tentativas, e sempre inválido (desiste limpo no limite).

### `schema_extraction.py` — o caller com LLM (precisa de Ollama)
Define o schema `CVEAssessment` (`id`, `severity` como Enum, `exploitability`
inteiro 1-10, `is_exploitable` bool, `remediation` string) e pede ao LLM para
extraí-lo de um CVE real do dataset do projeto via `get_cve_by_id`. Usa o motor
de `retry_parser.py` para validar e re-tentar com feedback, e imprime **quantas
tentativas** o modelo precisou — o sinal honesto de quão confiável ele é em
saída estruturada. Se o backend não estiver no ar, falha com mensagem clara em
vez de travar.

## Como rodar

```powershell
$env:PYTHONPATH = "."   # na raiz do projeto

# Testa o PARSER — determinístico, NÃO precisa de Ollama:
python -m 10_structured_output.retry_parser

# Extração real com LLM (requer Ollama no ar + modelo baixado):
python -m 10_structured_output.schema_extraction
```

O `retry_parser` roda em qualquer máquina e termina com todas as asserções
passando. O `schema_extraction` depende do LLM; sem backend disponível ele
imprime uma mensagem instrutiva e sai, sem pendurar.
