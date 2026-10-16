# 07 — Spec-Driven Development (SDD)

> Pré-requisitos: a parte central (a spec, a compilação do system prompt e o
> validador) roda **sem LLM** e sempre aparece na saída. O contraste ao vivo
> *sem-spec* vs. *com-spec* precisa de um LLM no ar (Ollama local por padrão —
> veja [../LLM_SETUP.md](../LLM_SETUP.md)); sem ele, o script degrada com
> mensagem clara. Python 3.11.

Como usar uma **spec** — um artefato prévio e estruturado — para guiar e validar o
que um agente produz, em vez de um prompt solto digitado na hora. A demo aplica
isso a um CVE: compila a spec num system prompt, gera a análise com e sem spec, e
valida a saída contra o mesmo contrato.

## Por que importa

Um prompt solto ("analise esse CVE") delega ao modelo *o que* significa "analisar":
cada execução pode devolver um formato diferente, faltar um campo ou responder em
prosa que nenhum pipeline consome. Não há nada contra o que validar, então não dá
para saber programaticamente se a saída "está certa".

Com uma spec:

1. **O contrato é explícito e único.** Os campos obrigatórios (`id`, `severidade`,
   `vetor_ataque`, `mitigacao`, `risco_negocio`), o formato (JSON) e as restrições
   são declarados uma vez.
2. **A spec vira o prompt.** `to_system_prompt()` compila a spec no system prompt —
   o agente é guiado pelo artefato, não por texto improvisado.
3. **A spec valida a saída.** `validate_against_spec()` checa o mesmo contrato:
   o JSON parseia? Todos os campos presentes e não-vazios? `severidade` está no
   enum?
4. **Saída inválida é detectável e tratável.** Um pipeline real rejeitaria e faria
   retry/repair — impossível com prosa solta.

É isso que torna um agente confiável em produção: saída estruturada, verificável e
repetível, em vez de "deu certo na vez em que eu testei".

## Conceitos

### Spec como artefato vs. spec como processo

Há duas coisas chamadas de "spec", e vale separá-las:

- **Spec como artefato** — um documento/objeto que descreve *o que* deve ser
  produzido (campos obrigatórios, formato, restrições, critério de aceite). É
  versionável, revisável e vive fora da conversa. Aqui ela aparece em duas formas
  que concordam entre si:
  - `spec_example.md` — a versão legível por humanos;
  - `CVEAnalysisSpec` em `spec_driven_analysis.py` — a mesma spec como objeto
    Pydantic, que o código compila em prompt **e** usa para validar.
- **Spec como processo** — o *fluxo* de escrever a spec primeiro, derivar o
  comportamento dela e checar o resultado contra ela. É a disciplina, não o
  arquivo.

A sacada do SDD é juntar os dois: o artefato é a fonte única de verdade e o
processo garante que o agente e a validação sempre apontem para o mesmo contrato.

### SDD não é waterfall

Escrever a spec **antes** lembra waterfall, mas a diferença é o ciclo:

- **Waterfall** — a spec é um documento grande, aprovado uma vez no início; a
  implementação tenta segui-lo até o fim. Feedback lento e caro; a spec tende a
  virar documentação morta que diverge do código.
- **SDD** — a spec é pequena, executável e **viva**: gera o comportamento e valida
  o resultado no mesmo passo, então um desvio aparece na hora. Iterar = ajustar a
  spec e re-rodar; spec e código não divergem porque a spec *é* parte do loop de
  execução. É iterativo como ágil, mas com um contrato explícito em vez de intenção
  implícita no prompt.

## Arquivos

- `spec_driven_analysis.py` — define a spec como objeto estruturado
  (`CVEAnalysisSpec`), compila-a em system prompt (`to_system_prompt()`), roda a
  análise com e sem spec sobre um CVE de `get_cve_by_id("CVE-2024-1234")`, e valida
  a saída contra a spec (`validate_against_spec()`).
- `spec_example.md` — a mesma spec escrita como artefato legível em markdown
  (tarefa, entrada, saída obrigatória, restrições, critério de aceite).

## Como rodar

A partir da raiz do repositório, com o pacote no path:

