from decimal import Decimal
from typing import List, Dict
from pydantic import BaseModel
from sqlmodel import Session, select
from pharmabot.models import Pharmacy, Offer, BasketItem

# --- Data Structures (Pydantic) ---


class BasketContent(BaseModel):
    items: Dict[int, int]


class InventoryMatch(BaseModel):
    product_id: int
    price: Decimal
    quantity_needed: int
    subtotal: Decimal


class PharmacyOption(BaseModel):
    pharmacy: Pharmacy
    matches: List[InventoryMatch]

    found_all_items: bool
    items_cost: Decimal
    shipping_cost: Decimal
    total_cost: Decimal
    missing_count: int

    class Config:
        arbitrary_types_allowed = True


# --- The Logic Class ---


class PriceOptimizer:
    def __init__(self, basket: BasketContent, inventories: List[PharmacyOption]):
        self.basket = basket
        self.inventories = inventories

    @classmethod
    def from_session(
        cls, session: Session, basket_items: List[BasketItem]
    ) -> "PriceOptimizer":
        basket_map = {b.product_id: b.quantity for b in basket_items}
        product_ids = list(basket_map.keys())
        basket_content = BasketContent(items=basket_map)

        # Fetch offers + pharmacy info
        statement = (
            select(Offer, Pharmacy)
            .join(Pharmacy)
            .where(Offer.product_id.in_(product_ids))
        )
        results = session.exec(statement).all()

        grouped_data = {}
        for offer, pharmacy in results:
            if pharmacy.id not in grouped_data:
                grouped_data[pharmacy.id] = {"pharmacy": pharmacy, "offers": []}
            grouped_data[pharmacy.id]["offers"].append(offer)

        options = []
        for pid, data in grouped_data.items():
            pharmacy = data["pharmacy"]
            offers = data["offers"]

            matches = []
            current_items_cost = Decimal(0)
            found_count = 0

            for offer in offers:
                qty = basket_map[offer.product_id]
                cost = offer.price * qty
                matches.append(
                    InventoryMatch(
                        product_id=offer.product_id,
                        price=offer.price,
                        quantity_needed=qty,
                        subtotal=cost,
                    )
                )
                current_items_cost += cost
                found_count += 1

            # Determine Shipping
            shipping = pharmacy.base_shipping_cost
            if (
                pharmacy.free_shipping_threshold is not None
                and current_items_cost >= pharmacy.free_shipping_threshold
            ):
                shipping = Decimal(0)

            # Create Option
            options.append(
                PharmacyOption(
                    pharmacy=pharmacy,
                    matches=matches,
                    found_all_items=(found_count == len(basket_map)),
                    missing_count=len(basket_map) - found_count,
                    items_cost=current_items_cost,
                    shipping_cost=shipping,
                    total_cost=current_items_cost + shipping,
                )
            )

        return cls(basket=basket_content, inventories=options)

    def find_best_pharmacies(self, limit: int = 3) -> List[PharmacyOption]:
        """
        Returns the top N cheapest pharmacies that contain ALL items.
        """
        # 1. Filter: Must have all items
        valid_options = [opt for opt in self.inventories if opt.found_all_items]

        # 2. Sort: Cheapest Total Cost first
        # (Optional secondary sort: Cheapest shipping)
        valid_options.sort(key=lambda x: x.total_cost)

        # 3. Slice
        return valid_options[:limit]
