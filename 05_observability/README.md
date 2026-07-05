# 🔍 Módulo 5: Observability — LangSmith & LangFuse

## O que está aqui?

Este módulo ensina **como observar e debugar agentes** — essencial em produção para:
- Entender o que o agente está fazendo
- Debugar erros
- Medir latência e custo
- Receber feedback de usuários
- Comparar diferentes versões

---

## 📋 Arquivos do Módulo

### 1. **langsmith_demo.py** — Observabilidade Automática (LangChain)
**O que é**: Plataforma oficial de LangChain para tracing e debugging

**Setup**:
1. Criar conta em https://smith.langchain.com (gratuito)
2. Gerar API key
3. Configurar variáveis de ambiente

**Configuração**:
```python
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "seu-api-key"
os.environ["LANGCHAIN_PROJECT"] = "qubika-study"
```

### 2. **langfuse_demo.py** — Analytics Detalhado (Langfuse)
```
Seu Código (LangChain/LangGraph)
    ↓
[Instrumentação Automática]
    ↓
LangSmith API
    ↓
Dashboard em https://smith.langchain.com
```

**O que você vê no Dashboard**:

1. **Traces** — Uma execução completa
```
Trace: "Analyze CVE-2024-1234"
├─ Start Time: 2024-01-15 10:45:32
├─ Duration: 2.34s
├─ Status: Success
└─ Total Tokens: 245
```

2. **Spans** — Operações dentro do trace
```
Span 1: call_llm
├─ Input: "Search for CVE-2024-1234"
├─ Duration: 1.8s
├─ Output: "Found critical vulnerability..."
└─ Tokens: 120

Span 2: tool_execution (search_cve)
├─ Duration: 0.4s
├─ Result: {"severity": "CRITICAL", ...}
```

3. **Latência por Componente**
```
search_cve: 400ms (tool)
llm_call_1: 1800ms (thinking)
llm_call_2: 140ms (analysis)
─────────────────────
Total: 2340ms
```

4. **Custo em Tokens**
```
Input Tokens: 145
Output Tokens: 100
Total: 245 tokens
Estimated Cost: $0.000735
```

**Exemplo Prático com LangChain**:
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

# Setup automático via .env
model = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# Isso já é traced!
response = model.invoke([
    HumanMessage(content="What is SQL injection?")
])

# Aparece automaticamente no dashboard
# Você vê:
# - Input: "What is SQL injection?"
# - Output: "SQL injection is..."
# - Latência: 1.2s
# - Tokens: 450
```

**Exemplo com LangGraph (Agente)**:
```python
from langgraph.graph import StateGraph, END

# Definir seu grafo normalmente...
graph = StateGraph(VulnerabilityState)
graph.add_node("analyze", analyze_func)
graph.add_node("escalate", escalate_func)
app = graph.compile()

# Execução automática é tracida
result = app.invoke({
    "query": "Analyze CVE-2024-1234"
})

# Dashboard mostra:
# - Cada nó executado
# - Transições entre nós
# - Estado em cada passo
# - Decisões de roteamento
```

**Vantagens LangSmith**:
- ✅ Integração automática com LangChain/LangGraph
- ✅ Zero código extra necessário
- ✅ Ricas visualizações
- ✅ Fácil debugging
- ✅ Comparar runs diferentes
- ✅ Feedback de usuários

**Desvantagens**:
- ❌ Requer conta na plataforma
- ❌ Dados enviados para servers LangChain
- ❌ Pode ter custo em escala
- ❌ Vendor lock-in

**Rodar**:
```bash
# Setup: configure LANGCHAIN_API_KEY primeiro
python 03_observability/langsmith_example.py

