# Configuração do LLM

O `utils.llm_client` fala com **qualquer endpoint compatível com a API da OpenAI**. Ollama, LM Studio e a própria OpenAI funcionam só trocando variáveis do `.env`. As variáveis têm o prefixo `OLLAMA_` porque o Ollama é o padrão do projeto, mas valem para qualquer provedor.

| Provedor | Setup | Observações |
|----------|-------|-------------|
| **Ollama** (local) | `ollama serve` → `ollama pull mistral` | Grátis, offline, sem chave |
| **LM Studio** (local) | Baixar um modelo na interface e iniciar o servidor local | Alternativa gráfica ao Ollama |
| **OpenAI** (nuvem) | `OPENAI_API_KEY` no `.env` | Pago por token |

---

## Opção 1: Ollama (recomendado para estudar)

**Por que o Ollama?**
- ✅ **Grátis:** sem chave nem assinatura
- ✅ **Privado:** os dados não saem da sua máquina
- ✅ **Rápido:** baixa latência para iterar
- ✅ **Offline:** funciona sem internet
- ✅ **Vários modelos:** Mistral, Llama, Qwen, Gemma etc.

**Setup:**

1. **Instale** o Ollama: https://ollama.com/download (no Windows, feche e reabra o terminal depois de instalar).
2. **Suba o servidor** num terminal separado e deixe rodando:
   ```bash
   ollama serve
   ```
   Deve mostrar `Listening on 127.0.0.1:11434`.
3. **Baixe um modelo** (só na primeira vez):
   ```bash
   ollama pull mistral   # padrão do projeto (~4 GB)
   ```
   Outros modelos: veja a biblioteca em https://ollama.com/library e use em `OLLAMA_MODEL` o nome exato que o `ollama list` mostra. Modelos menores rodam mais rápido em máquinas modestas.
4. **Configure o `.env`:**
   ```
   OLLAMA_MODEL=mistral:latest
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OPENAI_API_KEY=ollama
   ```
5. **Verifique** (deve listar os modelos baixados):
   ```bash
   curl http://localhost:11434/api/tags                 # Bash
   Invoke-RestMethod http://localhost:11434/api/tags    # PowerShell
   ```

---

## Opção 2: LM Studio (interface gráfica)

- Interface visual para rodar LLMs locais, sem terminal.
- **Setup:** baixe em https://lmstudio.ai, carregue um modelo e inicie o servidor local. A porta padrão é **1234**, e a API compatível com OpenAI fica em `http://localhost:1234/v1` (veja a [doc oficial](https://lmstudio.ai/docs/developer/openai-compat)).
- **`.env`:**
  ```
  OLLAMA_BASE_URL=http://localhost:1234/v1
  OPENAI_API_KEY=lm-studio
  OLLAMA_MODEL=<identificador do modelo carregado no LM Studio>
  ```
  O valor de `OPENAI_API_KEY` é ignorado localmente, mas a biblioteca exige um.

---

## Opção 3: OpenAI (nuvem)

**Quando usar:** aplicações de produção, quando precisa de modelos maiores ou de alto throughput.

1. Crie uma chave em https://platform.openai.com/api-keys.
2. Configure o `.env`:
   ```
   OPENAI_API_KEY=sk-xxxxxxxxxxxx
   OLLAMA_BASE_URL=https://api.openai.com/v1
   OLLAMA_MODEL=gpt-4o-mini   # exemplo; veja a lista atual em https://platform.openai.com/docs/models
   ```
   Não existe `OPENAI_MODEL`: o modelo é sempre `OLLAMA_MODEL`.

