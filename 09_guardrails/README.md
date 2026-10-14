# 09 — Guardrails de Segurança para LLM

> Os módulos anteriores *constroem* (RAG, agentes) e *medem* (evals) o sistema.
> Este módulo o **protege**: um LLM em produção recebe texto não confiável (a
> pergunta do usuário e, no RAG, documentos externos inteiros) e devolve texto
> para o usuário. As duas pontas precisam de controle — é a **dupla guardrail**:
> uma camada *antes* do modelo (entrada) e outra *depois* (saída).

Tudo aqui é **determinístico e sem LLM** (regex + lógica de string), então roda
sem Ollama, é instantâneo e dá sempre o mesmo veredito — exatamente a propriedade
que você quer de um controle de segurança, que nunca pode falhar em silêncio.

## As ameaças (alinhadas ao OWASP Top 10 for LLM Applications)

### Prompt injection (LLM01)
Texto não confiável que tenta **sobrescrever o system prompt** do modelo:
`ignore previous instructions`, `you are now ...`, `reveal your system prompt`,
marcadores de papel falsos (`SYSTEM:`), personas de jailbreak (`DAN`, `developer
mode`). É perigoso no RAG porque descrições de CVE — conteúdo externo — vão
*direto* para dentro do prompt. **Um documento envenenado é injection disfarçada
de dado.**

### Vazamento de PII e segredos (LLM02 / LLM06)
Dados sensíveis — emails e tokens com cara de chave de API (`sk-...`, `ghp_...`,
`AKIA...`, `Bearer ...`) — que não podem ser embeddados, logados nem enviados a um
modelo de terceiros. A defesa é **redigir antes** de a informação circular.

### Jailbreak
Caso particular de prompt injection: em vez de pedir uma ação pontual, o atacante
tenta trocar a **persona inteira** do modelo por uma sem restrições (`do anything
now`, `developer mode`). Mesmas assinaturas, mesma camada de entrada.

### Vazamento de system prompt e fuga de escopo (saída)
Mesmo que a entrada passe, o modelo pode ser induzido a **repetir seu system
prompt** (vazamento de instruções confidenciais, LLM06) ou a **sair do escopo**
(responder sobre receita de bolo em vez de CVEs). Isso só dá para pegar olhando a
**resposta** — por isso a segunda camada existe.

## Por que importa no mercado

Guardrails são o que separa um protótipo de LLM de um sistema que pode ir para
produção. Em entrevistas e code reviews de AI Engineering, "como você trata
prompt injection e vazamento de dados?" é pergunta recorrente, e o OWASP Top 10
for LLMs virou vocabulário comum. Checagens determinísticas são a base barata e
auditável: não substituem defesas mais sofisticadas, mas são a primeira (entrada)
e a última (saída) linha, e nunca ficam indisponíveis por falta de GPU.

## Arquivos

### `input_guardrails.py` — triagem *antes* do LLM (sem Ollama)
Funções determinísticas que rodam sobre qualquer texto de entrada:
- `detect_injection(text)` — devolve os rótulos de cada assinatura de prompt
  injection encontrada (ex: `ignore_previous`, `role_override`, `jailbreak_persona`).
- `detect_pii(text)` / `sanitize_pii(text)` — detectam e **redigem** emails e
  tokens com formato de segredo, trocando por marcadores tipados (`[REDACTED_EMAIL]`).
- `screen_input(text)` / `screen_cve(cve)` — a triagem completa, com `is_safe` e
  os motivos.

**Demonstração:** o script monta um **CVE envenenado** (um registro `CVEData`
realista cuja descrição esconde `IGNORE ALL PREVIOUS INSTRUCTIONS`, um
`Bearer sk-...` e um email de atacante) e mostra ele sendo **bloqueado e
sanitizado antes** de chegar a `get_llm_client().generate(...)`. Os CVEs reais da
base (`utils/data/cves.json`) passam limpos.

### `output_guardrails.py` — validação *depois* do LLM (sem Ollama)
Heurísticas determinísticas sobre a resposta do modelo:
- `detect_system_prompt_leak(response, system_prompt)` — pega vazamento por
  frases reveladoras ("my instructions are ...") **e** por sobreposição de
  n-gramas longos com o system prompt conhecido.
- `detect_out_of_scope(response)` — sinaliza respostas sem nenhuma conexão com o
  domínio de CVE/segurança.
- `screen_output(response, system_prompt)` — a validação completa, com `is_safe`.

**Demonstração:** três saídas de modelo pré-fabricadas (uma boa, ancorada num CVE
real da base; uma que vaza o system prompt; uma fora de escopo) passam pelos
validadores, mostrando `PASS` / `BLOCK` para cada — sem Ollama.

## Como rodar

```powershell
$env:PYTHONPATH = "."   # na raiz do projeto

# Guardrail de ENTRADA (não precisa de Ollama):
python -m 09_guardrails.input_guardrails

# Guardrail de SAÍDA (não precisa de Ollama):
python -m 09_guardrails.output_guardrails
```

Ambos os scripts são **100% determinísticos e offline** — não acessam o LLM, então
rodam igual com ou sem Ollama no ar. Eles consomem a mesma base de CVEs
(`utils/data/cves.json`) dos outros módulos: o guardrail de entrada é o portão por
onde esse conteúdo externo passaria antes de virar prompt.
