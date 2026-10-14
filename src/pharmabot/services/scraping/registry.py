from typing import Any
from pharmabot.services.scraping.base import BaseScraperProvider
from pharmabot.services.scraping.providers.prezzifarmaco import PrezziFarmacoProvider

_PROVIDERS: dict[str, type[BaseScraperProvider]] = {}


def register_scraper_provider(
    name: str, provider_cls: type[BaseScraperProvider]
) -> None:
    """Register a scraper provider class under a name."""
    _PROVIDERS[name.lower()] = provider_cls


def get_scraper_provider(
    name: str = "prezzifarmaco", **kwargs: Any
) -> BaseScraperProvider:
    """Retrieve an instantiated scraper provider by name."""
    provider_cls = _PROVIDERS.get(name.lower())
    if not provider_cls:
        available = ", ".join(repr(k) for k in _PROVIDERS.keys())
        raise ValueError(
            f"Unknown scraper provider '{name}'. Available providers: [{available}]"
        )
    return provider_cls(**kwargs)


# Register default providers
register_scraper_provider(PrezziFarmacoProvider.name, PrezziFarmacoProvider)

__all__ = [
    "_PROVIDERS",
    "register_scraper_provider",
    "get_scraper_provider",
]
