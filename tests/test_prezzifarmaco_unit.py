from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pharmabot.exceptions import ScraperBlockedError
from pharmabot.services.scraping.base import BaseScraperProvider, ScrapedOffer
from pharmabot.services.scraping.providers.prezzifarmaco import (
    PrezziFarmacoProvider,
    clean_price,
)
from pharmabot.services.scraping.registry import (
    get_scraper_provider,
    register_scraper_provider,
)


# --- clean_price Tests ---


def test_clean_price_formats():
    # Comma format
    assert clean_price("12,50 €") == Decimal("12.50")
    assert clean_price("12,50") == Decimal("12.50")

    # Period format
    assert clean_price("12.50 €") == Decimal("12.50")
    assert clean_price("9.99") == Decimal("9.99")

    # Integer format
    assert clean_price("10 €") == Decimal("10.00")
    assert clean_price("0") == Decimal("0.00")

    # With surrounding text
    assert clean_price("Spedizione 4,50 €") == Decimal("4.50")
    assert clean_price("Gratis per ordini superiori a 59,00 €") == Decimal("59.00")

    # Empty and invalid text
    assert clean_price("") == Decimal("0.00")
    assert clean_price("Gratis") == Decimal("0.00")
    assert clean_price("No price available") == Decimal("0.00")


# --- HTML Parsing Tests ---

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="productCard">
        <div class="logo">
            <img src="https://static.prezzifarmaco.it/ajax/logo-negozio/10.png" alt="Farmacia Alpha" />
        </div>
        <div class="price">12,50 €</div>
        <div class="sendpricetip">Spedizione 4,90 €</div>
        <div>Gratis per ordini superiori a 49,90 €</div>
    </div>
    <div class="productCard">
        <a href="/scheda-negozio/farmacia-beta" aria-label="Farmacia Beta"></a>
        <span class="basic_price">14.99 €</span>
        <div class="sendpricetip">Spedizione gratuita</div>
    </div>
    <div class="productCard">
        <img srcset="https://static.prezzifarmaco.it/ajax/logo-negozio/30.png" alt="Farmacia Gamma" />
        <span class="nero">20,00 €</span>
        <div class="shipping-info">Spedizione 3,50 €</div>
    </div>
    <!-- Swiper slide should be ignored -->
    <div class="productCard swiper-slide">
        <img src="/ajax/logo-negozio/99.png" alt="Carousel Pharmacy" />
        <div class="price">1,00 €</div>
    </div>
    <!-- Card with missing price should be skipped -->
    <div class="productCard">
        <img src="/ajax/logo-negozio/88.png" alt="No Price Pharmacy" />
        <div>Out of stock</div>
    </div>
