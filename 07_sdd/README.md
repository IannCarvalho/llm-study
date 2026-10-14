# 07 — Spec-Driven Development (SDD) para agentes

Como usar uma **spec** — um artefato prévio e estruturado — para guiar o que um
agente faz, em vez de um prompt solto digitado na hora.

## Spec como artefato vs. spec como processo

Há duas coisas diferentes chamadas de "spec", e vale separar:

- **Spec como artefato**: um documento/objeto que descreve *o que* deve ser
  produzido — campos obrigatórios, formato, restrições, critério de aceite. É
  versionável, revisável, e vive fora da conversa. Aqui ela aparece em duas
  formas que concordam entre si:
  - `spec_example.md` — a versão legível por humanos (o que o Kiro usaria como
    steering/spec de feature);
  - `CVEAnalysisSpec` em `spec_driven_analysis.py` — a mesma spec como objeto
    Pydantic, que o código consegue compilar em prompt **e** usar para validar.
- **Spec como processo**: o *fluxo de trabalho* de escrever a spec primeiro,
  derivar o comportamento dela, e checar o resultado contra ela — em vez de ir
  direto pro código/prompt. É a disciplina, não o arquivo.

A sacada do SDD é juntar os dois: o artefato é a fonte única de verdade e o
processo garante que o agente e a validação sempre apontem pro mesmo contrato.

## Por que SDD importa no desenvolvimento com agentes hoje

Um prompt solto ("analise esse CVE") delega ao modelo *o que* significa "analisar":
cada execução pode devolver um formato diferente, faltar um campo, ou responder em
prosa que nenhum pipeline consegue consumir. Não há nada contra o que validar, então
não dá pra saber programaticamente se a saída "está certa".

Com uma spec:

1. **O contrato é explícito e único.** Os campos obrigatórios
   (`id`, `severidade`, `vetor_ataque`, `mitigacao`, `risco_negocio`), o formato
   (JSON) e as restrições são declarados uma vez.
2. **A spec vira o prompt.** `to_system_prompt()` compila a spec no system prompt —
   o agente é guiado pelo artefato, não por texto improvisado.
3. **A spec valida a saída.** `validate_against_spec()` checa o mesmo contrato:
   JSON parseia? Todos os campos presentes e não-vazios? `severidade` dentro do enum?
4. **Saída inválida é detectável e tratável.** Um pipeline real rejeitaria e faria
   retry/repair — algo impossível com prosa solta.

Isso é exatamente o que torna agentes confiáveis em produção: saída estruturada,
verificável e repetível, em vez de "deu certo na vez que eu testei".

## Processo vs. waterfall

SDD escreve a spec **antes**, o que lembra waterfall — mas a diferença é o ciclo:

- **Waterfall**: a spec é um documento grande, aprovado uma vez no início, e a
  implementação tenta segui-lo até o fim. Feedback é lento e caro; a spec tende a
  virar documentação morta que diverge do código.
- **SDD**: a spec é pequena, executável e **viva**. Ela gera o comportamento e
  valida o resultado no mesmo passo, então um desvio aparece na hora. Iterar =
  ajustar a spec e re-rodar; a spec e o código não divergem porque a spec *é* parte
  do loop de execução. É iterativo como ágil, mas com um contrato explícito em vez
  de intenção implícita no prompt.

Em resumo: waterfall congela a spec e espera; SDD mantém a spec como fonte de verdade
executável que guia e checa cada iteração.

## Como rodar

Da raiz do repositório, com o pacote no path:

```bash
# Linux/macOS
PYTHONPATH="." python -m 07_sdd.spec_driven_analysis
```

```powershell
# Windows PowerShell
$env:PYTHONPATH="."; python -m 07_sdd.spec_driven_analysis
```

A spec, a compilação do system prompt e o validador rodam **sem** LLM e sempre
aparecem na saída. A geração ao vivo (contraste sem-spec vs. com-spec) precisa do
Ollama no ar; se ele não estiver disponível, o script falha com uma mensagem clara
explicando como subir o Ollama — não trava.

## Arquivos deste módulo

- `spec_driven_analysis.py` — define a spec como objeto estruturado, compila ela em
  system prompt, roda a análise com e sem spec sobre um CVE real de
  `get_cve_by_id(...)`, e valida a saída contra a spec.
- `spec_example.md` — a mesma spec escrita como artefato legível em markdown.
