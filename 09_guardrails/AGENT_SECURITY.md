# 09 — Guardrails para Agentes com Ferramentas
> Pré-requisitos: roda **sem LLM** (tudo determinístico, regex/heurística/contagem). Não precisa de Ollama, rede nem chave. Python 3.11.

Os guardrails de entrada/saída (`input_guardrails.py`, `output_guardrails.py`) protegem **uma** chamada de LLM. Um **agente** é mais difícil: ele lê documentos e saídas de ferramenta de volta para o contexto, recebe ferramentas para invocar e roda em laço — então a superfície de ataque é o ciclo inteiro de uso de ferramentas, não um único prompt. Este módulo adiciona quatro defesas determinísticas para esse cenário.

## Por que importa
Um agente que recupera um documento envenenado, ou que carrega uma ferramenta vinda de um servidor MCP malicioso, pode ser levado a ler arquivos sensíveis e exfiltrá-los — sem que o usuário veja. A instrução hostil não está no prompt do usuário: vem escondida em **conteúdo** (documento, saída de ferramenta) ou na **descrição da ferramenta**. Controles determinísticos pegam os casos conhecidos de forma barata, reproduzível e à prova de falha-aberta (fail-closed), que é a propriedade certa para uma defesa.

## Conceitos
Mapeados para o OWASP Top 10 for LLM Applications (edição 2025):

1. **Injeção de prompt indireta (LLM01:2025 — Prompt Injection, que cobre explicitamente o caso indireto).** Um documento recuperado ou a saída de uma ferramenta carrega instruções dirigidas ao modelo. Defesa: (a) escanear o conteúdo não confiável **antes** de ele entrar no contexto; (b) **spotlighting** — embrulhar o conteúdo não confiável em delimitadores explícitos e não forjáveis, marcando-o como "dado a analisar, nunca instrução a seguir".
2. **Excessive Agency (LLM06:2025).** Agente com mais capacidade do que a tarefa exige. Defesa: uma **política de ferramentas** — allowlist por tarefa, validação de argumentos e **gate de aprovação humana** para ferramentas destrutivas (o "human in the loop" que a própria especificação do MCP recomenda).
3. **Tool poisoning.** Uma forma de injeção indireta carregada na **descrição** da ferramenta MCP: o modelo lê a descrição inteira, mas o usuário costuma ver só um resumo. Um servidor malicioso esconde ali instruções para ler/exfiltrar dados. Defesa: escanear a descrição em busca de instruções escondidas, pedidos de exfiltração e caracteres Unicode invisíveis/suspeitos. A descrição pode mudar **depois** de aprovada (um "rug pull"), então o scanner deve rodar no registro **e** a cada mudança.
4. **Unbounded Consumption (LLM10:2025).** Laço de agente sem teto de chamadas ou tokens. Defesa: um **orçamento por sessão** que nega mais trabalho assim que um limite é atingido.

## Arquivos
- [`agent_guardrails.py`](agent_guardrails.py) — as quatro defesas e uma `main()` didática com casos bons e maus sobre a base de CVEs.
- [`tests/test_agent_guardrails.py`](../tests/test_agent_guardrails.py) — testes determinísticos das quatro defesas.

O que o `agent_guardrails.py` expõe:
- `scan_untrusted_content(content) -> ContentScanResult` e `spotlight(content, source)` — defesa 1.
- `ToolPolicy(allowed_tools).evaluate(tool_name, arguments) -> ToolDecision`, com `ToolSpec` (campos `destructive`, `arg_validators`) — defesa 2.
- `scan_tool_description(description) -> ToolDescriptionScanResult` — defesa 3.
- `SessionBudget(max_calls, max_tokens).charge(text) -> BudgetStatus` — defesa 4.

Cada verdito é um dataclass (`is_safe`/`allowed` + motivos legíveis), no mesmo estilo de `input_guardrails.py` e `output_guardrails.py`.

## Como rodar
A partir da raiz do repositório (`PYTHONPATH=.`):

```
python -m 09_guardrails.agent_guardrails
```

Testes (suíte determinística, sem rede/LLM):

