from pharmabot.services.scraping.base import (
    BaseScraperProvider,
    ScrapedOffer,
    ScraperBlockedError,
)
from pharmabot.services.scraping.providers.prezzifarmaco import PrezziFarmacoProvider
from pharmabot.services.scraping.registry import (
    get_scraper_provider,
    register_scraper_provider,
)

__all__ = [
    "ScrapedOffer",
    "BaseScraperProvider",
    "PrezziFarmacoProvider",
    "get_scraper_provider",
    "register_scraper_provider",
    "ScraperBlockedError",
]