# Output:
# Saiba onde ir: https://smith.langchain.com
# Veja seus traces lá!
```

---

### 2. **langfuse_example.py** — Observabilidade Open-Source
**O que é**: Alternativa open-source/self-hosted para LangSmith

**Diferencial**:
- Open-source (pode hospedar você mesmo)
- Funciona com Anthropic, OpenAI, Ollama, qualquer coisa
- Mais flexível
- Feedback explícito (scores, comments)

**Setup**:
```bash
# Opção 1: Cloud gratuito
pip install langfuse

# Opção 2: Self-hosted
git clone https://github.com/langfuse/langfuse
docker-compose up
```

**Configuração**:
```python
from langfuse import Langfuse
from langfuse.decorators import observe

# Cloud
langfuse = Langfuse(
    public_key="pk_...",
    secret_key="sk_...",
    host="https://cloud.langfuse.com"
)

# Self-hosted
langfuse = Langfuse(
    public_key="pk_...",
    secret_key="sk_...",
    host="http://localhost:3000"
)
```

**Dois Modos de Uso**:

#### Modo 1: Decoradores (Simples)
```python
from langfuse.decorators import observe

@observe()
def analyze_code_security(code: str) -> str:
    """Função automaticamente rastreada."""
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"Analyze code: {code}"
        }]
    )
    return response.content[0].text

# Usar normalmente
result = analyze_code_security("SELECT * FROM users WHERE id=" + user_input)
# Já está no LangFuse!
```

**O que aparece no dashboard**:
```
Trace: analyze_code_security
├─ Input: "SELECT * FROM users WHERE id=..."
├─ Output: "This code has SQL injection at..."
├─ Duration: 1.2s
├─ Model: claude-3-5-sonnet
├─ Tokens: 340
└─ Status: Completed
```

#### Modo 2: Tracing Manual (Controle Total)
```python
from langfuse import Langfuse

langfuse = Langfuse()

# Criar uma trace (execução completa)
trace = langfuse.trace(
    name="security_audit",
    input={"host": "example.com"}
)

# Criar spans (operações dentro da trace)
span1 = trace.span(name="port_scan")
# ... executar escaneo
span1.end(output={"ports": [80, 443, 22]})

span2 = trace.span(name="analyze_results")
# ... analisar
span2.end(output={"risk": "HIGH"})

# Finalizar
trace.end(output={"report": "..."})
```

**Feedback de Usuários**:
```python
trace = langfuse.trace(name="recommend_patch")
# ... executar
trace.generation_id = gen_id

# Depois o usuário diz se gostou
trace.score(
    name="user_feedback",
    value=1  # 0 = ruim, 1 = bom
)

# Ou comentário
trace.metadata = {
    "comment": "Patched successfully"
}
```

**Vantagens LangFuse**:
- ✅ Open-source (pode auto-hospedar)
- ✅ Funciona com ANY LLM
- ✅ Feedback explícito
- ✅ Mais controle
- ✅ Sem vendor lock-in

**Desvantagens**:
- ❌ Requer setup manual se self-hosted
- ❌ Menos integrado que LangSmith
- ❌ Comunidade menor

**Rodar**:
```bash
pip install langfuse

python 03_observability/langfuse_example.py
```

---

## 🎓 Conceitos Chave

### Trace
Uma execução completa do seu sistema
```
User Query
    ↓ ┌─────────────────────── TRACE ──────────────────────┐
    ↓ │                                                      │
    ├─→ [Span 1: Parse Query]                               │
    │   ↓                                                    │
    ├─→ [Span 2: Search Vector DB]                          │
    │   ↓                                                    │
    ├─→ [Span 3: Call LLM with Context]                     │
    │   ↓                                                    │
    ├─→ [Span 4: Format Response]                           │
    ↓ │                                                      │
Final Output                                                │
    └──────────────────────────────────────────────────────┘
