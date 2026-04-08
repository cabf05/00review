from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import tempfile
import time
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, build_opener

from dateutil import parser


class MapsScraperError(Exception):
    """Erro amigável para falhas de scraping do Google Maps."""


@dataclass(frozen=True)
class ScraperConfig:
    total_timeout_seconds: int = 180
    step_retries: int = 3
    no_new_items_limit: int = 5
    scroll_pause_seconds: float = 1.2
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )


def scrape_reviews(maps_url: str, days: int) -> list[dict]:
    """Extrai avaliações recentes de uma página de local no Google Maps.

    Retorna uma lista normalizada de dicts com o contrato esperado por
    ``src/reviews_service.py`` (campos de review).
    """
    if not maps_url or not maps_url.strip():
        raise MapsScraperError("Informe uma URL do Google Maps.")
    if days < 1:
        raise MapsScraperError("O número de dias deve ser maior ou igual a 1.")

    config = ScraperConfig()
    started_at = time.monotonic()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        final_url = _resolve_maps_url(maps_url)
        return _scrape_with_playwright(final_url, cutoff, config, started_at)
    except MapsScraperError:
        raise
    except Exception as exc:  # pragma: no cover - erro de última camada
        raise MapsScraperError(
            "Não foi possível coletar avaliações automaticamente. "
            "O layout do Google Maps pode ter mudado; tente novamente mais tarde."
        ) from exc


