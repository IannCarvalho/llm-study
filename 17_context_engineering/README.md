# 17 — Context Engineering (Day 3.5 do roteiro)

> Pré-requisitos: **roda sem LLM** (parte central determinística, offline, sem
> Ollama/chave/rede). A comparação ao vivo de resposta+latência é opcional e só
> roda com um LLM acessível — sem ele, o script degrada com mensagem instrutiva.
> O número `17` é só identificador de diretório; no roteiro este tópico é o
> **Day 3.5 — Context Engineering**.

Engenharia de contexto é a arte de preencher a janela de contexto com *exatamente*
a informação certa a cada passo do agente. Mais contexto não é melhor contexto:
inflar a janela degrada qualidade e latência. Este módulo demonstra isso com os
CVEs reais do repo e aplica as quatro estratégias que corrigem o problema.

## Por que importa
Com janelas de 1M de tokens, a tentação é "jogar tudo no prompt". Mas o modelo
precisa prestar atenção em *tudo* que você coloca na janela — inclusive no lixo.
Context Engineering substituiu "prompt engineering" como diferencial sênior
porque é o que separa um agente que funciona de um que se perde. Você já pratica
partes dela sem nomear: RAG é *Select*; observabilidade (módulo 05) ajuda a
enxergar *context rot*.

## Conceitos
- **Janela de contexto**: a "RAM" do modelo. O mecanismo de atenção custa
  O(n²) no tamanho da entrada, então janela maior não escala de graça.
- **Lost in the middle**: modelos recuperam melhor a evidência que está no
  **início** ou no **fim** do contexto, e pior a que está no **meio** (Liu et al.,
  2023).
- **Context rot**: mesmo em tarefas simples, a precisão cai de forma não uniforme
  à medida que o número de tokens de entrada cresce (relatório da Chroma, 2025).
- **4 modos de falha** (Breunig, 2025):
  - *poisoning* — uma alucinação entra no contexto e é referenciada repetidamente;
  - *distraction* — o contexto cresce tanto que o modelo super-foca nele e esquece
    o que aprendeu no treino;
  - *confusion* — conteúdo supérfluo (mas parecido) é usado e piora a resposta;
  - *clash* — partes do contexto se contradizem.
- **4 estratégias** (LangChain, 2025):
  - **Write** — salvar informação *fora* da janela (scratchpad/notas, memória);
  - **Select** — puxar para a janela só o que é relevante (ex.: RAG top-k);
  - **Compress** — reduzir o que está na janela mantendo o essencial;
  - **Isolate** — separar o contexto (um subcontexto por sub-tarefa/sub-agente).

## Arquivos
- [`context_distraction.py`](context_distraction.py) — monta o contexto **focado**
  (só o CVE-alvo) e o **inflado** (o mesmo CVE enterrado em dezenas de distratores
  sintéticos, gerados **deterministicamente** a partir dos CVEs reais e marcados
  `[SYNTHETIC]`), coloca a evidência no **início/meio/fim**, mede tamanho em chars
  e em tokens estimados (bytes/4, uma *estimativa*, não um tokenizer real), e
  aplica as quatro estratégias mostrando o tamanho resultante e se a evidência
  sobrevive. Com LLM disponível (import lazy, opcional), pergunta com cada
  contexto e compara resposta e latência.
- [`__init__.py`](__init__.py) — marcador de pacote (vazio).
- [`../tests/test_context_engineering.py`](../tests/test_context_engineering.py) —
  testes determinísticos (sem rede, sem LLM, só `bm25`).

## Como rodar
A partir da **raiz** do repositório, com `PYTHONPATH` na raiz:

```powershell
$env:PYTHONPATH = "."
python -m 17_context_engineering.context_distraction
```

Testes:

```powershell
$env:PYTHONPATH = "."
python -m pytest tests/test_context_engineering.py -q
```

## O que a demo mostra
Trecho da saída **real** (sem Ollama — o passo com LLM é pulado com aviso):

```
Context sizes:
  focused (target only)                      chars=   894  ~tokens=  223  evidence=yes
  inflated (target buried among distractors) chars= 13796  ~tokens= 3449  evidence=yes

  -> inflating multiplied the window ~15.5x in estimated tokens, for the SAME single answer.

Applying the four strategies to the inflated context:

  SELECT (bm25 top-3)                        chars=  1444  ~tokens=  361  evidence=yes
  COMPRESS (relevant sentences only)         chars= 13753  ~tokens= 3438  evidence=yes
  WRITE (persisted scratchpad notes)         chars=   115  ~tokens=   28  evidence=yes
  ISOLATE[severity of CVE-2024-1234]         chars=  1169  ~tokens=  292  evidence=yes
  ISOLATE[what does CVE-2024-1234 allow an attacker to do] chars=  1168  ~tokens=  292  evidence=yes
```

Leitura: inflar o contexto multiplicou a janela ~15x **para a mesma resposta**.
`SELECT`, `ISOLATE` e `WRITE` reconstroem uma janela muito menor mantendo a
evidência real. `COMPRESS` quase não encolhe aqui **de propósito**: todo bloco
sintético também contém "CVE", "Severity" e o id, então a sobreposição léxica
ingênua mantém quase tudo — uma demonstração ao vivo de *context confusion*
(texto supérfluo mas parecido é difícil de descartar). Compressores reais usam
LLM ou embeddings para julgar significado, não palavras compartilhadas.

## Exercícios
1. Aumente `NUM_DISTRACTORS` de 40 para 200 e observe a janela inflada crescer —
   a resposta continua sendo uma linha.
2. Mude `COMPRESS` para pontuar sentenças pela sobreposição com a **evidência do
   alvo** (não só com a pergunta curta) e veja o tamanho cair de verdade.
3. Com Ollama ligado, rode o passo opcional e compare a resposta/latência entre
   contexto focado e inflado — veja se o modelo ainda cita o CVE certo.
4. Mova a cópia da evidência só para o **meio** do contexto inflado e discuta o
   efeito "lost in the middle" sobre um modelo real.
5. Combine `SELECT` + `COMPRESS` (comprima só o top-k recuperado) e meça a
   janela final.

## Referências
(Só fontes verificadas nesta tarefa, lidas via `web_fetch`.)
- Liu, N. F. et al. (2023). *Lost in the Middle: How Language Models Use Long
  Contexts*. TACL 2023. [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)
- Hong, K., Troynikov, A., Huber, J. (Chroma, 2025). *Context Rot: How Increasing
  Input Tokens Impacts LLM Performance*.
  [research.trychroma.com/context-rot](https://research.trychroma.com/context-rot)
- Breunig, D. (2025). *How Long Contexts Fail* (poisoning, distraction, confusion,
  clash).
  [dbreunig.com](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html)
- LangChain (2025). *Context Engineering* (Write / Select / Compress / Isolate).
  [blog.langchain.com/context-engineering-for-agents](https://blog.langchain.com/context-engineering-for-agents/)