```

### Span
Uma operação dentro da trace
```
Span: "search_vector_db"
├─ Input: {"query": "SQL injection", "top_k": 5}
├─ Duration: 234ms
├─ Output: [{"id": "vuln_1", "score": 0.94}, ...]
└─ Status: Success
```

### Latency Analysis
```
Total: 2.45s
├─ Vector DB Search: 234ms (10%)
├─ LLM Call: 1800ms (73%)  ← Bottleneck!
├─ Post-processing: 120ms (5%)
└─ Network: 291ms (12%)
```

### Token Usage
```
Input Tokens: 450
├─ System Prompt: 120
├─ Context (from DB): 180
└─ User Query: 150

Output Tokens: 320
├─ Main Response: 280
└─ Reasoning: 40

Total: 770 tokens
Cost: 770 * $0.003/1k ≈ $0.0023
```

---

## 🔧 Setup

### LangSmith
```bash
# 1. Criar conta
# https://smith.langchain.com

# 2. Copiar API key

# 3. Configurar .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-api-key-here
LANGCHAIN_PROJECT=qubika-study

# 4. Usar LangChain/LangGraph normalmente
# Tudo é automaticamente tracido!
```

### LangFuse (Cloud)
```bash
# 1. Criar conta
# https://cloud.langfuse.com

# 2. Instalar
pip install langfuse

# 3. Configurar
export LANGFUSE_PUBLIC_KEY=pk_...
export LANGFUSE_SECRET_KEY=sk_...
```

### LangFuse (Self-Hosted)
```bash
# 1. Docker
docker-compose up

# 2. Acessar
http://localhost:3000

# 3. Copiar credentials
# Configure em seu código
```

---

## 🧪 Testando Localmente

```bash
cd /path/to/qubika
.\venv\Scripts\activate.ps1

# Testar LangSmith (requer API key)
# python 03_observability/langsmith_example.py

# Testar LangFuse (requer setup)
python 03_observability/langfuse_example.py
```

---

## 💡 Casos de Uso — Interview Ready

### Caso 1: Debugging de Agente em Produção
```
"Agente ocasionalmente retorna resposta errada. Como debugar?"

Solução:
1. Olhar trace no LangSmith
2. Ver exatamente qual nó falhou
3. Ver inputs/outputs de cada span
4. Identificar bottleneck (LLM? Vector DB? Tool?)
5. Corrigir

Exemplo Real:
- Trace 1: LLM demorou 5s → aumentar timeout
- Trace 2: Vector DB retornou contexto errado → ajustar chunking
- Trace 3: Tool falhou → adicionar retry logic
```

### Caso 2: Custo x Qualidade
```
"Como balancear custo de tokens vs qualidade de resposta?"

Solução:
1. Medir tokens por trace em LangFuse
2. Comparar qualidade (user feedback score)
3. Ajustar:
   - Tamanho do contexto
   - Número de documentos recuperados
   - Prompt size
   - Model size

Exemplo:
- Versão 1: GPT-4 = $0.15/req, qualidade 0.95
- Versão 2: GPT-3.5 = $0.02/req, qualidade 0.87
- Versão 3: Ollama (local) = $0/req, qualidade 0.84
  → Escolher baseado em trade-off
```

### Caso 3: A/B Testing de Prompts
```
"Qual prompt funciona melhor?"

LangSmith permite:
1. Versão A: Prompt antigo
2. Versão B: Prompt novo
3. Comparar métricas:
   - Latência
   - Token usage
   - User feedback score
4. Decidir qual usar

Integração:
- Tag traces com versão
- Filtrar no dashboard
- Ver stats lado a lado
```

---

## 🎯 O que aprender daqui

1. **LangSmith**: Observabilidade automática para LangChain
2. **LangFuse**: Open-source alternativa
3. **Debugging**: Como encontrar problemas em agentes
4. **Métricas**: Latência, tokens, qualidade
5. **Feedback**: User feedback loops

**Pro Tip para Entrevista**:
> "Em produção, sempre use observabilidade. LangSmith para LangChain, LangFuse para qualquer coisa. Permite debugar rapidamente."

**Next**: Vá para `04_appsec/` para dominar vulnerabilidades!
