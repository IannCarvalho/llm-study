# Contribuindo

Obrigado pelo interesse neste repositório de estudos. É um projeto educacional:
os exemplos devem ficar pequenos, legíveis e executáveis localmente.

## Setup

```bash
# 1. Clone e entre no repositório
git clone https://github.com/IannCarvalho/llm-study.git
cd llm-study

# 2. Crie um ambiente virtual (Python 3.11)
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Copie o modelo do .env e preencha o que precisar
cp .env.example .env
```

Para os exemplos com LLM, rode um modelo local com [Ollama](https://ollama.com):
`ollama serve` e depois `ollama pull mistral`. Nenhuma chave de nuvem é
necessária para uso local; as opções de LM Studio e OpenAI estão em
[LLM_SETUP.md](LLM_SETUP.md).

## Rodando os exemplos

Todo módulo roda como pacote a partir da raiz:

```bash
python -m 01_vector_databases.hybrid_search
python -m 12_agentic_rag.agentic_rag
```

Muitos exemplos têm um **caminho determinístico que roda sem Ollama** (busca,
reranking, guardrails, métricas, janelas de memória, cache). É isso que a suíte
de testes e o CI exercitam.

## Testes e lint

```bash
# Suíte determinística (sem LLM, sem rede, sem download de modelo)
python -m pytest tests -q

# Lint
ruff check .
```

O CI roda os dois em todo push e pull request (veja
`.github/workflows/ci.yml`). Mantenha a suíte verde e acrescente testes para
todo comportamento determinístico novo.

`tests/test_docs.py` também verifica a documentação: links relativos para
arquivos que existem, comandos `python -m NN_modulo.script` que apontam para
scripts reais e trechos `from utils.X import Y` com nomes que existem.

## Idioma

- **Documentação** (README, `.md`): **PT-BR**.
- **Código** (nomes, docstrings, comentários, mensagens de log): **inglês**.

## Organização

- Cada tema é um diretório `NN_tema/` com `__init__.py` vazio, `README.md` e os
  scripts.
- Os números são **identificadores estáveis**: nunca renumere um módulo
  existente. Um tema novo pega o próximo número livre; a **ordem de estudo** é
  a do roteiro no README raiz, não a dos números.
- Nomes que começam com dígito não são importáveis com `import`; use
  `python -m NN_tema.script`, `importlib.import_module("NN_tema.script")` ou,
  nos testes, `conftest.load_module(...)`.

## Convenções de código

- Cada script tem uma docstring de módulo explicando o conceito, uma
  `def main() -> None:` e `if __name__ == "__main__": main()`. **Nada roda no
  import.**
- Caminho determinístico primeiro: a parte central deve rodar sem Ollama, sem
  rede e sem chave. O LLM é opcional: importe `utils.llm_client` dentro da
  função que o usa, com um `try/except` que degrada com uma mensagem clara.
- Configuração só pelo `utils.config` (`get_config()`); ele também carrega o
  `.env` para as bibliotecas de terceiros. Não chame `load_dotenv()` nem leia
  `os.environ` para as variáveis do projeto.
- Prefira os helpers de `utils/` (busca, carregamento de dados, tokenização) a
  duplicar lógica.
- `print()` serve para a narração didática da demo; `utils.logging.get_logger`
  serve para diagnóstico.
- Um README ou comentário só pode citar arquivos que existem.

## Template de README de módulo

```markdown
# NN — Tema
> Pré-requisitos: roda sem LLM? precisa de Ollama / chave / pacote extra?

Intro curta (2–4 linhas).

## Por que importa
## Conceitos
## Arquivos
## Como rodar            (comandos `python -m ...` a partir da raiz)
## O que a demo mostra   (trecho da saída real da execução)
## Exercícios
## Referências           (só fontes verificadas, com URL)
```

## Licença

Ao contribuir, você concorda que suas contribuições são licenciadas sob a
[MIT License](LICENSE).
