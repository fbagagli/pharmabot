from typing import List
from sqlmodel import Session, select
from pharmabot.models import BasketItem, ProductCatalog


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
