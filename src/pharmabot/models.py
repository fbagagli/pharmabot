from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class ProductCatalog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    minsan: str = Field(index=True, unique=True)
    name: str

    basket_entries: List["BasketItem"] = Relationship(back_populates="product")
    offers: List["Offer"] = Relationship(back_populates="product")


# this tables below are ephemeral, because in a scrape session Pharmacy and Offer are
# completely replaced. BasketItem is the basket used to base the scraping


class Pharmacy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    base_shipping_cost: Decimal = Field(default=0, max_digits=5, decimal_places=2)
    free_shipping_threshold: Optional[Decimal] = Field(
        default=None, max_digits=6, decimal_places=2
    )

    offers: List["Offer"] = Relationship(back_populates="pharmacy")


class BasketItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quantity: int = Field(default=1)

    product_id: int = Field(foreign_key="productcatalog.id", unique=True)

    product: ProductCatalog = Relationship(back_populates="basket_entries")


class Offer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    price: Decimal = Field(max_digits=6, decimal_places=2)
    timestamp: datetime = Field(default_factory=datetime.now)

    pharmacy_id: int = Field(foreign_key="pharmacy.id")
    pharmacy: Pharmacy = Relationship(back_populates="offers")

    product_id: int = Field(foreign_key="productcatalog.id")
    product: ProductCatalog = Relationship(back_populates="offers")
