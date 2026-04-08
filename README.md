# Coletor de Reviews (Streamlit)

Aplicação Streamlit com layout inicial para coleta de reviews a partir de uma URL do Google Maps.

## Pré-requisitos

- Python 3.10+
- `pip`

## Instalação

```bash
pip install -r requirements.txt
```

## Executar localmente

```bash
streamlit run app.py
```

Depois, acesse a URL local exibida no terminal (normalmente `http://localhost:8501`).

## Variáveis de ambiente

A aplicação espera o token do provedor de scraping gerenciado via variável de ambiente:

- `APIFY_TOKEN`: token de acesso da sua conta Apify.

Exemplo (Linux/macOS):

```bash
export APIFY_TOKEN="seu_token_aqui"
streamlit run app.py
```

Exemplo (Windows PowerShell):

```powershell
$env:APIFY_TOKEN="seu_token_aqui"
streamlit run app.py
```

## Deploy no Streamlit Cloud

1. Suba este projeto para um repositório GitHub.
2. Acesse [streamlit.io/cloud](https://streamlit.io/cloud) e conecte sua conta GitHub.
3. Clique em **New app** e selecione o repositório/branch.
4. Defina o arquivo principal como `app.py`.
5. Em **Advanced settings > Secrets**, adicione:

```toml
APIFY_TOKEN = "seu_token_aqui"
```

6. Clique em **Deploy**.

## Estrutura

- `app.py`: entrada principal do Streamlit.
- `requirements.txt`: dependências do projeto.
- `.streamlit/config.toml`: tema/configuração do app.
- `README.md`: instruções de uso e deploy.
