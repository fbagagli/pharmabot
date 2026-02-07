from typing import List
from sqlmodel import Session, select
from pharmabot.models import BasketItem, ProductCatalog
from pharmabot.services import price_optimizer


class ProductNotFoundError(Exception):
    pass


class ItemNotPresentError(Exception):
    pass


def add_item_to_basket(session: Session, product_id: int, quantity: int) -> BasketItem:
    if quantity <= 0:
        raise ValueError("Quantity must be a positive integer")

    # Check if product exists
    product = session.get(ProductCatalog, product_id)
    if not product:
        raise ProductNotFoundError(f"Product with ID {product_id} not found")

    # Check if item already exists in basket
    statement = select(BasketItem).where(BasketItem.product_id == product_id)
    basket_item = session.exec(statement).first()

    if basket_item:
        basket_item.quantity += quantity
    else:
        basket_item = BasketItem(product_id=product_id, quantity=quantity)
        session.add(basket_item)

    session.commit()
    session.refresh(basket_item)
    return basket_item


def update_basket_item_quantity(
    session: Session, product_id: int, quantity: int
) -> BasketItem:
    if quantity <= 0:
        raise ValueError("Quantity must be a positive integer")

    statement = select(BasketItem).where(BasketItem.product_id == product_id)
    basket_item = session.exec(statement).first()

    if not basket_item:
        raise ItemNotPresentError(f"Product with ID {product_id} is not in the basket")

    basket_item.quantity = quantity
    session.add(basket_item)
    session.commit()
    session.refresh(basket_item)
    return basket_item


def remove_item_from_basket(session: Session, product_id: int) -> None:
    statement = select(BasketItem).where(BasketItem.product_id == product_id)
    basket_item = session.exec(statement).first()

    if not basket_item:
        raise ItemNotPresentError(f"Product with ID {product_id} is not in the basket")

    session.delete(basket_item)
    session.commit()


def list_basket_items(session: Session) -> List[BasketItem]:
    statement = select(BasketItem)
    return list(session.exec(statement).all())


def optimize_basket(
    session: Session, limit: str = "3", max_orders: int = 1
) -> List[price_optimizer.Solution]:
    basket = session.exec(select(BasketItem)).all()
    optimizer = price_optimizer.PriceOptimizer.from_session(session, basket)

    # Parse limits
    limits_dict = {}
    parts = [p.strip() for p in limit.split(",") if p.strip()]

    if not parts:
        # Default behavior if empty string
        for k in range(1, max_orders + 1):
            limits_dict[k] = 3
    elif len(parts) == 1:
        # Apply single value to all
        try:
            val = int(parts[0])
            for k in range(1, max_orders + 1):
                limits_dict[k] = val
        except ValueError:
             # Fallback
             for k in range(1, max_orders + 1):
                limits_dict[k] = 3
    else:
        # Apply specific values per order count
        for k in range(1, max_orders + 1):
            idx = k - 1
            if idx < len(parts):
                try:
                    limits_dict[k] = int(parts[idx])
                except ValueError:
                    limits_dict[k] = 0
            else:
                # If not specified, default to 0 (don't show) or 1?
                # Usually if I say "limit 5,2", I don't care about k=3.
                limits_dict[k] = 0

    return optimizer.find_best_solutions(max_orders=max_orders, limits=limits_dict)
