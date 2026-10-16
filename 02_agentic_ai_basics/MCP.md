# 02 — MCP (Model Context Protocol): servidor mínimo

> Pré-requisitos: a parte central (handlers e testes puros) roda **sem LLM, sem
> rede e sem chave**. Subir o servidor de verdade e rodar o cliente exigem o
> pacote extra `mcp` **2.x** (API `MCPServer` / `Client`), instalado **só num
> venv seu**: o CI não o instala. Não precisa de Ollama.

O MCP (Model Context Protocol) padroniza a interface entre um agente e os
sistemas que ele usa (dados e ferramentas). Em vez de cada agente reinventar
como falar com a nossa base de CVEs, descrevemos a capacidade **uma vez** (uma
tool nomeada, com assinatura tipada e docstring) e qualquer host compatível com
MCP descobre e chama essa tool sozinho. Este módulo expõe o `search_cves` /
`get_cve_by_id` do repo como um servidor MCP mínimo e o exercita por um cliente.

## Por que importa

- **ACI (Agent-Computer Interface) padronizada.** Assim como uma API web
  padroniza app ↔ serviço, o MCP padroniza agente ↔ sistema. Uma tool bem
  desenhada (nome claro, parâmetros tipados, docstring, erros úteis) é "boa UX
  para o modelo": reduz chamada errada e alucinação de parâmetro.
- **Desacoplamento.** O servidor publica _o que_ sabe fazer; o cliente/host
  decide _quando_ usar. Troca-se o host (IDE, chat, agente) sem mexer na tool.
- **Transporte único.** O mesmo servidor fala stdio (processo local), HTTP
  streamable e SSE. Aqui usamos **stdio**: o host sobe o servidor como
  subprocesso e conversa por stdin/stdout.

## Conceitos

- **Server**: processo que expõe capacidades. Aqui: `MCPServer("cve-knowledge-base")`.
- **Client / Host**: quem conecta, descobre e invoca. Aqui: `mcp.Client`.
- **Tool**: função chamável pelo modelo. A assinatura tipada _é_ o schema: não
  escrevemos JSON Schema na mão. Registramos duas:
  - `lookup_cve(cve_id)`: busca um CVE pelo id exato;
  - `search_cves(query, limit=10)`: busca por palavra-chave.
- **Resource**: conteúdo endereçável para leitura (não é ação). Expomos
  `cve://{cve_id}`, que entrega o mesmo registro como recurso lido pelo host.
- **Prompt**: template de conversa reutilizável (não usado aqui; faz parte do
  protocolo).

### Design de tools (o que guiou este servidor)

- **O nome diz a intenção:** `lookup_cve` (id exato) vs. `search_cves`
  (descoberta por texto). O modelo escolhe pela diferença semântica.
- **Parâmetros tipados e mínimos:** `cve_id: str`, `query: str`, `limit: int`.
  O tipo vira schema; menos campos livres = menos erro.
- **Erros úteis, não stack traces:** id vazio/malformado → mensagem com o
  formato esperado (`CVE-YYYY-NNNN`); id inexistente → mensagem que _sugere a
  outra tool_ (`use 'search_cves' para descobrir ids`). No SDK isso é feito
  levantando `ToolError`, que o cliente recebe como erro limpo com a mensagem
  (uma exceção qualquer viraria um erro interno opaco).
- **Lógica separada do SDK:** os _handlers_ (`lookup_cve`, `search_cves_tool`)
  são funções puras, testáveis sem `mcp`; o SDK é importado **lazy** dentro de
  `build_server()`. Assim o CI (sem `mcp`) ainda importa e testa o módulo.
- **Reuso sem acoplar dependência:** a lógica vem de `utils.data_loader`
  (`get_cve_by_id`, `search_cves`). Não importamos `utils.tools`: ele usa o
  decorator `@tool` do LangChain, que não faz parte do CI.

## Arquivos

- [`mcp_server.py`](mcp_server.py): handlers puros (`lookup_cve`,
  `search_cves_tool`) com erros úteis; `build_server()`, que importa o SDK de
  forma lazy e registra as duas tools + o resource `cve://{id}`; `main()`, que
  roda em stdio.
- [`mcp_client_demo.py`](mcp_client_demo.py): cliente do SDK oficial que sobe o
  servidor via stdio, lista as tools, chama `search_cves` e `lookup_cve`, lê o
  resource e mostra o caminho de erro.
- [`../tests/test_mcp_server.py`](../tests/test_mcp_server.py): testa os
  handlers sem SDK; testa `build_server()` com `pytest.importorskip("mcp")`.

## Como rodar

Instale o SDK num venv seu (o CI não o tem). O código usa a API **2.x** do
pacote (`from mcp.server import MCPServer`, `mcp.Client`); foi validado com o
`mcp` 2.3.0. As versões 1.x expunham outra API (`FastMCP`) e não servem:

```powershell
python -m venv --system-site-packages .venv-mcp
.\.venv-mcp\Scripts\python.exe -m pip install "mcp>=2.3"
```

