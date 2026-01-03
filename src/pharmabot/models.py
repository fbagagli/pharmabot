from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Product(SQLModel, table=True):
    minsan: str = Field(primary_key=True)
    name: str
    quantity: int = Field(default=1)

    offers: List["Offer"] = Relationship(
        back_populates="product", sa_relationship_kwargs={"cascade": "all, delete"}
    )


class Pharmacy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    base_shipping_cost: Decimal = Field(default=0, max_digits=5, decimal_places=2)
    free_shipping_threshold: Optional[Decimal] = Field(
        default=None, max_digits=6, decimal_places=2
    )

    offers: List["Offer"] = Relationship(back_populates="pharmacy")


class Offer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    price: Decimal = Field(max_digits=6, decimal_places=2)
    url: str
    available: bool = Field(default=True)
    timestamp: datetime = Field(default_factory=datetime.now)

    pharmacy_id: int = Field(foreign_key="pharmacy.id")
    pharmacy: Pharmacy = Relationship(back_populates="offers")

    product_minsan: str = Field(foreign_key="product.minsan")
    product: Product = Relationship(back_populates="offers")
