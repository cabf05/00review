import os
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from dateutil import parser

st.set_page_config(page_title="Coletor de Reviews", page_icon="⭐", layout="wide")

st.title("Coletor de Reviews do Google Maps")
st.caption("Layout inicial para coleta de reviews com Streamlit")

with st.sidebar:
    st.header("Configuração")
    token_configurado = bool(os.getenv("APIFY_TOKEN"))
    st.write("APIFY_TOKEN configurado:", "✅" if token_configurado else "❌")

col1, col2 = st.columns([3, 1])

with col1:
    maps_url = st.text_input(
        "URL do Google Maps",
        placeholder="https://www.google.com/maps/place/...",
        help="Cole aqui a URL do local no Google Maps.",
    )

with col2:
    ultimos_dias = st.number_input(
        "Últimos X dias",
        min_value=1,
        value=2000,
        step=1,
        help="Filtre reviews publicados nos últimos X dias.",
    )

coletar = st.button("Coletar reviews", type="primary")

st.divider()
st.subheader("Resultados")

if "reviews_df" not in st.session_state:
    st.session_state.reviews_df = pd.DataFrame()

if coletar:
    if not maps_url:
        st.warning("Informe uma URL do Google Maps para continuar.")
    else:
        # Placeholder de dados para layout inicial.
        agora = datetime.utcnow()
        dados_exemplo = [
            {
                "autor": "Usuário Exemplo 1",
                "nota": 5,
                "comentario": "Excelente atendimento!",
                "data": (agora - timedelta(days=2)).date().isoformat(),
                "source_url": maps_url,
            },
            {
                "autor": "Usuário Exemplo 2",
                "nota": 4,
                "comentario": "Boa experiência geral.",
                "data": (agora - timedelta(days=10)).date().isoformat(),
                "source_url": maps_url,
            },
            {
                "autor": "Usuário Exemplo 3",
                "nota": 3,
                "comentario": "Poderia melhorar.",
                "data": (agora - timedelta(days=40)).date().isoformat(),
                "source_url": maps_url,
            },
        ]

        limite = datetime.utcnow() - timedelta(days=int(ultimos_dias))
        filtrado = []
        for item in dados_exemplo:
            data_review = parser.parse(item["data"])
            if data_review >= limite:
                filtrado.append(item)

        st.session_state.reviews_df = pd.DataFrame(filtrado)
        st.success("Coleta concluída (dados de exemplo para o layout inicial).")

if not st.session_state.reviews_df.empty:
    st.dataframe(st.session_state.reviews_df, use_container_width=True)

    csv_data = st.session_state.reviews_df.to_csv(index=False).encode("utf-8")
    json_data = st.session_state.reviews_df.to_json(orient="records", force_ascii=False, indent=2)

    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name="reviews.csv",
            mime="text/csv",
        )
    with dcol2:
        st.download_button(
            "Download JSON",
            data=json_data,
            file_name="reviews.json",
            mime="application/json",
        )
else:
    st.info("Os reviews aparecerão aqui após clicar em **Coletar reviews**.")