```
python -m pytest tests/test_agent_guardrails.py -q
```

## O que a demo mostra
Trecho da saída real da execução (`python -m 09_guardrails.agent_guardrails`):

```
[1] Indirect prompt injection scan (LLM01) — on untrusted content
  benign document        -> is_safe=True reasons=[]
  poisoned document      -> is_safe=False reasons=['indirect_injection:ignore_previous', 'indirect_injection:exfiltrate', 'indirect_injection:read_secret_file', 'indirect_injection:do_not_tell']

[2] Tool policy (LLM06 — Excessive Agency)
  search_cves({'query': 'sql injection'}) -> ALLOW []
  search_cves({'query': ''}) -> DENY ["invalid_argument: 'query' failed validation"]
  send_email({'to': 'x@y.com'}) -> DENY ["not_allowlisted: 'send_email' is not granted for this task"]
  delete_record({'id': 'CVE-2024-1234'}) -> APPROVAL ["human_approval_required: 'delete_record' is destructive"]

[3] Tool-description poisoning scan (MCP tool poisoning)
  benign description     -> is_safe=True reasons=[]
  poisoned description   -> is_safe=False reasons=['tool_poisoning:hidden_important_tag', 'tool_poisoning:hidden_instruction', 'tool_poisoning:do_not_tell_user', 'tool_poisoning:read_secret_file', 'tool_poisoning:exfiltrate', 'suspicious_unicode:U+200B']

[4] Session budget (LLM10 — Unbounded Consumption)
  call 1: charged [calls=1, tokens=6]
  call 2: charged [calls=2, tokens=12]
  call 3: charged [calls=3, tokens=18]
  call 4: DENIED (call budget exhausted (3 calls)) [calls=3, tokens=18]
  call 5: DENIED (call budget exhausted (3 calls)) [calls=3, tokens=18]
```

> O trecho acima é da execução real nesta máquina (sem Ollama). A lista exata de rótulos em `[1]` e `[3]` depende do texto de exemplo; o importante é que o documento/descrição envenenado sai `is_safe=False` com motivos, e o benigno sai `is_safe=True`.

## Exercícios
1. Adicione ao `scan_untrusted_content` uma assinatura para detecção de **base64 longo** embutido em conteúdo não confiável (canal comum de exfiltração encoberta). Escreva o teste bom/mau antes.
2. Estenda `ToolPolicy` com um limite de **taxa por ferramenta** (ex.: no máximo N chamadas de `search_cves` por sessão) reutilizando o padrão do `SessionBudget`.
3. Faça `scan_tool_description` sinalizar **mistura de scripts Unicode** (ex.: caracteres cirílicos homóglifos em meio a texto latino), não só caracteres invisíveis.
4. Integre o `spotlight` ao caminho de RAG do `12_agentic_rag`: todo documento recuperado deve ser escaneado e delimitado antes de entrar no prompt. Documente onde encaixar.
5. Troque a estimativa de tokens (~4 chars/token) por uma contagem real com `tiktoken` **apenas** se o pacote estiver instalado (import preguiçoso + degradação), mantendo o caminho determinístico por padrão.

## Referências
- OWASP Top 10 for LLM Applications 2025 — numeração e títulos: [https://genai.owasp.org/llm-top-10/](https://genai.owasp.org/llm-top-10/) (LLM01:2025 Prompt Injection, LLM06:2025 Excessive Agency, LLM10:2025 Unbounded Consumption).
- OWASP — LLM06:2025 Excessive Agency (mitigação com allowlist de ferramentas e aprovação humana): [https://genai.owasp.org/llmrisk/llm062025-excessive-agency/](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- OWASP — LLM10:2025 Unbounded Consumption: [https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/](https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/)
- Invariant Labs — "MCP Security Notification: Tool Poisoning Attacks" (instruções escondidas em `<IMPORTANT>` na descrição da ferramenta; exfiltração de `~/.ssh/id_rsa` e `mcp.json`; "rug pull" e "tool shadowing"): [https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks)
- Model Context Protocol — Security Best Practices (confused deputy, consentimento/human-in-the-loop): [https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices)