def _resolve_maps_url(maps_url: str) -> str:
    request = Request(
        maps_url.strip(),
        headers={
            "User-Agent": ScraperConfig.user_agent,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    opener = build_opener()
    with opener.open(request, timeout=20) as response:
        resolved = response.geturl()

    parsed = urlparse(resolved)
    if "google" not in parsed.netloc.lower() and "goo.gl" not in parsed.netloc.lower():
        raise MapsScraperError("URL resolvida não parece ser do Google Maps.")

    return resolved


def _scrape_with_playwright(
    final_url: str,
    cutoff: datetime,
    config: ScraperConfig,
    started_at: float,
) -> list[dict]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise MapsScraperError(
            "Playwright não está disponível no ambiente. "
            "Instale 'playwright' e os browsers antes de executar o scraper."
        ) from exc

    reviews_by_id: dict[str, dict[str, Any]] = {}
    no_new_items = 0
    stop_due_to_cutoff = False

    with sync_playwright() as p:
        with tempfile.TemporaryDirectory(prefix="maps-scraper-") as user_data_dir:
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                user_agent=config.user_agent,
                locale="pt-BR",
                timezone_id="UTC",
                viewport={"width": 1366, "height": 900},
            )
            page = browser_context.new_page()
            page.set_default_timeout(15000)

            _run_step_with_retries(
                lambda: page.goto(final_url, wait_until="domcontentloaded", timeout=30000),
                "abrir URL do local",
                config,
                started_at,
                PlaywrightTimeoutError,
            )

            _open_reviews_panel(page, config, started_at, PlaywrightTimeoutError)
            _sort_by_most_recent(page, config, started_at, PlaywrightTimeoutError)
            container = _find_reviews_container(page)

            while True:
                _ensure_not_timed_out(started_at, config.total_timeout_seconds)

                current_batch = _extract_reviews_from_dom(page)
                added_count = 0
                oldest_in_batch: datetime | None = None

                for item in current_batch:
                    rid = item.get("reviewId")
                    if not rid:
                        continue
                    if rid not in reviews_by_id:
                        reviews_by_id[rid] = item
                        added_count += 1

                    published_dt = _safe_parse_datetime(item.get("publishedAtDate"))
                    if published_dt is not None:
                        oldest_in_batch = (
                            published_dt
                            if oldest_in_batch is None
                            else min(oldest_in_batch, published_dt)
                        )

                if oldest_in_batch is not None and oldest_in_batch < cutoff:
                    stop_due_to_cutoff = True

                if added_count == 0:
                    no_new_items += 1
                else:
                    no_new_items = 0

                if stop_due_to_cutoff or no_new_items >= config.no_new_items_limit:
                    break

                container.evaluate("(el) => { el.scrollBy(0, Math.floor(el.clientHeight * 0.9)); }")
                page.wait_for_timeout(int(config.scroll_pause_seconds * 1000))

            browser_context.close()

    return _finalize_reviews(reviews_by_id, cutoff)


def _open_reviews_panel(page, config: ScraperConfig, started_at: float, timeout_exc: type[Exception]) -> None:
    selectors = [
        'button[jsaction*="pane.reviewChart.moreReviews"]',
        'button:has-text("avalia")',
        'button:has-text("reviews")',
        '[role="tab"]:has-text("Avaliações")',
        '[role="tab"]:has-text("Reviews")',
    ]

    def _click_first_found() -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.click()
                return
        raise MapsScraperError(
            "Não foi possível abrir o painel de avaliações. O layout da página pode ter mudado."
        )

    _run_step_with_retries(
        _click_first_found,
        "abrir painel de avaliações",
        config,
        started_at,
        timeout_exc,
    )


def _sort_by_most_recent(page, config: ScraperConfig, started_at: float, timeout_exc: type[Exception]) -> None:
    def _sort() -> None:
        page.locator('button[aria-label*="Sort"]').first.click()
        option_candidates = [
            page.get_by_role("menuitemradio", name=re.compile("mais recentes", re.I)).first,
            page.get_by_role("menuitemradio", name=re.compile("newest", re.I)).first,
            page.locator('div[role="menu"] [role="menuitemradio"]:has-text("Mais recentes")').first,
            page.locator('div[role="menu"] [role="menuitemradio"]:has-text("Newest")').first,
        ]
        for opt in option_candidates:
            if opt.count() > 0:
                opt.click()
                return
        raise MapsScraperError(
            "Não foi possível ordenar por 'Mais recentes'. O layout da página pode ter mudado."
        )

    _run_step_with_retries(_sort, "ordenar reviews por mais recentes", config, started_at, timeout_exc)


def _find_reviews_container(page):
    candidates = [
        'div[role="main"] div[aria-label*="Reviews"]',
        'div[role="main"] div[aria-label*="Avaliações"]',
        'div[role="feed"]',
    ]
    for selector in candidates:
        loc = page.locator(selector).first
        if loc.count() > 0:
            return loc
    raise MapsScraperError(
        "Não foi possível localizar o container de avaliações. O layout da página pode ter mudado."
    )


def _extract_reviews_from_dom(page) -> list[dict[str, Any]]:
    js = """
    () => {
      const cards = Array.from(document.querySelectorAll('div.jftiEf, div[data-review-id]'));
      return cards.map((card) => {
        const reviewId = card.getAttribute('data-review-id') || card.getAttribute('jslog') || '';

        const nameEl = card.querySelector('.d4r55, .TSUbDb');
        const textEl = card.querySelector('.wiI7pd, .MyEned');
        const starEl = card.querySelector('[role="img"][aria-label*="star"], [role="img"][aria-label*="estrela"]');
        const dateEl = card.querySelector('.rsqaWe, .xRkPPb, span[class*="rsqaWe"]');
        const likesEl = card.querySelector('.GBkF3d, .pkWtMe');
        const reviewLinkEl = card.querySelector('a[href*="/maps/reviews/"]');
        const ownerRespEl = card.querySelector('.CDe7pd, .wiI7pd + div');

        const starLabel = starEl ? (starEl.getAttribute('aria-label') || '') : '';
        const starsMatch = starLabel.match(/(\d+[\.,]?\d*)/);

        return {
          reviewId,
          name: nameEl ? nameEl.textContent.trim() : '',
          text: textEl ? textEl.textContent.trim() : '',
          stars: starsMatch ? Number(starsMatch[1].replace(',', '.')) : null,
          publishedAtDate: dateEl ? dateEl.textContent.trim() : '',
          likesCount: likesEl ? Number((likesEl.textContent || '0').replace(/\D/g, '') || '0') : 0,
          reviewUrl: reviewLinkEl ? reviewLinkEl.href : '',
          responseFromOwnerText: ownerRespEl ? ownerRespEl.textContent.trim() : '',
        };
      });
    }
    """
    raw_items = page.evaluate(js)
    normalized_items: list[dict[str, Any]] = []

    for idx, item in enumerate(raw_items or []):
        review_id = _normalize_review_id(item.get("reviewId") or "", idx)
        normalized_items.append(
            {
                "reviewId": review_id,
                "title": "",
                "name": (item.get("name") or "").strip(),
                "text": (item.get("text") or "").strip(),
                "stars": item.get("stars"),
                "publishedAtDate": _normalize_date_text(item.get("publishedAtDate") or ""),
                "likesCount": item.get("likesCount") or 0,
                "reviewUrl": item.get("reviewUrl") or "",
                "responseFromOwnerText": (item.get("responseFromOwnerText") or "").strip(),
            }
        )
    return normalized_items


def _normalize_review_id(raw_review_id: str, idx: int) -> str:
    if not raw_review_id:
        return f"fallback-{idx}"

    candidate = raw_review_id
    if "review_id" in raw_review_id:
        parsed = parse_qs(urlparse(raw_review_id).query)
        candidate = parsed.get("review_id", [raw_review_id])[0]

    clean = re.sub(r"[^A-Za-z0-9_-]", "", candidate)
    return clean or f"fallback-{idx}"


def _normalize_date_text(value: str) -> str:
    value = (value or "").strip()
    parsed = _safe_parse_datetime(value)
    if parsed is None:
        return value
    return parsed.date().isoformat()


def _safe_parse_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None

    text = str(raw).strip()
    relative_match = re.match(r"^há\s+(\d+)\s+(dia|dias|semana|semanas|mês|meses|ano|anos)$", text, re.I)
    if relative_match:
        qty = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        now = datetime.now(timezone.utc)
        if unit.startswith("dia"):
            return now - timedelta(days=qty)
        if unit.startswith("semana"):
            return now - timedelta(days=qty * 7)
        if unit in {"mês", "meses"}:
            return now - timedelta(days=qty * 30)
        if unit.startswith("ano"):
            return now - timedelta(days=qty * 365)

    try:
        dt = parser.parse(text, dayfirst=True)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _finalize_reviews(reviews_by_id: dict[str, dict[str, Any]], cutoff: datetime) -> list[dict]:
    out: list[dict] = []
    for item in reviews_by_id.values():
        published_dt = _safe_parse_datetime(item.get("publishedAtDate"))
        if published_dt is None:
            continue
        if published_dt < cutoff:
            continue

        normalized = {
            "reviewId": item.get("reviewId") or "",
            "title": item.get("title") or "",
            "name": item.get("name") or "",
            "text": item.get("text") or "",
            "publishedAtDate": published_dt.date().isoformat(),
            "stars": item.get("stars"),
            "likesCount": item.get("likesCount") or 0,
            "reviewUrl": item.get("reviewUrl") or "",
            "responseFromOwnerText": item.get("responseFromOwnerText") or "",
        }
        out.append(normalized)

    out.sort(key=lambda r: r.get("publishedAtDate", ""), reverse=True)
    return out


def _run_step_with_retries(
    fn: Callable[[], Any],
    step_name: str,
    config: ScraperConfig,
    started_at: float,
    timeout_exception_type: type[Exception],
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, config.step_retries + 1):
        _ensure_not_timed_out(started_at, config.total_timeout_seconds)
        try:
            return fn()
        except (timeout_exception_type, MapsScraperError) as exc:
            last_error = exc
            if attempt >= config.step_retries:
                break
            time.sleep(0.6 * attempt)
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt >= config.step_retries:
                break
            time.sleep(0.6 * attempt)

    raise MapsScraperError(
        f"Falha ao {step_name} após {config.step_retries} tentativas. "
        "O layout do Google Maps pode ter mudado."
    ) from last_error


def _ensure_not_timed_out(started_at: float, total_timeout_seconds: int) -> None:
    if time.monotonic() - started_at > total_timeout_seconds:
        raise MapsScraperError(
            f"Tempo limite total excedido ({total_timeout_seconds}s) durante a coleta de reviews."
        )