</body>
</html>
"""


def test_parse_html_offers():
    provider = PrezziFarmacoProvider()
    offers = provider._parse_html(SAMPLE_HTML)

    assert len(offers) == 3

    # Offer 1
    assert offers[0].pharmacy_name == "Farmacia Alpha"
    assert offers[0].price == Decimal("12.50")
    assert offers[0].shipping_price == Decimal("4.90")
    assert offers[0].free_shipping_over == Decimal("49.90")

    # Offer 2
    assert offers[1].pharmacy_name == "Farmacia Beta"
    assert offers[1].price == Decimal("14.99")
    assert offers[1].shipping_price == Decimal("0.00")
    assert offers[1].free_shipping_over is None

    # Offer 3
    assert offers[2].pharmacy_name == "Farmacia Gamma"
    assert offers[2].price == Decimal("20.00")
    assert offers[2].shipping_price == Decimal("3.50")
    assert offers[2].free_shipping_over is None


# --- PrezziFarmacoProvider.scrape Mock Tests ---


def test_scrape_minsan_direct_success():
    provider = PrezziFarmacoProvider()
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.url = httpx.URL("https://www.prezzifarmaco.it/925512636")
    mock_response.text = SAMPLE_HTML

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        offers = provider.scrape("925512636")

        mock_get.assert_called_once_with("https://www.prezzifarmaco.it/925512636")
        assert len(offers) == 3
        assert offers[0].pharmacy_name == "Farmacia Alpha"


def test_scrape_minsan_fallback_to_cerca():
    provider = PrezziFarmacoProvider()

    res_404 = MagicMock(spec=httpx.Response)
    res_404.status_code = 404
    res_404.url = httpx.URL("https://www.prezzifarmaco.it/925512636")

    res_cerca = MagicMock(spec=httpx.Response)
    res_cerca.status_code = 200
    res_cerca.url = httpx.URL("https://www.prezzifarmaco.it/cerca?query=925512636")
    res_cerca.text = SAMPLE_HTML

    with patch.object(
        provider._client, "get", side_effect=[res_404, res_cerca]
    ) as mock_get:
        offers = provider.scrape("925512636")

        assert mock_get.call_count == 2
        mock_get.assert_any_call("https://www.prezzifarmaco.it/925512636")
        mock_get.assert_any_call("https://www.prezzifarmaco.it/cerca?query=925512636")
        assert len(offers) == 3


def test_scrape_name_query():
    provider = PrezziFarmacoProvider()

    res_cerca = MagicMock(spec=httpx.Response)
    res_cerca.status_code = 200
    res_cerca.url = httpx.URL("https://www.prezzifarmaco.it/cerca?query=NeoBianacid")
    res_cerca.text = SAMPLE_HTML

    with patch.object(provider._client, "get", return_value=res_cerca) as mock_get:
        offers = provider.scrape("NeoBianacid")

        mock_get.assert_called_once_with(
            "https://www.prezzifarmaco.it/cerca?query=NeoBianacid"
        )
        assert len(offers) == 3


def test_scrape_empty_query():
    provider = PrezziFarmacoProvider()
    assert provider.scrape("") == []
    assert provider.scrape("   ") == []


def test_scrape_empty_results_404():
    provider = PrezziFarmacoProvider()

    res_404 = MagicMock(spec=httpx.Response)
    res_404.status_code = 404
    res_404.url = httpx.URL("https://www.prezzifarmaco.it/999999999")

    res_empty_cerca = MagicMock(spec=httpx.Response)
    res_empty_cerca.status_code = 200
    res_empty_cerca.url = httpx.URL(
        "https://www.prezzifarmaco.it/cerca?query=999999999"
    )
    res_empty_cerca.text = "<html><body>No products found</body></html>"

    with patch.object(provider._client, "get", side_effect=[res_404, res_empty_cerca]):
        offers = provider.scrape("999999999")
        assert offers == []


def test_scrape_http_error():
    provider = PrezziFarmacoProvider()
    with patch.object(
        provider._client,
        "get",
        side_effect=httpx.RequestError("Network error"),
    ):
        offers = provider.scrape("NeoBianacid")
        assert offers == []


# --- Blocked and Captcha Handling ---


def test_scrape_blocked_403():
    provider = PrezziFarmacoProvider()
    res_403 = MagicMock(spec=httpx.Response)
    res_403.status_code = 403
    res_403.url = httpx.URL("https://www.prezzifarmaco.it/925512636")

    with patch.object(provider._client, "get", return_value=res_403):
        with pytest.raises(
            ScraperBlockedError, match="blocked by captcha or rate limiting"
        ):
            provider.scrape("925512636")


def test_scrape_blocked_429():
    provider = PrezziFarmacoProvider()
    res_429 = MagicMock(spec=httpx.Response)
    res_429.status_code = 429
    res_429.url = httpx.URL("https://www.prezzifarmaco.it/925512636")

    with patch.object(provider._client, "get", return_value=res_429):
        with pytest.raises(
            ScraperBlockedError, match="blocked by captcha or rate limiting"
        ):
            provider.scrape("925512636")


def test_scrape_blocked_captcha_redirect():
    provider = PrezziFarmacoProvider()
    res_captcha = MagicMock(spec=httpx.Response)
    res_captcha.status_code = 200
    res_captcha.url = httpx.URL("https://www.prezzifarmaco.it/captcha?challenge=123")

    with patch.object(provider._client, "get", return_value=res_captcha):
        with pytest.raises(
            ScraperBlockedError, match="blocked by captcha or rate limiting"
        ):
            provider.scrape("925512636")


# --- Registry and Factory Tests ---


def test_get_scraper_provider_prezzifarmaco():
    provider = get_scraper_provider("prezzifarmaco")
    assert isinstance(provider, PrezziFarmacoProvider)
    assert provider.name == "prezzifarmaco"

    # Case-insensitive
    provider_upper = get_scraper_provider("PREZZIFARMACO")
    assert isinstance(provider_upper, PrezziFarmacoProvider)


def test_get_scraper_provider_unknown():
    with pytest.raises(ValueError, match="Unknown scraper provider 'unknown_provider'"):
        get_scraper_provider("unknown_provider")


def test_register_custom_provider():
    class DummyProvider(BaseScraperProvider):
        name = "dummy"

        def scrape(self, query: str) -> list[ScrapedOffer]:
            return [
                ScrapedOffer(
                    pharmacy_name="Dummy Pharm",
                    price=Decimal("1.00"),
                    shipping_price=Decimal("0.00"),
                )
            ]

    register_scraper_provider("dummy", DummyProvider)
    provider = get_scraper_provider("dummy")
    assert isinstance(provider, DummyProvider)
    offers = provider.scrape("test")
    assert len(offers) == 1
    assert offers[0].pharmacy_name == "Dummy Pharm"
