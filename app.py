import pandas as pd
import streamlit as st

from src.reviews_service import ReviewsServiceError, filter_and_normalize_reviews

st.set_page_config(page_title="Coletor de Reviews", page_icon="⭐", layout="wide")

st.title("Coletor de Reviews do Google Maps")
st.caption("Deploy no Streamlit Cloud sem integração com serviços pagos.")

st.info(
    "Para manter o app sem serviços pagos, a coleta automática por URL não é executada. "
    "Envie um JSON/CSV com reviews contendo campo de data absoluta (ex.: publishedAtDate)."
)

col1, col2 = st.columns([3, 1])

with col1:
    maps_url = st.text_input(
        "URL do Google Maps",
        placeholder="https://www.google.com/maps/place/...",
        help="Usada para validação e referência no resultado.",
    )

with col2:
    ultimos_dias = st.number_input(
        "Últimos X dias",
        min_value=1,
        value=90,
        step=1,
        help="Filtre reviews publicados nos últimos X dias.",
    )

reviews_file = st.file_uploader(
    "Arquivo de reviews (.json ou .csv)",
    type=["json", "csv"],
    help="O arquivo deve conter uma lista de reviews com campo absoluto de data.",
)

coletar = st.button("Processar reviews", type="primary")

st.divider()
st.subheader("Resultados")

if "reviews_df" not in st.session_state:
    st.session_state.reviews_df = pd.DataFrame()

if coletar:
    try:
        if reviews_file is None:
            raise ReviewsServiceError("Envie um arquivo JSON/CSV para processar os reviews.")

        reviews = filter_and_normalize_reviews(
            maps_url=maps_url,
            days=int(ultimos_dias),
            file_bytes=reviews_file.getvalue(),
            file_name=reviews_file.name,
        )
        st.session_state.reviews_df = pd.DataFrame(reviews)

        if st.session_state.reviews_df.empty:
            st.info("Nenhum review encontrado dentro do período informado.")
        else:
            st.success(f"Processamento concluído com {len(st.session_state.reviews_df)} review(s).")
    except ReviewsServiceError as exc:
        st.error(str(exc))
    except Exception:
        st.error("Falha inesperada ao processar o arquivo de reviews.")

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
    st.info("Os reviews aparecerão aqui após clicar em **Processar reviews**.")
