import os

import pandas as pd
import streamlit as st

from src.reviews_service import ReviewsServiceError, fetch_reviews_from_maps_url

st.set_page_config(page_title="Coletor de Reviews", page_icon="⭐", layout="wide")

st.title("Coletor de Reviews do Google Maps")
st.caption("Coleta reviews com provedor gerenciado e respeitando políticas aplicáveis.")

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
        value=90,
        step=1,
        help="Filtre reviews publicados nos últimos X dias.",
    )

coletar = st.button("Coletar reviews", type="primary")

st.divider()
st.subheader("Resultados")

if "reviews_df" not in st.session_state:
    st.session_state.reviews_df = pd.DataFrame()

if coletar:
    try:
        reviews = fetch_reviews_from_maps_url(maps_url=maps_url, days=int(ultimos_dias))
        st.session_state.reviews_df = pd.DataFrame(reviews)

        if st.session_state.reviews_df.empty:
            st.info("Nenhum review encontrado dentro do período informado.")
        else:
            st.success(f"Coleta concluída com {len(st.session_state.reviews_df)} review(s).")
    except ReviewsServiceError as exc:
        st.error(str(exc))
    except Exception:
        st.error(
            "Falha inesperada ao coletar reviews. "
            "Revise a URL/token e tente novamente em alguns minutos."
        )

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
