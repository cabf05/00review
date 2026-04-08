import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from apify_client import ApifyClient
from dateutil import parser

DEFAULT_ACTOR_ID = os.getenv("APIFY_REVIEWS_ACTOR_ID", "compass/google-maps-reviews-scraper")
DEFAULT_TIMEOUT_SECS = int(os.getenv("APIFY_TIMEOUT_SECS", "180"))
DEFAULT_MAX_RETRIES = int(os.getenv("APIFY_MAX_RETRIES", "4"))
DEFAULT_BACKOFF_BASE_SECS = float(os.getenv("APIFY_BACKOFF_BASE_SECS", "1.5"))

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
    """Erro amigável para o app ao coletar reviews."""


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


def _normalize_review(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": item.get("title") or item.get("placeName") or "",
        "name": item.get("name") or item.get("reviewerName") or "",
        "text": item.get("text") or item.get("reviewText") or "",
        "publishedAtDate": item.get("publishedAtDate") or item.get("publishedAt") or "",
        "stars": item.get("stars") if item.get("stars") is not None else item.get("rating"),
        "likesCount": item.get("likesCount") if item.get("likesCount") is not None else item.get("likes"),
        "reviewUrl": item.get("reviewUrl") or item.get("reviewLink") or "",
        "responseFromOwnerText": item.get("responseFromOwnerText") or item.get("ownerResponse") or "",
    }


def _call_actor_with_retry(
    client: ApifyClient,
    actor_id: str,
    run_input: dict[str, Any],
    timeout_secs: int,
    max_retries: int,
    backoff_base_secs: float,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            run = client.actor(actor_id).call(
                run_input=run_input,
                timeout_secs=timeout_secs,
            )
            if not run:
                raise ReviewsServiceError("O provedor retornou uma execução vazia.")
            return run
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_retries:
                break
            sleep_secs = backoff_base_secs * (2 ** (attempt - 1))
            time.sleep(sleep_secs)

    raise ReviewsServiceError(
        "Não foi possível coletar reviews no momento. "
        "Tente novamente em instantes e valide suas credenciais/configurações."
    ) from last_error


def fetch_reviews_from_maps_url(maps_url: str, days: int) -> list[dict[str, Any]]:
    """Coleta reviews de uma URL do Google Maps e filtra por janela de dias."""
    if not maps_url or not maps_url.strip():
        raise ReviewsServiceError("Informe uma URL do Google Maps.")

    if not _is_valid_google_maps_url(maps_url):
        raise ReviewsServiceError(
            "URL inválida. Use um link do Google Maps (ex.: maps.app.goo.gl ou google.com/maps)."
        )

    if days < 1:
        raise ReviewsServiceError("O número de dias deve ser maior ou igual a 1.")

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise ReviewsServiceError("APIFY_TOKEN não configurado no ambiente.")

    actor_id = DEFAULT_ACTOR_ID
    client = ApifyClient(token)

    run_input = {
        "startUrls": [{"url": maps_url.strip()}],
        "maxReviews": 0,
        "reviewsSort": "newest",
        "language": "pt-BR",
    }

    run = _call_actor_with_retry(
        client=client,
        actor_id=actor_id,
        run_input=run_input,
        timeout_secs=DEFAULT_TIMEOUT_SECS,
        max_retries=DEFAULT_MAX_RETRIES,
        backoff_base_secs=DEFAULT_BACKOFF_BASE_SECS,
    )

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise ReviewsServiceError("A coleta terminou sem dataset de saída.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = client.dataset(dataset_id).list_items(clean=True).items

    normalized: list[dict[str, Any]] = []
    for item in items:
        published_dt = _parse_absolute_date(item.get("publishedAtDate"))
        if not published_dt:
            continue
        if published_dt < cutoff:
            continue

        mapped = _normalize_review(item)
        mapped["publishedAtDate"] = published_dt.date().isoformat()
        normalized.append({key: mapped.get(key) for key in _STABLE_COLUMNS})

    return normalized