A partir da **raiz do repo** (com `PYTHONPATH` apontando para a raiz, para o
`from utils...` resolver):

```powershell
$env:PYTHONPATH = "."
# subir só o servidor (fica aguardando no stdio):
.\.venv-mcp\Scripts\python.exe -m 02_agentic_ai_basics.mcp_server
# ou rodar o cliente, que sobe o servidor como subprocesso e o exercita:
.\.venv-mcp\Scripts\python.exe -m 02_agentic_ai_basics.mcp_client_demo
```

## O que a demo mostra

Saída **real** de `python -m 02_agentic_ai_basics.mcp_client_demo` (as
descrições longas dos CVEs estão abreviadas aqui com `[...]`; no terminal saem
completas):

```text
=== Tools advertised by the server ===
- lookup_cve: Look up one CVE by its exact id (e.g. 'CVE-2021-44228').
- search_cves: Search CVEs by keyword; returns a list of matching records.

=== call search_cves(query='sql injection') ===
{
  "id": "CVE-2024-5678",
  "severity": "HIGH",
  "score": 8.2,
  "description": "SQL injection vulnerability in AuthService v1.5 [...]",
  "affected_versions": [
    "1.4",
    "1.5"
  ],
  "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"
}

=== call lookup_cve(cve_id='CVE-2024-5678') ===
{
  "id": "CVE-2024-5678",
  "severity": "HIGH",
  "score": 8.2,
  "description": "SQL injection vulnerability in AuthService v1.5 [...]",
  "affected_versions": [
    "1.4",
    "1.5"
  ],
  "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"
}

=== read_resource('cve://CVE-2024-5678') ===
{
  "id": "CVE-2024-5678",
  "severity": "HIGH",
  "score": 8.2,
  "description": "SQL injection vulnerability in AuthService v1.5 [...]",
  "affected_versions": [
    "1.4",
    "1.5"
  ],
  "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"
}

=== call lookup_cve(cve_id='CVE-0000-0000') (expected error) ===
is_error: True
Error executing tool lookup_cve: No CVE found with id 'CVE-0000-0000'. Use the 'search_cves' tool to discover available identifiers.
```

Repare: a tool `search_cves` descobre o id, `lookup_cve` e o resource
`cve://...` devolvem o mesmo registro, e o id inexistente volta como **erro
limpo com mensagem acionável** (`is_error: True`), não como stack trace.

## Como registrar o servidor num agente

Um host MCP (por exemplo, o Claude Desktop) sobe servidores locais a partir de
um arquivo de configuração JSON com a chave `mcpServers`. Na doc oficial (ver
Referências), cada entrada tem um `command` e um array `args`, com **caminhos
absolutos**; no Windows, o arquivo do Claude Desktop fica em
`%APPDATA%\Claude\claude_desktop_config.json`, e é preciso reiniciar o app
depois de editar.

Este módulo tem um detalhe a mais: como o nome do pacote começa com dígito, ele
só roda com `python -m` **a partir da raiz do repo** (e com a raiz no
`PYTHONPATH`, para o `from utils...` resolver). Por isso o exemplo abaixo usa
também `cwd` e `env`. **Essas duas chaves não aparecem no guia oficial:**
confira na documentação do seu host se ele as aceita.

```json
{
  "mcpServers": {
    "cve-knowledge-base": {
      "command": "C:\\caminho\\para\\.venv-mcp\\Scripts\\python.exe",
      "args": ["-m", "02_agentic_ai_basics.mcp_server"],
      "cwd": "C:\\caminho\\para\\llm-study",
      "env": { "PYTHONPATH": "C:\\caminho\\para\\llm-study" }
    }
  }
}
```

## Exercícios

1. Adicione uma tool `list_cves()` que devolva só os ids e as severidades (um
   "índice" barato antes de puxar o registro inteiro). Pense no nome e na
   docstring do ponto de vista do modelo.
2. Faça `search_cves` aceitar um filtro opcional `severity: str | None` e
   valide-o contra `SeverityLevel`; devolva um erro útil para valor inválido.
3. Escreva um teste que, com `pytest.importorskip("mcp")`, suba o servidor via
   `Client` e afirme que `lookup_cve` de um id inexistente volta com
   `is_error = True`.
4. Troque o transporte para `streamable-http` (`server.run(transport=...)`) e
   conecte um `Client` por URL. O que muda no cliente? O que **não** muda na
   definição das tools?
5. Adicione um `Prompt` (template de conversa) que peça ao modelo para resumir
   um CVE a partir do resource `cve://{id}`.

## Referências

- SDK oficial Python do MCP (README: `MCPServer`, `Client`, transportes):
  [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- Guia oficial "Connect to local MCP servers" (formato `mcpServers` /
  `command` / `args`, caminho do config no Windows):
  [modelcontextprotocol.io/quickstart/user](https://modelcontextprotocol.io/quickstart/user)
- Site oficial do protocolo:
  [modelcontextprotocol.io](https://modelcontextprotocol.io)
