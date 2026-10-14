# 11 — Memória Conversacional (Short-Term & Long-Term)

> Os agentes construídos nos módulos anteriores são **stateless**: cada chamada
> enxerga só o prompt que recebeu e esquece tudo depois. Este módulo mostra como
> dar **memória** a um agente — as duas metades que todo assistente de produção
> combina: memória de curto prazo (a conversa recente) e memória de longo prazo
> (conhecimento durável, recuperado por significado).

## Por que importa no mercado

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

## Short-term memory — janela deslizante + sumarização

O problema: a janela de contexto do LLM é finita e cobrar por tokens significa
que mandar a conversa inteira a cada turno é caro e, eventualmente, impossível.

A solução em `memory_store.py`:

- **Janela deslizante**: mantém só os últimos `N` turnos *literais*. O tamanho do
  contexto fica limitado por mais longa que a conversa seja.
- **Gatilho de sumarização**: quando um turno novo empurraria a conversa para
  além da janela, os turnos mais antigos que "caem" não são jogados fora — são
  comprimidos num **resumo corrente** (um turno `system`) para que a essência
  sobreviva. A compressão é cumulativa: cada nova evicção dobra o resumo
  anterior no próximo.
- **Sumarizador com fallback**: a compressão usa o cliente central
  (`client.generate`). Se não houver LLM/Ollama, cai num **resumo determinístico**
  (role + trecho de cada turno) — por isso o self-test roda 100% offline.

A classe `ConversationMemory` expõe `add_turn`/`add_user`/`add_assistant` para
alimentar a conversa e `get_messages()` para montar a lista pronta para o
`LLMClient.chat` (resumo como `system` + janela literal).

## Long-term memory — memória semântica sobre a base de CVEs

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
(semantic) e, se o modelo de embeddings não puder ser carregado (offline/sem
cache), degrada sozinha para **BM25** (keyword puro). Só a *geração* da resposta
final precisa de LLM — sem ele, o script ainda imprime o contexto recuperado,
então o passo de recall é totalmente demonstrável offline.

## Arquivos

- `__init__.py` — marca o diretório como pacote.
- `memory_store.py` — memória de curto prazo: a classe `ConversationMemory`
  (janela deslizante + gatilho de sumarização), com sumarizador LLM e fallback
  determinístico. O `__main__` testa a janela e o trigger **sem LLM**.
- `long_term_memory.py` — memória de longo prazo: a classe `LongTermMemory`
  (recall semântico sobre a base de CVEs, com fallback para BM25) e um `__main__`
  que recupera conhecimento sem Ollama e tenta a geração final se houver LLM.

## Como rodar

Na raiz do projeto, com `PYTHONPATH` apontando para ela:

```powershell
$env:PYTHONPATH = "."

# Curto prazo — self-test determinístico, NÃO precisa de Ollama:
python -m 11_memory.memory_store

# Longo prazo — a recuperação roda sem Ollama; a geração final é pulada
# com uma mensagem clara se nenhum backend de LLM estiver no ar:
python -m 11_memory.long_term_memory
```

Se o backend de LLM não estiver disponível, nada trava: `memory_store.py` usa o
resumidor determinístico e `long_term_memory.py` recupera o contexto e informa
que a geração foi pulada. Com Ollama no ar, a sumarização e a resposta final
passam a usar o modelo automaticamente.
