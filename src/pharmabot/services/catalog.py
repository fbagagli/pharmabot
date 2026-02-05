from typing import List, Optional
from sqlmodel import Session, select
from pharmabot.models import ProductCatalog, BasketItem


class ProductAlreadyExistsError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


def add_product(
    session: Session, name: str, minsan: Optional[str] = None
) -> ProductCatalog:
    # Check for name uniqueness
    existing_name = session.exec(
        select(ProductCatalog).where(ProductCatalog.name == name)
    ).first()
    if existing_name:
        raise ProductAlreadyExistsError(f"Product with name '{name}' already exists")

    if minsan is not None:
        statement = select(ProductCatalog).where(ProductCatalog.minsan == minsan)
        existing_product = session.exec(statement).first()
        if existing_product:
            raise ProductAlreadyExistsError(
                f"Product with minsan {minsan} already exists"
            )

    product = ProductCatalog(minsan=minsan, name=name)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def remove_product(session: Session, product_id: int) -> None:
    product = session.get(ProductCatalog, product_id)
    if not product:
        raise ProductNotFoundError(f"Product with id {product_id} not found")

    # Cascade delete BasketItems
    # Since we don't have ON DELETE CASCADE in DB, we do it manually.
    # Note: Using execute() for bulk delete or iterating.
    # We can fetch basket items and delete them.
    # Or use delete statement if supported by SQLModel/SQLAlchemy directly

    # Deleting basket items
    basket_items_statement = select(BasketItem).where(
        BasketItem.product_id == product.id
    )
    basket_items = session.exec(basket_items_statement).all()
    for item in basket_items:
        session.delete(item)

    session.delete(product)
    session.commit()


def list_products(session: Session) -> List[ProductCatalog]:
    statement = select(ProductCatalog)
    return list(session.exec(statement).all())


def update_product(session: Session, product_id: int, name: str) -> ProductCatalog:
    product = session.get(ProductCatalog, product_id)
    if not product:
        raise ProductNotFoundError(f"Product with id {product_id} not found")

    product.name = name
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
