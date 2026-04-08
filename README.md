# Coletor de Reviews (Streamlit)

Aplicação Streamlit para coleta de reviews de locais no Google Maps usando provedor gerenciado (Apify API).

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

- `APIFY_TOKEN`: token de acesso da sua conta Apify (obrigatório).
- `APIFY_REVIEWS_ACTOR_ID`: actor de reviews (opcional, default `compass/google-maps-reviews-scraper`).
- `APIFY_TIMEOUT_SECS`: timeout da execução do actor em segundos (opcional, default `180`).
- `APIFY_MAX_RETRIES`: quantidade máxima de tentativas com backoff exponencial (opcional, default `4`).
- `APIFY_BACKOFF_BASE_SECS`: base em segundos do backoff exponencial (opcional, default `1.5`).

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

## Estrutura

- `app.py`: interface Streamlit e mensagens amigáveis.
- `src/reviews_service.py`: valida URL, chama API oficial do provedor, aplica retry/backoff, normaliza e filtra por data absoluta.
- `requirements.txt`: dependências do projeto.
- `.streamlit/config.toml`: tema/configuração do app.
- `README.md`: instruções de uso e deploy.
