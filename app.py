import pandas as pd
import streamlit as st
from datetime import datetime

from src.maps_scraper import MapsScraperError, scrape_reviews
from src.reviews_service import (
    ReviewsAuthError,
    ReviewsInvalidUrlError,
    ReviewsNetworkError,
    ReviewsServiceError,
    normalize_and_filter_items,
    process_and_filter_reviews_with_counts,
    validate_days_or_raise,
    validate_url_or_raise,
)

st.set_page_config(page_title="Coletor de Reviews", page_icon="⭐", layout="wide")

st.title("Coletor de Reviews do Google Maps")
st.caption("Deploy no Streamlit Cloud sem integração com serviços pagos.")
modo_coleta = st.radio(
    "Modo de coleta",
    options=[
        "Coletar automaticamente por URL",
        "Upload de JSON/CSV",
    ],
    index=0,
    horizontal=True,
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

reviews_file = None
if modo_coleta == "Upload de JSON/CSV":
    st.info(
        "Modo de contingência: envie um arquivo JSON/CSV com reviews contendo data absoluta "
        "(ex.: publishedAtDate)."
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
if "processed_reviews" not in st.session_state:
    st.session_state.processed_reviews = False
if "total_collected" not in st.session_state:
    st.session_state.total_collected = 0
if "total_deduped" not in st.session_state:
    st.session_state.total_deduped = 0
if "total_filtered" not in st.session_state:
    st.session_state.total_filtered = 0

if coletar:
    try:
        if modo_coleta == "Coletar automaticamente por URL":
            validate_url_or_raise(maps_url)
            validate_days_or_raise(int(ultimos_dias))

            with st.spinner("Coletando reviews automaticamente..."):
                progress = st.progress(0, text="Validando parâmetros...")
                progress.progress(10, text="Iniciando scraper de avaliações...")
                raw_reviews = scrape_reviews(maps_url=maps_url, days=int(ultimos_dias))
                progress.progress(70, text="Normalizando e deduplicando avaliações...")
                reviews, total_collected, total_deduped = normalize_and_filter_items(
                    items=raw_reviews,
                    maps_url=maps_url,
                    days=int(ultimos_dias),
                )
                progress.progress(100, text="Finalizado.")
                progress.empty()
        else:
            validate_url_or_raise(maps_url)
            validate_days_or_raise(int(ultimos_dias))

            if reviews_file is None:
                raise ReviewsServiceError("Envie um arquivo JSON/CSV para processar os reviews.")

            with st.spinner("Processando reviews de arquivo..."):
                reviews, total_collected, total_deduped = process_and_filter_reviews_with_counts(
                    maps_url=maps_url,
                    days=int(ultimos_dias),
                    file_bytes=reviews_file.getvalue(),
                    file_name=reviews_file.name,
                )

        st.session_state.reviews_df = pd.DataFrame(reviews)
        st.session_state.processed_reviews = True
        st.session_state.total_collected = total_collected
        st.session_state.total_deduped = total_deduped
        st.session_state.total_filtered = len(reviews)

        if st.session_state.reviews_df.empty:
            st.info("Nenhum review encontrado dentro do período informado.")
        else:
            st.success(f"Processamento concluído com {len(st.session_state.reviews_df)} review(s).")
    except ReviewsInvalidUrlError as exc:
        st.error(f"URL inválida: {exc}")
    except ReviewsAuthError as exc:
        st.error(f"Bloqueio temporário de autenticação/credenciais: {exc}")
    except ReviewsNetworkError as exc:
        st.error(f"Timeout ou falha de rede durante a coleta: {exc}")
    except MapsScraperError as exc:
        scraper_error_map = {
            "BLOCKED_TEMPORARY": (
                "O Google Maps bloqueou temporariamente a coleta automática.",
                "Aguarde alguns minutos e tente novamente; se persistir, use Upload de JSON/CSV.",
            ),
            "DOM_CHANGED": (
                "A estrutura da página do Google Maps mudou.",
                "Tente novamente mais tarde; enquanto isso, use Upload de JSON/CSV.",
            ),
            "TIMEOUT": (
                "A coleta excedeu o tempo limite.",
                "Tente novamente com menos dias ou use Upload de JSON/CSV.",
            ),
            "NO_REVIEWS": (
                "Não encontramos avaliações no período informado.",
                "Aumente o intervalo de dias ou valide se o local possui reviews recentes.",
            ),
        }
        code = getattr(exc, "code", "BLOCKED_TEMPORARY")
        friendly_message, suggested_action = scraper_error_map.get(
            code,
            (
                "Falha temporária durante a coleta automática.",
                "Tente novamente em instantes ou use Upload de JSON/CSV.",
            ),
        )
        st.error(f"{friendly_message} ({code})")
        if code == "BLOCKED_TEMPORARY":
            st.caption(f"Detalhe técnico: {exc}")
        st.info(f"Ação sugerida: {suggested_action}")
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
    c1, c2, c3 = st.columns(3)
    c1.metric("Total coletado", st.session_state.total_collected)
    c2.metric("Total deduplicado", st.session_state.total_deduped)
    c3.metric("Total após filtro", st.session_state.total_filtered)

csv_data = df.to_csv(index=False).encode("utf-8") if has_reviews else b""
json_data = df.to_json(orient="records", force_ascii=False, indent=2) if has_reviews else "[]"
download_prefix = f"reviews_google_maps_{timestamp}"

dcol1, dcol2 = st.columns(2)
with dcol1:
    st.download_button(
        "Baixar CSV",
        data=csv_data,
        file_name=f"{download_prefix}.csv",
        mime="text/csv",
        disabled=not has_reviews,
    )
with dcol2:
    st.download_button(
        "Baixar JSON",
        data=json_data,
        file_name=f"{download_prefix}.json",
        mime="application/json",
        disabled=not has_reviews,
    )
