# 10 — Saída Estruturada Confiável (Structured Output)

> Pré-requisitos: `retry_parser.py` roda **sem LLM** (só precisa do `pydantic`, que já vem no ambiente base/CI). `schema_extraction.py` precisa de **Ollama** no ar (ou outro backend compatível) e do modelo baixado — sem ele, degrada com mensagem instrutiva.

"O modelo retorna JSON... quase sempre." Esse *quase* é o que derruba pipeline em produção. Este módulo mostra o padrão que transforma "quase sempre" em "sempre": **forçar o formato + VALIDAR contra um schema + RE-TENTAR com o erro de volta no prompt**.

## Por que importa

Qualquer feature que *consome* a saída do LLM programaticamente (extração de campos, roteamento por categoria, tool-calling, preenchimento de formulário) depende de saída estruturada confiável. Em vaga de AI Engineering, saber montar o laço parse→validate→retry (em vez de só `json.loads` com `try/except` e torcer) é a diferença entre um protótipo e algo que aguenta produção.

## Conceitos

### O problema
Pedir JSON a um LLM funciona na maioria das vezes. A minoria é o que quebra: uma frase extra antes do objeto, uma cerca Markdown ` ```json `, uma vírgula sobrando, um valor de enum inventado (`"teal"` num campo que só aceita três cores), um número fora da faixa (`exploitability: 42` quando o contrato é 1–10). Confiar só no prompt ("responda APENAS com JSON") é fé — o modelo escorrega e o código que faz `json.loads(...)` estoura em runtime.

### As três camadas (e por que todas importam)

| Camada | O que faz | Garante sozinha? |
|--------|-----------|------------------|
| **JSON mode / prompt** | Pede ao modelo para emitir JSON e dá o shape exato | Não — reduz o erro, não elimina |
| **Validação (Pydantic)** | Rejeita o que não bate com o schema: tipo errado, enum inválido, número fora da faixa, campo faltando | Detecta o erro, mas sozinha só te dá uma exceção |
| **Retry com feedback** | Re-pede ao modelo injetando *por que* a tentativa anterior falhou, até N vezes | Fecha o ciclo: o modelo se autocorrige em vez de você rezar |

A ideia-chave é a última linha: a mensagem de erro da validação **vira parte do próximo prompt** ("sua saída falhou porque o campo 'exploitability' precisa ser <= 10; corrija"). O modelo passa de "chutador cego" para "corretor guiado". É exatamente isso que impede o clássico "às vezes retorna JSON inválido".

### Pydantic V2 (a camada de validação)
O código usa **Pydantic V2**. O schema é uma classe que herda de `BaseModel`; cada campo é uma trava de validação. Restrições numéricas (`Field(ge=1, le=10)`), enums (`str, Enum`) e campos obrigatórios bem tipados são verificados quando se chama `model_validate(data)` — que levanta `ValidationError` se os dados não satisfazem os tipos/restrições. Depois de validado, `model_dump()` devolve o dicionário dos campos. É sobre essa exceção estruturada que o retry se apoia: cada problema de campo vira texto de feedback.

## Arquivos

### `retry_parser.py` — o motor genérico (sem LLM, determinístico)
Helper autocontido com a lógica reutilizável:
- `strip_code_fences(text)`: remove a cerca ` ```json ` (ou qualquer cerca ```` ```lang ````) quando o modelo embrulha o JSON; devolve o conteúdo da cerca, ou o texto original (trimado) se não houver cerca.
- `extract_json_block(text)`: depois de tirar a cerca, isola o objeto `{...}` quando o modelo ainda envolve o JSON em prosa ("Here is the JSON: {...}. Hope it helps!").
- `parse_with_retry(model_cls, generator, max_attempts)`: recebe um modelo Pydantic e uma **função-geradora** `fn(feedback) -> str`. Chama o gerador, valida; se falhar, chama de novo passando o erro como `feedback`, até `max_attempts`. Devolve um `ParseResult` com a instância validada (ou `None`), o número de tentativas e os erros coletados. Levanta `ValueError` se `max_attempts < 1`.

O gerador ser abstrato é o truque: o mesmo motor roda com um LLM real (`schema_extraction.py`) e com stubs determinísticos no bloco `__main__` deste arquivo — que prova o parser **sem Ollama**, cobrindo quatro casos: JSON válido na primeira, JSON dentro de cerca + prosa, inválido→corrigido ao longo das tentativas, e sempre inválido (desiste limpo no limite).

### `schema_extraction.py` — o caller com LLM (precisa de Ollama)
Define o schema `CVEAssessment` (`id` string, `severity` como Enum `Severity` de `CRITICAL/HIGH/MEDIUM/LOW/INFO`, `exploitability` inteiro 1–10 via `Field(ge=1, le=10)`, `is_exploitable` bool, `remediation` string não vazia) e pede ao LLM para extraí-lo de um CVE real do dataset via `get_cve_by_id`. Usa o motor de `retry_parser.py` para validar e re-tentar com feedback, e imprime **quantas tentativas** o modelo precisou — o sinal honesto de quão confiável ele é em saída estruturada. Se o backend não estiver no ar, falha com mensagem clara em vez de travar.

O gerador do caller pede `temperature=0.0` para tornar a extração o mais determinística que o backend permite. **Esse 0.0 chega de fato ao modelo.** Uma versão anterior do cliente LLM resolvia a temperatura com `temperature or default`, e como em Python `0.0 or 0.7` avalia para `0.7`, uma temperatura 0.0 pedida era silenciosamente trocada pela default (0.7) — exatamente o tipo de bug que mina a reprodutibilidade de extração estruturada. A correção usa `temperature if temperature is not None else default`, então `0.0` passa intacto (ver `utils/llm_client.py`).

## Como rodar

A partir da raiz do repositório. Setup de provedor (para a extração) em [../LLM_SETUP.md](../LLM_SETUP.md).

**PowerShell (Windows):**
```powershell
$env:PYTHONPATH = "."

# Testa o PARSER — determinístico, NÃO precisa de Ollama:
python -m 10_structured_output.retry_parser

# Extração real com LLM (requer Ollama no ar + modelo baixado):
python -m 10_structured_output.schema_extraction
```

**Bash (Linux/macOS):**
```bash
export PYTHONPATH="."

python -m 10_structured_output.retry_parser
python -m 10_structured_output.schema_extraction
```

O `retry_parser` roda em qualquer máquina e termina com todas as asserções passando. O `schema_extraction` depende do LLM; sem backend disponível ele imprime uma mensagem instrutiva e sai, sem pendurar.

## O que a demo mostra

`retry_parser` — os quatro casos, determinísticos, `exit=0`:

```
[case 1] valid JSON, first attempt
  success=True attempts=1 model=Widget(name='alpha', count=3, color=<Color.GREEN: 'green'>)

[case 2] JSON inside a Markdown fence + prose
  success=True attempts=1 model=Widget(name='beta', count=0, color=<Color.BLUE: 'blue'>)

[case 3] invalid -> schema error -> corrected across retries
  success=True attempts=3 model=Widget(name='gamma', count=5, color=<Color.BLUE: 'blue'>)
    attempt 1 rejected: the output was not valid JSON (Expecting value at char 0)
    attempt 2 rejected: the JSON failed schema validation - field 'count': Input should be greater than or equal to 0; field 'color': Input should be 'red', 'green' or 'blue'

[case 4] always invalid -> gives up cleanly
  success=False attempts=2 errors=2

All self-test assertions passed. [OK]
```

`schema_extraction` — **sem Ollama** (o estado desta máquina), degrada com mensagem instrutiva e sai `exit=0`, sem travar:

```
Structured Output: extract -> validate -> retry on failure
Subject CVE: CVE-2024-1234
Schema: CVEAssessment (fields: id, severity, exploitability, is_exploitable, remediation)
======================================================================

[error] Could not reach the LLM backend. Is Ollama running (e.g. `ollama serve`) and the configured model pulled?
Details: Connection error.
```

Com o Ollama no ar, o script imprime `Attempts used: <n> / 3`, o motivo de cada tentativa rejeitada (`attempt <i> rejected: ...`) e, no fim, `[OK] Validated assessment:` com um campo do `CVEAssessment` por linha. Se o modelo não produzir JSON válido para o schema dentro das 3 tentativas, imprime `[fail] The model never produced schema-valid output within ...` seguido da última resposta crua. Os valores dependem do modelo; como esta máquina estava sem Ollama, não há saída real desse caminho aqui.

## Exercícios

1. **Aperte uma trava e veja o retry agir.** Em `retry_parser.py` (`__main__`), mude o stub do caso 3 para devolver um `exploitability`/`count` fora da faixa até a última tentativa e confirme pela saída que a mensagem de feedback cita o campo e o motivo exatos antes de corrigir.
2. **Esgote as tentativas.** Rode o caso 4 mentalmente e depois ajuste `max_attempts` para 1: confirme que `parse_with_retry` devolve `success=False` com `attempts=1` e um erro coletado, sem levantar exceção.
3. **Teste `extract_json_block`.** Passe a ele uma string com prosa antes e depois de um `{...}` e verifique que ele isola só o objeto; depois passe `"não é json"` e veja o que ele devolve (o texto limpo, que a validação então rejeita).
4. **Adicione um campo ao schema.** Em `CVEAssessment`, inclua `cwe: str = Field(min_length=1)` e ajuste o `schema_hint` do prompt em `build_extraction_prompt`. (Requer Ollama para rodar a extração de ponta a ponta — ou escreva um stub determinístico seguindo o padrão de `retry_parser`.)
5. **Prove o bug da temperatura.** Sem rodar o LLM, explique por que `0.0 or 0.7 == 0.7` em Python e por que `0.0 if 0.0 is not None else 0.7 == 0.0`. Veja em `utils/llm_client.py` qual das duas formas o cliente usa e descreva o impacto que a outra teria na reprodutibilidade da extração.

## Referências

- [Pydantic — Models](https://docs.pydantic.dev/latest/concepts/models/) — `BaseModel`, `model_validate`, `model_dump` e quando `ValidationError` é levantada (V2).
- [Pydantic — Fields](https://docs.pydantic.dev/latest/concepts/fields/) — restrições de campo, incluindo as numéricas (`gt`, `ge`, `lt`, `le`).