**Custo:** cobrado por token. Consulte os valores atuais na [página de preços oficial](https://openai.com/api/pricing/).

---

## Opção 4: outros provedores (Anthropic, Google etc.)

Esses **exigem mudança de código**: o `utils/llm_client.py` usa o `ChatOpenAI` do LangChain. Para outro provedor, troque-o pela integração correspondente do LangChain e configure as variáveis daquele provedor:

```python
# Em utils/llm_client.py, no lugar de ChatOpenAI:
# from langchain_anthropic import ChatAnthropic                # Claude  (ANTHROPIC_API_KEY)
# from langchain_google_genai import ChatGoogleGenerativeAI    # Gemini
```

Cada provedor tem sua própria configuração; veja as [integrações do LangChain](https://python.langchain.com/docs/integrations/llms/).

---

## Trocando de provedor (resumo)

| De → para | O que muda no `.env` |
|-----------|----------------------|
| Ollama → OpenAI | `OPENAI_API_KEY=sk-...`, `OLLAMA_BASE_URL=https://api.openai.com/v1`, `OLLAMA_MODEL=<modelo da OpenAI>` |
| Ollama → LM Studio | `OLLAMA_BASE_URL=http://localhost:1234/v1`, `OLLAMA_MODEL=<modelo carregado>` |
| Ollama → Anthropic/Google | Não é só `.env`: veja a [Opção 4](#opção-4-outros-provedores-anthropic-google-etc) |

`LLM_TEMPERATURE` e `LLM_MAX_TOKENS` definem os padrões do cliente para qualquer provedor.

---

## 🔐 Boas práticas com credenciais

**Faça:**
```
✅ Guarde no .env (já está no .gitignore)
✅ Use variáveis de ambiente em produção
✅ Rotacione as chaves periodicamente
✅ Use chaves com o menor privilégio possível (só leitura quando der)
✅ Monitore o uso da API para pegar cobranças inesperadas
```

**Não faça:**
```
❌ Commitar chaves no git
❌ Compartilhar o arquivo .env
❌ Usar a mesma chave em vários projetos
❌ Deixar credenciais fixas no código
❌ Logar chaves em saída de debug
```

**Em produção:**
- Use um gerenciador de segredos (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault)
- Defina as variáveis de ambiente no servidor/container
- Rotacione as chaves a cada 90 dias
- Use chaves diferentes para dev, staging e produção

---

## Problemas comuns

### Conexão com o LLM

| Problema | Soluções |
|----------|----------|
| `Connection refused` no Ollama | 1. Suba o Ollama em outro terminal: `ollama serve` · 2. Confira a porta: `curl http://localhost:11434/api/tags` · 3. Reinicie o Ollama (pode ter caído) · 4. Confira `OLLAMA_BASE_URL` no `.env` (`http://localhost:11434/v1`) |
| `model not found` ou respostas vazias | 1. Veja os modelos instalados: `ollama list` · 2. Baixe o modelo: `ollama pull mistral` · 3. Confira se `OLLAMA_MODEL` bate com um modelo instalado |
| `ollama: command not found` | Feche e reabra o terminal depois de instalar o Ollama |
| Porta 11434 já em uso | Outro processo (ou outro Ollama) está nela: encerre-o, ou rode o Ollama em outra porta e ajuste `OLLAMA_BASE_URL` |
| LLM muito lento ou usando muita memória | 1. Use um modelo menor (veja https://ollama.com/library) · 2. Reduza `LLM_MAX_TOKENS` (menos saída = mais rápido) · 3. Mais RAM/swap · 4. Use um LLM na nuvem |

### Credenciais

| Problema | Soluções |
|----------|----------|
| `401 Unauthorized` na OpenAI | 1. Confira se `OPENAI_API_KEY` está definida · 2. Valide a chave em https://platform.openai.com/api-keys · 3. A chave pode ter sido revogada: gere outra · 4. Chaves da OpenAI começam com `sk-` |
| `Invalid API key` no Pinecone | 1. Confira `PINECONE_API_KEY` no `.env` · 2. Valide a chave em https://www.pinecone.io · 3. Crie um índice chamado `llm-study` |
| Perdeu a chave | Gere uma nova no painel do provedor e atualize o `.env` |

### Python e ambiente

| Problema | Soluções |
|----------|----------|
| `ModuleNotFoundError` | 1. Ative o venv (`.venv\Scripts\Activate.ps1` no Windows, `source .venv/bin/activate` no Linux/macOS) · 2. `pip install -r requirements.txt` · 3. Teste: `python -c "import langchain; print('OK')"` |
| `No module named 'utils'` | Rode a partir da raiz do projeto com `$env:PYTHONPATH = "."` (PowerShell) ou `export PYTHONPATH="."` (Bash), usando `python -m NN_modulo.script` |
| Problemas com a versão do Python | Use Python 3.11 (`python --version`), crie um venv novo e reinstale as dependências |

### Dados

| Problema | Soluções |
|----------|----------|
| Banco vetorial vazio ou com dados antigos | Apague `data/chroma` (`rm -r data/chroma`, ou `rmdir /s data\chroma` no cmd) e rode `python -m 04_advanced_workflows.chroma_rag` |
| Base de CVEs não carrega | Confira se `utils/data/cves.json` existe (ele está versionado no git) |

---

## Testes rápidos

```powershell
# 1. Ollama instalado?
ollama --version

# 2. Quais modelos?
ollama list

# 3. Python + LLM pelo cliente do projeto (a partir da raiz, com PYTHONPATH=".")
python -c "from utils.llm_client import get_llm_client; print(get_llm_client().generate('Oi!', max_tokens=50))"
```
