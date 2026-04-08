import pandas as pd
import streamlit as st
from datetime import datetime

from src.reviews_service import (
    ReviewsAuthError,
    ReviewsInvalidUrlError,
    ReviewsNetworkError,
    ReviewsServiceError,
    process_and_filter_reviews,
    validate_days_or_raise,
    validate_url_or_raise,
)

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
        value=2000,
        step=1,
        format="%d",
        help="Filtre reviews publicados nos últimos X dias.",
    )

st.markdown("### Exemplo de URL")
st.code("https://www.google.com/maps/place/Nome+do+Local/@-23.5505,-46.6333,17z")

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
if "processed_reviews" not in st.session_state:
    st.session_state.processed_reviews = False
if "total_collected" not in st.session_state:
    st.session_state.total_collected = 0
if "total_filtered" not in st.session_state:
    st.session_state.total_filtered = 0

if coletar:
    try:
        validate_url_or_raise(maps_url)
        validate_days_or_raise(int(ultimos_dias))

        if reviews_file is None:
            raise ReviewsServiceError("Envie um arquivo JSON/CSV para processar os reviews.")

        with st.spinner("Coletando reviews..."):
            reviews, total_collected = process_and_filter_reviews(
                maps_url=maps_url,
                days=int(ultimos_dias),
                file_bytes=reviews_file.getvalue(),
                file_name=reviews_file.name,
            )

        st.session_state.reviews_df = pd.DataFrame(reviews)
        st.session_state.processed_reviews = True
        st.session_state.total_collected = total_collected
        st.session_state.total_filtered = len(reviews)

        if st.session_state.reviews_df.empty:
            st.info("Nenhum review encontrado dentro do período informado.")
        else:
            st.success(f"Processamento concluído com {len(st.session_state.reviews_df)} review(s).")
    except ReviewsInvalidUrlError as exc:
        st.error(f"Erro de URL inválida: {exc}")
    except ReviewsAuthError as exc:
        st.error(f"Erro de autenticação: {exc}")
    except ReviewsNetworkError as exc:
        st.error(f"Erro de timeout/rede: {exc}")
    except ReviewsServiceError as exc:
        st.error(str(exc))
    except Exception:
        st.error("Falha inesperada ao processar o arquivo de reviews.")

df = st.session_state.reviews_df
has_reviews = not df.empty
timestamp = datetime.now().strftime("%Y%m%d_%H%M")

if has_reviews:
    st.dataframe(df, use_container_width=True)
elif st.session_state.processed_reviews:
    st.warning("Nenhum review disponível no período selecionado. Os downloads estão desabilitados.")
else:
    st.info("Os reviews aparecerão aqui após clicar em **Processar reviews**.")

if st.session_state.processed_reviews:
    c1, c2 = st.columns(2)
    c1.metric("Total coletado", st.session_state.total_collected)
    c2.metric("Total após filtro", st.session_state.total_filtered)

csv_data = df.to_csv(index=False).encode("utf-8") if has_reviews else b""
json_data = df.to_json(orient="records", force_ascii=False, indent=2) if has_reviews else "[]"

dcol1, dcol2 = st.columns(2)
with dcol1:
    st.download_button(
        "Baixar CSV",
        data=csv_data,
        file_name=f"reviews_{timestamp}.csv",
        mime="text/csv",
        disabled=not has_reviews,
    )
with dcol2:
    st.download_button(
        "Baixar JSON",
        data=json_data,
        file_name=f"reviews_{timestamp}.json",
        mime="application/json",
        disabled=not has_reviews,
    )