```powershell
# Windows (PowerShell)
$env:PYTHONPATH = "."
python -m 07_sdd.spec_driven_analysis
```

```bash
# Linux/macOS (Bash)
PYTHONPATH="." python -m 07_sdd.spec_driven_analysis
```

Leia também [spec_example.md](spec_example.md). Setup de provedor de LLM:
[../LLM_SETUP.md](../LLM_SETUP.md).

## O que a demo mostra

Sem Ollama, a parte determinística roda inteira (exit 0): imprime a spec como
objeto, o system prompt compilado a partir dela, e então degrada com uma mensagem
clara na etapa de geração ao vivo. Trecho real de
`outputs\07_sdd.spec_driven_analysis.txt`:

```
SPEC-DRIVEN ANALYSIS
Target CVE: CVE-2024-1234 (CRITICAL, score 9.8)

--- THE SPEC (structured artifact) ---
{
  "task": "analyze_cve",
  "required_fields": [ "id", "severidade", "vetor_ataque", "mitigacao", "risco_negocio" ],
  "output_format": "json",
  "constraints": [ ... ]
}

--- COMPILED SYSTEM PROMPT (spec -> prompt) ---
You are a security analyst. Analyze the given CVE and return a result that
strictly follows this specification.
TASK: analyze_cve
OUTPUT FORMAT: JSON
REQUIRED OUTPUT FIELDS (all mandatory):
  - id
  - severidade
  - vetor_ataque
  - mitigacao
  - risco_negocio
...

WITHOUT SPEC (loose prompt — free-form, unvalidatable)
LLM NOT AVAILABLE
Could not reach the LLM backend: Connection error.
Start Ollama (e.g. `ollama serve` and pull the configured model), then re-run:
    python -m 07_sdd.spec_driven_analysis
The spec, prompt compilation, and validator above do not need the LLM and ran
fine — only the live generation step requires Ollama.
```

Com o Ollama no ar, a demo imprime a análise *sem spec* (prosa livre, sem nada a
validar) e a análise *com spec* (JSON), seguida do relatório de validação (JSON
válido? campos ausentes? campos vazios? `severidade` no enum? saída aceita?).

## Exercícios

1. **Quebre o contrato.** Em `validate_against_spec(...)`, passe à mão uma string
   como `'{"id": "CVE-2024-1234", "severidade": "SEVERA"}'`. Confirme que o
   `ValidationReport` acusa `missing_fields` e `severity_ok=False` — isto roda sem
   Ollama.
2. **Adicione um campo obrigatório.** Inclua `"cwe"` em `required_fields` da
   `CVEAnalysisSpec` e observe o system prompt compilado mudar (`to_system_prompt()`)
   e a validação passar a exigir o novo campo. Note que a *ordem* de
   `required_fields` é parte do contrato.
3. **Teste o removedor de cercas.** Chame `_strip_fences("```json\\n{...}\\n```")`
   e verifique que ele devolve só o objeto. Por que um pipeline real ainda precisa
   disso mesmo tendo pedido "só JSON" no prompt?
4. **Spec para outra tarefa.** Escreva um `spec_example.md` novo (e o
   `CVEAnalysisSpec` equivalente) para "resumir um CVE para um gestor" — defina
   campos, formato e critério de aceite próprios, sem tocar no validador genérico.
5. **Compare com um fluxo real de SDD.** Leia a doc do Kiro Specs (ver Referências)
   e mapeie os três arquivos dela (`requirements.md`, `design.md`, `tasks.md`) para
   as partes da nossa spec mínima: o que o `spec_example.md` cobre e o que fica de
   fora.

## Referências

- [Kiro — Specs](https://kiro.dev/docs/specs/) — specs são "structured artifacts" com o workflow de três fases (Requirements/Bug Analysis → Design → Tasks) e os arquivos `requirements.md`, `design.md` e `tasks.md`.
- [GitHub Spec Kit](https://github.com/github/spec-kit) — toolkit open-source (descrito pelo próprio repositório como "Toolkit to help you get started with SDD or any other process!").
- [Pydantic](https://docs.pydantic.dev/) — a `CVEAnalysisSpec` é um modelo Pydantic.
