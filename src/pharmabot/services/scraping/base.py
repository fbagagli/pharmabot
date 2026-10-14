from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional
from pharmabot.exceptions import ScraperBlockedError


@dataclass
class ScrapedOffer:
    pharmacy_name: str
    price: Decimal
    shipping_price: Decimal
    free_shipping_over: Optional[Decimal] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pharmacy": self.pharmacy_name,
            "price": float(self.price),
            "shipping_price": float(self.shipping_price),
            "free_shipping_over": (
                float(self.free_shipping_over)
                if self.free_shipping_over is not None
                else None
            ),
        }


class BaseScraperProvider(ABC):
    name: str

    @abstractmethod
    def scrape(self, query: str) -> list[ScrapedOffer]:
        """Scrape product offers for a given MINSAN or search query."""
        pass


__all__ = ["ScrapedOffer", "BaseScraperProvider", "ScraperBlockedError"]
