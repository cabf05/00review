import json
import os
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from dateutil import parser

_ALLOWED_HOSTS = {
    "maps.app.goo.gl",
    "google.com",
    "www.google.com",
    "maps.google.com",
}

_STABLE_COLUMNS = [
    "title",
    "name",
    "text",
    "publishedAtDate",
    "stars",
    "likesCount",
    "reviewUrl",
    "responseFromOwnerText",
]


class ReviewsServiceError(Exception):
    """Erro amigável para o app ao processar reviews."""


class ReviewsAuthError(ReviewsServiceError):
    """Erro de autenticação com APIFY_TOKEN."""


class ReviewsNetworkError(ReviewsServiceError):
    """Erro de timeout/rede na coleta externa."""


class ReviewsInvalidUrlError(ReviewsServiceError):
    """Erro de URL inválida."""


def _is_valid_google_maps_url(maps_url: str) -> bool:
    try:
        parsed = urlparse(maps_url.strip())
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = parsed.netloc.lower()
    if host in _ALLOWED_HOSTS:
        return True

    return host.endswith(".google.com") and "/maps" in parsed.path


def _parse_absolute_date(raw_date: Any) -> datetime | None:
    if not raw_date:
        return None

    try:
        dt = parser.isoparse(str(raw_date))
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_review(item: dict[str, Any], maps_url: str | None = None) -> dict[str, Any]:
    return {
        "title": item.get("title") or item.get("placeName") or "",
        "name": item.get("name") or item.get("reviewerName") or item.get("authorName") or "",
        "text": item.get("text") or item.get("reviewText") or item.get("comment") or "",
        "publishedAtDate": item.get("publishedAtDate") or item.get("publishedAt") or item.get("date") or "",
        "stars": item.get("stars") if item.get("stars") is not None else item.get("rating"),
        "likesCount": item.get("likesCount") if item.get("likesCount") is not None else item.get("likes"),
        "reviewUrl": item.get("reviewUrl") or item.get("reviewLink") or maps_url or "",
        "responseFromOwnerText": item.get("responseFromOwnerText") or item.get("ownerResponse") or "",
    }


def _read_reviews_payload(file_bytes: bytes, file_name: str) -> list[dict[str, Any]]:
    lower = file_name.lower()

    if lower.endswith(".json"):
        payload = json.loads(file_bytes.decode("utf-8"))
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            if isinstance(payload.get("reviews"), list):
                return [x for x in payload["reviews"] if isinstance(x, dict)]
            return [payload]
        raise ReviewsServiceError("JSON inválido: esperado objeto ou lista de objetos.")

    if lower.endswith(".csv"):
        df = pd.read_csv(StringIO(file_bytes.decode("utf-8")))
        return df.fillna("").to_dict(orient="records")

    raise ReviewsServiceError("Formato não suportado. Envie um arquivo .json ou .csv.")


def fetch_reviews_from_maps_url(maps_url: str, days: int) -> list[dict[str, Any]]:
    """
    Mantida por compatibilidade de interface.

    Sem uso de serviços pagos, a aplicação processa reviews enviados pelo usuário
    (JSON/CSV) em vez de fazer extração automática de Google Maps.
    """
    if not maps_url or not maps_url.strip():
        raise ReviewsServiceError("Informe uma URL do Google Maps.")

    if not _is_valid_google_maps_url(maps_url):
        raise ReviewsInvalidUrlError(
            "URL inválida. Use um link do Google Maps (ex.: maps.app.goo.gl ou google.com/maps)."
        )

    if days < 1:
        raise ReviewsServiceError("O número de dias deve ser maior ou igual a 1.")

    token = (os.getenv("APIFY_TOKEN") or "").strip()
    if not token:
        raise ReviewsAuthError(
            "APIFY_TOKEN ausente. Configure o token para habilitar coleta automática por URL."
        )

    if len(token) < 8:
        raise ReviewsAuthError(
            "APIFY_TOKEN inválido. Revise o token configurado e tente novamente."
        )

    raise ReviewsNetworkError(
        "Falha de timeout/rede ao tentar coletar reviews automaticamente. "
        "Tente novamente em instantes ou use upload de arquivo JSON/CSV."
    )


def process_and_filter_reviews(
    maps_url: str,
    days: int,
    file_bytes: bytes,
    file_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """Retorna os reviews filtrados e a contagem total lida do arquivo."""
    if not maps_url or not maps_url.strip():
        raise ReviewsServiceError("Informe uma URL do Google Maps.")

    if not _is_valid_google_maps_url(maps_url):
        raise ReviewsInvalidUrlError(
            "URL inválida. Use um link do Google Maps (ex.: maps.app.goo.gl ou google.com/maps)."
        )

    if days < 1:
        raise ReviewsServiceError("O número de dias deve ser maior ou igual a 1.")

    if not file_bytes:
        raise ReviewsServiceError("Envie um arquivo JSON/CSV com os reviews.")

    items = _read_reviews_payload(file_bytes=file_bytes, file_name=file_name)
    total_items = len(items)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    normalized: list[dict[str, Any]] = []
    for item in items:
        mapped = _normalize_review(item, maps_url=maps_url)
        published_dt = _parse_absolute_date(mapped.get("publishedAtDate"))
        if not published_dt:
            continue
        if published_dt < cutoff:
            continue

        mapped["publishedAtDate"] = published_dt.date().isoformat()
        normalized.append({key: mapped.get(key) for key in _STABLE_COLUMNS})

    return normalized, total_items


def validate_url_or_raise(maps_url: str) -> None:
    if not maps_url or not maps_url.strip():
        raise ReviewsServiceError("Informe uma URL do Google Maps.")

    if not _is_valid_google_maps_url(maps_url):
        raise ReviewsInvalidUrlError(
            "URL inválida. Use um link do Google Maps (ex.: maps.app.goo.gl ou google.com/maps)."
        )


def validate_days_or_raise(days: int) -> None:
    if days < 1:
        raise ReviewsServiceError("O número de dias deve ser maior ou igual a 1.")


def validate_apify_token_or_raise() -> None:
    token = (os.getenv("APIFY_TOKEN") or "").strip()
    if not token:
        raise ReviewsAuthError(
            "APIFY_TOKEN ausente. Configure o token para habilitar coleta automática por URL."
        )
    if len(token) < 8:
        raise ReviewsAuthError(
            "APIFY_TOKEN inválido. Revise o token configurado e tente novamente."
        )


def classify_network_error() -> None:
    raise ReviewsNetworkError(
        "Falha de timeout/rede ao tentar acessar o serviço externo de coleta."
    )


def filter_and_normalize_reviews(
    maps_url: str,
    days: int,
    file_bytes: bytes,
    file_name: str,
) -> list[dict[str, Any]]:
    """Normaliza e filtra reviews por `publishedAtDate >= utc_now - timedelta(days=days)`."""
    filtered, _ = process_and_filter_reviews(
        maps_url=maps_url,
        days=days,
        file_bytes=file_bytes,
        file_name=file_name,
    )
    return filtered
