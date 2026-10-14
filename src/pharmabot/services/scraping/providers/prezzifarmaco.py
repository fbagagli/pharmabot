import logging
import re
import socket
from decimal import Decimal
from typing import Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from pharmabot.exceptions import ScraperBlockedError
from pharmabot.services.scraping.base import BaseScraperProvider, ScrapedOffer

logger = logging.getLogger(__name__)

# Prefer IPv4 resolution in environments where IPv6 address triggers Cloudflare rate-limits
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_first_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in res if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else res


socket.getaddrinfo = _ipv4_first_getaddrinfo


def clean_price(price_str: str) -> Decimal:
    """Extract price decimal from a string formatted e.g. as '12,50 €' or '12.50'."""
    if not price_str:
        return Decimal("0.00")
    match = re.search(r"(\d+[\.,]\d{2})", price_str)
    if match:
        return Decimal(match.group(1).replace(",", "."))
    match_int = re.search(r"\b(\d+)\b", price_str)
    if match_int:
        return Decimal(match_int.group(1)).quantize(Decimal("0.01"))
    return Decimal("0.00")


class PrezziFarmacoProvider(BaseScraperProvider):
    name: str = "prezzifarmaco"
    base_url: str = "https://www.prezzifarmaco.it"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ):
        if base_url:
            self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
        }
        self._client = client or httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers=self.headers,
        )

    def scrape(self, query: str) -> list[ScrapedOffer]:
        """Scrape offers from PrezziFarmaco for a MINSAN code or query string."""
        normalized_query = query.strip()
        if not normalized_query:
            return []

        # Determine URL: direct MINSAN if numeric/starts with digits, else cerca
        is_minsan = bool(re.match(r"^\d+", normalized_query))
        response = None

        if is_minsan:
            # Extract leading digits or minsan code
            minsan_match = re.match(r"^(\d+)", normalized_query)
            minsan = minsan_match.group(1) if minsan_match else normalized_query
            minsan_url = f"{self.base_url}/{minsan}"
            try:
                response = self._client.get(minsan_url)
                if response.status_code == 404:
                    response = None
            except httpx.HTTPError as e:
                logger.warning(f"Error requesting MINSAN URL {minsan_url}: {e}")
                response = None

        if response is None:
            cerca_url = f"{self.base_url}/cerca?query={quote_plus(normalized_query)}"
            try:
                response = self._client.get(cerca_url)
            except httpx.HTTPError as e:
                logger.error(f"Error querying search URL {cerca_url}: {e}")
                return []

        # Check for captcha or blocking
        if "captcha" in str(response.url) or response.status_code in (403, 429):
            raise ScraperBlockedError(
                f"PrezziFarmaco request blocked by captcha or rate limiting "
                f"(status={response.status_code}, url={response.url})"
            )

        if response.status_code != 200:
            logger.warning(
                f"Unexpected status code {response.status_code} for query '{query}'"
            )
            return []

        return self._parse_html(response.text)

    def _parse_html(self, html_content: str) -> list[ScrapedOffer]:
        """Parse PrezziFarmaco product page HTML into list of ScrapedOffer."""
        soup = BeautifulSoup(html_content, "html.parser")
        card_elements = soup.find_all("div", class_="productCard")
        offers: list[ScrapedOffer] = []

        for card in card_elements:
            # Skip recommendation / carousel slides
            classes = card.get("class", [])
            if "swiper-slide" in classes:
                continue

            # 1. Pharmacy Name
            pharmacy_name = self._extract_pharmacy_name(card)

            # 2. Price
            price = self._extract_price(card)
            if price is None:
                continue

            # 3. Shipping Cost
            shipping_price = self._extract_shipping_price(card)

            # 4. Free Shipping Threshold
            free_shipping_over = self._extract_free_shipping_threshold(card)

            offers.append(
                ScrapedOffer(
                    pharmacy_name=pharmacy_name,
                    price=price,
                    shipping_price=shipping_price,
                    free_shipping_over=free_shipping_over,
                )
            )

        return offers

    def _extract_pharmacy_name(self, card) -> str:
        """Extract pharmacy name from card, falling back to 'Unknown'."""
        img = card.find("img", src=re.compile(r"ajax/logo-negozio", re.I))
        if not img:
            img = card.find("img", srcset=re.compile(r"ajax/logo-negozio", re.I))

        if img and img.get("alt"):
            alt_text = img["alt"].strip()
            if alt_text:
                return alt_text

        merchant_el = card.find("a", href=re.compile(r"/scheda-negozio/"))
        if merchant_el:
            m_img = merchant_el.find("img")
            if m_img and m_img.get("alt") and m_img["alt"].strip():
                return m_img["alt"].strip()
            if merchant_el.get("aria-label") and merchant_el["aria-label"].strip():
                return merchant_el["aria-label"].strip()
            text = merchant_el.get_text(strip=True)
            if text:
                return text

        return "Unknown"

    def _extract_price(self, card) -> Optional[Decimal]:
        """Extract item price from card."""
        price_el = card.find(
            lambda el: el.name in ["span", "p", "div"]
            and (
                any(
                    c in el.get("class", [])
                    for c in ["price", "basic_price", "nero", "text-bigger"]
                )
                or ("€" in el.get_text() and "spedizion" not in el.get_text().lower())
            )
        )
        if price_el:
            m = re.search(r"(\d+[\.,]\d{2})", price_el.get_text())
            if m:
                return clean_price(m.group(1))

        # Fallback regex in card text
        m = re.search(r"(\d+[\.,]\d{2})\s*€", card.get_text())
        if m:
            return clean_price(m.group(1))

        return None

    def _extract_shipping_price(self, card) -> Decimal:
        """Extract shipping price from card. Defaults to Decimal('0.00')."""
        ship_el = card.find(class_=re.compile(r"sendpricetip", re.I))
        if not ship_el:
            ship_el = card.find(
                lambda el: el.name in ["span", "div", "p"]
                and "spedizion" in el.get_text().lower()
                and "superiori" not in el.get_text().lower()
            )

        if ship_el:
            stext = ship_el.get_text(strip=True).lower()
            if "gratis" in stext or "gratuita" in stext:
                return Decimal("0.00")
            m = re.search(r"(\d+[\.,]\d{2})", stext)
            if m:
                return clean_price(m.group(1))

        return Decimal("0.00")

    def _extract_free_shipping_threshold(self, card) -> Optional[Decimal]:
        """Extract free shipping threshold if mentioned (e.g. 'Gratis per ordini superiori a 59,00€')."""
        card_text = card.get_text()
        m = re.search(
            r"Gratis per ordini superiori a\s*(\d+[\.,]\d{2})", card_text, re.I
        )
        if m:
            return clean_price(m.group(1))
        return None
