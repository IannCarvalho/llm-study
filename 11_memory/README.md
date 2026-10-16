# 11 — Memória Conversacional (curto e longo prazo)

> Pré-requisitos: roda sem LLM. A recuperação e os self-tests são
> determinísticos e offline; só a *geração* da resposta final usa o LLM (Ollama),
> e degrada com elegância quando ele não está no ar. Nenhum pacote extra além dos
> que o projeto já instala.

Os agentes dos módulos anteriores são **stateless**: cada chamada enxerga só o
prompt que recebeu e esquece tudo depois. Este módulo dá **memória** a um agente,
nas duas metades que todo assistente de produção combina: memória de curto prazo
(a conversa recente) e memória de longo prazo (conhecimento durável, recuperado
por significado).

## Por que importa

Memória é o que separa um "wrapper de prompt" de um assistente de verdade. Sem
ela o agente repete perguntas, perde o fio da conversa e não aproveita nada do
que já sabe. As duas técnicas aqui são exatamente as que aparecem em sistemas
reais (ChatGPT, Claude, copilots): **janela + sumarização** para caber no
contexto sem estourar custo, e **recuperação semântica** para lembrar fatos que
nunca estiveram na conversa atual.

| Tipo | O que guarda | Como lembra | Precisa de LLM? |
|------|--------------|-------------|-----------------|
| Curto prazo | os últimos N turnos da conversa | janela deslizante + resumo | só na sumarização (com fallback) |
| Longo prazo | base de conhecimento durável | busca semântica (embeddings) | só na geração final |

## Conceitos

### Curto prazo — janela deslizante + sumarização

O problema: a janela de contexto do LLM é finita e, como se paga por tokens,
mandar a conversa inteira a cada turno é caro e, eventualmente, impossível.

A solução em `memory_store.py`:

- **Janela deslizante**: mantém só os últimos `N` turnos *literais*. O tamanho do
  contexto fica limitado por mais longa que a conversa seja.
- **Gatilho de sumarização**: quando um turno novo empurraria a conversa para
  além da janela, os turnos mais antigos que "caem" não são jogados fora — são
  comprimidos num **resumo corrente** (um turno `system`) para que a essência
  sobreviva. A compressão é cumulativa: cada evicção dobra o resumo anterior no
  próximo, em vez de reescrever o cabeçalho a cada vez.
- **Sumarizador com fallback**: a compressão usa o cliente central
  (`client.generate`). Se não houver LLM/Ollama, cai num **resumo determinístico**
  (role + trecho de cada turno) — por isso o self-test roda 100% offline.

A classe `ConversationMemory` expõe `add_turn` / `add_user` / `add_assistant`
para alimentar a conversa e `get_messages()` para montar a lista pronta para o
`LLMClient.chat` (resumo como `system` + janela literal). O padrão de
`window_size` é `4`; o sumarizador padrão é o apoiado em LLM, que por sua vez já
degrada para o determinístico quando nenhum backend responde.

### Longo prazo — memória semântica sobre a base de CVEs

A janela, por projeto, **esquece**: o que sai dela some (ou vira resumo grosso).
A memória de longo prazo resolve a outra metade — guardar conhecimento de forma
durável e trazer de volta o pedaço *relevante* sob demanda, não importa há quanto
tempo foi visto.

A implementação padrão é um vector store consultado por significado. Em
`long_term_memory.py` reaproveitamos a própria stack de recuperação do projeto
como esse store de longo prazo:

- a base de CVEs (`get_cve_documents()`) faz o papel de memória durável;
- `create_search_engine('semantic')` (ou `'hybrid'`) é o mecanismo de recall por
  significado;
- dada a pergunta do usuário, os melhores matches são recuperados e **injetados
  no contexto** do prompt — exatamente como um agente estilo RAG "lembra" fatos
  que ninguém falou na conversa atual.

A **recuperação é determinística e sem Ollama**: usa embeddings locais
(`'semantic'`) e, se o modelo de embeddings não puder ser carregado (offline, sem
cache), a classe `LongTermMemory` degrada sozinha para **BM25** (keyword puro) —
imprimindo um aviso e seguindo. Só a *geração* da resposta final precisa de LLM:
sem ele, `answer()` devolve `None` e avisa que a geração foi pulada, enquanto
`recall()` e `build_context()` continuam entregando o contexto recuperado.

## Arquivos

- `memory_store.py` — memória de curto prazo: a classe `ConversationMemory`
  (janela deslizante + gatilho de sumarização), com o sumarizador apoiado em LLM
  (`_llm_summary`) e o fallback determinístico (`_deterministic_summary`). O
  `main()` testa a janela e o trigger **sem LLM**.
