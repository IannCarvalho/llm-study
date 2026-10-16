# 00 — Prompting (variações de prompt sobre um CVE)

> **Pré-requisitos:** roda **sem LLM** (parte determinística: constrói/imprime os
> prompts e valida a saída estruturada). A execução ao vivo contra um modelo é
> **opcional** e requer **Ollama** rodando — sem ele o script explica como subir
> e termina com `exit 0`. Nenhum pacote extra além do que o repositório já usa.

Antes de recuperar contexto (RAG) ou dar ferramentas a um agente, é preciso saber
**pedir bem**. Este módulo é o Day 0 do roteiro: ele materializa a camada de
"como você pergunta" construindo **seis variações do mesmo pedido sobre o MESMO
CVE** da base única do projeto, de forma 100% determinística.

## Por que importa

A qualidade da resposta de um LLM depende tanto do *como* você pergunta quanto do
*modelo*. Trocar "Resuma este CVE." por um prompt com papel, exemplos ou um
contrato de formato muda radicalmente a saída — e um prompt que exige JSON é o
que permite integrar o modelo com código. Ver as variações lado a lado sobre o
mesmo dado isola exatamente o efeito do prompt.

## Conceitos

- **Zero-shot vs. few-shot (k-shot):** pedir direto, sem exemplos, vs. mostrar
  exemplos resolvidos para o modelo inferir o padrão (Brown et al. 2020).
- **Role prompting:** atribuir um papel/persona ("você é um analista de
  segurança escrevendo para um gestor") para guiar tom e público.
- **Chain-of-Thought (CoT):** pedir o raciocínio passo a passo antes da
  conclusão (Wei et al. 2022).
- **Contrato + contraste:** dizer o que **fazer** *e* o que **não fazer** no
  mesmo prompt (limites, proibições).
- **Saída estruturada (JSON mode):** exigir um objeto JSON com esquema fixo
  (`{id, severidade, resumo, acao_recomendada}`) para a resposta ser
  processável por código — e validável de forma determinística.

## Arquivos

- [`prompt_variants.py`](prompt_variants.py) — builders puros e determinísticos
  para cada variante (`build_zero_shot`, `build_few_shot`, `build_role`,
  `build_chain_of_thought`, `build_contract_contrast`, `build_structured` e
  `build_all_variants`); `extract_json` + `validate_structured_output`
  (validador determinístico: extrai o JSON mesmo dentro de cerca ```json,
  checa as chaves `id/severidade/resumo/acao_recomendada` e confirma que
  `severidade` ∈ `utils.models.SeverityLevel`); e `main()`.
- [`__init__.py`](__init__.py) — pacote vazio.
- [`../tests/test_prompting.py`](../tests/test_prompting.py) — testes
  determinísticos dos builders e do validador.

## Como rodar

A partir da **raiz do repositório** (os pacotes com prefixo numérico só rodam
via `-m`):

```powershell
$env:PYTHONPATH = "."
python -m 00_prompting.prompt_variants
```

Sem Ollama, a parte determinística roda inteira e o script encerra explicando
como subir o modelo. Com Ollama no ar (`ollama serve` + `ollama pull mistral`),
ele também executa cada variante contra o modelo e valida a saída estruturada.

## O que a demo mostra

Trecho da saída real (execução **sem Ollama** nesta máquina):

```
======================================================================
Day 0 — Prompting: seis variacoes sobre o MESMO CVE
CVE alvo: CVE-2024-1234 (CRITICAL, CVSS 9.8)
Exemplos few-shot: CVE-2024-5678, CVE-2024-9012
======================================================================

----------------------------------------------------------------------
VARIANTE: zero_shot
----------------------------------------------------------------------
Resuma este CVE.
...
======================================================================
Validador deterministico da saida estruturada (sem LLM)
======================================================================
  amostra valida    : OK
  amostra invalida  : REJEITADA (severidade 'URGENTE' fora de SeverityLevel ...)
...
[info] Nenhum backend de LLM acessivel — a parte deterministica acima ja rodou por completo.
```

## Exercícios

1. Rode a demo e compare os seis prompts: o que a variante *role* acrescenta ao
   *zero-shot*? E o *contract+contrast*?
2. Suba o Ollama e observe as respostas reais: qual variante produz o resumo
   mais útil para um gestor? Qual é mais consistente entre execuções?
3. Quebre de propósito a saída estruturada (troque `severidade` por um valor
   inválido, remova uma chave, envolva em texto) e confirme que
   `validate_structured_output` rejeita cada caso com a razão certa.
4. Adicione um terceiro exemplo ao few-shot e meça se a qualidade melhora — ou
   se só gasta mais tokens.
5. Escreva uma variante "role + CoT + estruturado" combinada e discuta os
   trade-offs (custo, latência, legibilidade) frente às variantes isoladas.

## Referências

- OpenAI — Prompt engineering: [https://platform.openai.com/docs/guides/prompt-engineering](https://platform.openai.com/docs/guides/prompt-engineering)
- Anthropic — Prompt engineering overview: [https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
- Anthropic — Prompting best practices: [https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-prompting-best-practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- Brown et al. (2020), *Language Models are Few-Shot Learners*, arXiv:2005.14165: [https://arxiv.org/abs/2005.14165](https://arxiv.org/abs/2005.14165)
- Wei et al. (2022), *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*, arXiv:2201.11903: [https://arxiv.org/abs/2201.11903](https://arxiv.org/abs/2201.11903)
