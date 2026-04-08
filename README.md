# Coletor de Reviews (Streamlit)

Aplicação Streamlit para **processar e filtrar** reviews do Google Maps no deploy do Streamlit Cloud, **sem uso de serviços pagos**.

## Como funciona

1. Você informa a URL do local no Google Maps (para validação/referência).
2. Você define o período em `Últimos X dias` (inteiro positivo, padrão `2000`, mínimo `1`).
3. Você envia um arquivo `.json` ou `.csv` com os reviews.
4. O app normaliza as colunas e filtra pelo período (`utc_now - timedelta(days=X)`) usando `publishedAtDate` (ou equivalente), exibindo total coletado e total após filtro.

## Pré-requisitos

- Python 3.10+
- `pip`

## Instalação

```bash
pip install -r requirements.txt
```

## Streamlit Cloud (deploy)

- Configure o app com `app.py` como arquivo principal.
- Não há necessidade de token de serviço pago.

## Formato esperado do arquivo

Campos recomendados (aceita aliases comuns):
- `title`
- `name`
- `text`
- `publishedAtDate` (obrigatório para entrar no filtro de período)
- `stars`
- `likesCount`
- `reviewUrl`
- `responseFromOwnerText`

## Exemplo de URL válida

- `https://www.google.com/maps/place/Nome+do+Local/@-23.5505,-46.6333,17z`
- `https://maps.app.goo.gl/abc123xyz`

## Estrutura

- `app.py`: interface Streamlit para upload/processamento.
- `src/reviews_service.py`: valida URL, leitura JSON/CSV, normalização e filtro por data absoluta.
- `requirements.txt`: dependências do projeto.
- `README.md`: instruções de uso.