- `long_term_memory.py` — memória de longo prazo: a classe `LongTermMemory`
  (`recall` / `build_context` / `answer`, recall semântico sobre a base de CVEs,
  com fallback para BM25) e um `main()` que recupera conhecimento sem Ollama e
  tenta a geração final se houver LLM.
- `__init__.py` — marca o diretório como pacote.
- `README.md` — este arquivo.

Setup de provedor de LLM (Ollama, LM Studio, OpenAI): veja
[../LLM_SETUP.md](../LLM_SETUP.md).

## Como rodar

A partir da raiz do projeto, com `PYTHONPATH` apontando para ela.

**PowerShell:**
```powershell
$env:PYTHONPATH = "."

# Curto prazo — self-test determinístico, NÃO precisa de Ollama:
python -m 11_memory.memory_store

# Longo prazo — a recuperação roda sem Ollama; a geração final é pulada
# com uma mensagem clara se nenhum backend de LLM estiver no ar:
python -m 11_memory.long_term_memory
```

**Bash:**
```bash
export PYTHONPATH="."

python -m 11_memory.memory_store
python -m 11_memory.long_term_memory
```

Se o backend de LLM não estiver disponível, nada trava: `memory_store.py` usa o
resumidor determinístico e `long_term_memory.py` recupera o contexto e informa
que a geração foi pulada. Com Ollama no ar, a sumarização e a resposta final
passam a usar o modelo automaticamente.

## O que a demo mostra

`memory_store.py` (sem LLM): com `window_size = 4`, os quatro primeiros turnos
entram literais; a partir do quinto, a janela permanece em 4 e o resumo é
acionado. Trecho real da saída:

```
window_size = 4

after turn  1 (user     ) -> window holds 1 turn(s), summary=no
...
after turn  5 (user     ) -> window holds 4 turn(s), summary=yes
after turn  6 (assistant) -> window holds 4 turn(s), summary=yes
after turn  7 (user     ) -> window holds 4 turn(s), summary=yes

Running summary (compressed evicted history):
Earlier conversation (summarized):
- user: Which CVE is the critical RCE?
- assistant: CVE-2024-1234 is a CRITICAL remote code execution (score 9.8).
- user: And the SQL injection one?
```

Os turnos que saíram da janela só existem agora dentro do resumo; os quatro mais
recentes seguem literais na lista enviada ao LLM (resumo como `system` + janela).

`long_term_memory.py` (recuperação sem Ollama; geração pulada): a classe carrega
as 3 memórias de CVE e recupera por significado. Trecho real da saída:

```
Store: 3 CVE memories | retrieval method: 'semantic'

Question: "Was there a remote code execution bug in the request handler?"
  Recalled 2 memory/memories (ranked):
    - CVE-2024-1234 (score 0.501) :: CVE ID: CVE-2024-1234
    - CVE-2024-5678 (score 0.192) :: CVE ID: CVE-2024-5678
[long-term memory] LLM generation skipped (no backend: Connection error.).
```

O recall ranqueia corretamente o CVE certo (maior score) mesmo sem nenhum termo
em comum literal; só o passo de geração é pulado por não haver LLM no ar — com
Ollama rodando, `answer()` produziria uma resposta ancorada nesse contexto.

## Exercícios

1. Mude `window_size` de `4` para `2` em `ConversationMemory` e rode
   `memory_store` de novo: observe que o resumo passa a disparar mais cedo (no
   terceiro turno) e mais turnos acabam comprimidos.
2. Passe o `_deterministic_summary` explicitamente como `summarizer=` ao construir
   a `ConversationMemory` e confirme pela saída que o comportamento é idêntico ao
   padrão quando o LLM está fora — é esse o caminho que torna o módulo testável
   offline.
3. Em `long_term_memory`, troque `method="semantic"` por `method="bm25"` no
   `main()` e compare os scores e o ranking das mesmas duas perguntas: veja onde
   keyword puro acerta e onde a busca semântica leva vantagem.
4. Force o fallback: chame `LongTermMemory(method="hybrid")` sem o modelo de
   embeddings em cache (offline) e confirme pela mensagem `falling back to 'bm25'`
   que a recuperação não quebra — só muda de mecanismo.
5. Alimente uma conversa real com `add_user`/`add_assistant` até a janela estourar
   e imprima `get_messages()`: verifique que o primeiro item é o turno `system`
   com o resumo e que os demais são a janela literal.

## Referências

- [Documentação do LangChain](https://python.langchain.com/)
- [Modelos do Ollama](https://ollama.com/library)
