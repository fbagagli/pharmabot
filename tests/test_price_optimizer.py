from decimal import Decimal
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from pharmabot.models import ProductCatalog, Pharmacy, Offer, BasketItem
from pharmabot.services.price_optimizer import PriceOptimizer


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=None
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_single_pharmacy_optimization(session: Session):
    # Setup
    p1 = Pharmacy(
        name="P1",
        base_shipping_cost=Decimal("5.00"),
        free_shipping_threshold=Decimal("50.00"),
    )
    session.add(p1)

    prod1 = ProductCatalog(name="Item1", minsan="123")
    prod2 = ProductCatalog(name="Item2", minsan="456")
    session.add(prod1)
    session.add(prod2)
    session.commit()

    # P1 has both
    o1 = Offer(pharmacy_id=p1.id, product_id=prod1.id, price=Decimal("10.00"))
    o2 = Offer(pharmacy_id=p1.id, product_id=prod2.id, price=Decimal("10.00"))
    session.add(o1)
    session.add(o2)

    # Basket
    b1 = BasketItem(product_id=prod1.id, quantity=1)
    b2 = BasketItem(product_id=prod2.id, quantity=1)
    session.add(b1)
    session.add(b2)
    session.commit()

    basket_items = [b1, b2]
    optimizer = PriceOptimizer.from_session(session, basket_items)

    solutions = optimizer.find_best_solutions(max_orders=1)

    assert len(solutions) == 1
    sol = solutions[0]
    assert sol.order_count == 1
    assert sol.orders[0].pharmacy.name == "P1"
    assert sol.total_cost == Decimal("25.00")  # 10+10+5


def test_multi_pharmacy_optimization(session: Session):
    # Scenario: P1 expensive but single order. P2 and P3 cheap items + low threshold.

    # P1: Item A ($20), Item B ($20). Shipping $5. Total $45.
    p1 = Pharmacy(
        name="P1",
        base_shipping_cost=Decimal("5.00"),
        free_shipping_threshold=Decimal("100.00"),
    )

    # P2: Item A ($5). Shipping $5. Free > $4. (So Free). Total $5.
    p2 = Pharmacy(
        name="P2",
        base_shipping_cost=Decimal("5.00"),
        free_shipping_threshold=Decimal("4.00"),
    )

    # P3: Item B ($5). Shipping $5. Free > $4. (So Free). Total $5.
    p3 = Pharmacy(
        name="P3",
        base_shipping_cost=Decimal("5.00"),
        free_shipping_threshold=Decimal("4.00"),
    )

    session.add(p1)
    session.add(p2)
    session.add(p3)

    prodA = ProductCatalog(name="ItemA", minsan="A")
    prodB = ProductCatalog(name="ItemB", minsan="B")
    session.add(prodA)
    session.add(prodB)
    session.commit()

    # Offers
    session.add(Offer(pharmacy_id=p1.id, product_id=prodA.id, price=Decimal("20.00")))
    session.add(Offer(pharmacy_id=p1.id, product_id=prodB.id, price=Decimal("20.00")))

    session.add(Offer(pharmacy_id=p2.id, product_id=prodA.id, price=Decimal("5.00")))
    # P2 doesn't have B

    session.add(Offer(pharmacy_id=p3.id, product_id=prodB.id, price=Decimal("5.00")))
    # P3 doesn't have A

    # Basket
    session.add(BasketItem(product_id=prodA.id, quantity=1))
    session.add(BasketItem(product_id=prodB.id, quantity=1))
    session.commit()

    basket = session.exec(select(BasketItem)).all()
    optimizer = PriceOptimizer.from_session(session, basket)

    # Check max_orders=1
    sols_1 = optimizer.find_best_solutions(max_orders=1)
    # Should find P1
    assert len(sols_1) == 1
    assert sols_1[0].total_cost == Decimal("45.00")

    # Check max_orders=2
    # Should find P2+P3 as best solution
    sols_2 = optimizer.find_best_solutions(max_orders=2, limits={1: 1, 2: 1})

    # We expect 2 solutions in total if limits apply correctly?
    # Or just top ones.
    # The list is flat.
    # We should have P1 (order=1) and P2+P3 (order=2).

    # P2+P3 cost: 5 (A) + 0 (ship) + 5 (B) + 0 (ship) = 10.
    # P1 cost: 45.

    # Sort by cost
    sols_2.sort(key=lambda x: x.total_cost)

    assert sols_2[0].total_cost == Decimal("10.00")
    assert sols_2[0].order_count == 2

    p_names = {o.pharmacy.name for o in sols_2[0].orders}
    assert "P2" in p_names
    assert "P3" in p_names


def test_shipping_threshold_sensitivity(session: Session):
    # Scenario: Buying everything at P1 is cheaper than splitting because of shipping,
    # even if item price is higher at P1.

    # P1: Item A ($10), Item B ($10). Free Ship > $15. Total $20.
    p1 = Pharmacy(
        name="P1",
        base_shipping_cost=Decimal("10.00"),
        free_shipping_threshold=Decimal("15.00"),
    )

    # P2: Item A ($8). Shipping $10. Total $18.
    p2 = Pharmacy(
        name="P2", base_shipping_cost=Decimal("10.00"), free_shipping_threshold=None
    )

    # P3: Item B ($8). Shipping $10. Total $18.
    p3 = Pharmacy(
        name="P3", base_shipping_cost=Decimal("10.00"), free_shipping_threshold=None
    )

    # Splitting P2+P3: $8+$10 + $8+$10 = $36.
    # P1: $20.

    session.add(p1)
    session.add(p2)
    session.add(p3)

    prodA = ProductCatalog(name="ItemA")
    prodB = ProductCatalog(name="ItemB")
    session.add(prodA)
    session.add(prodB)
    session.commit()

    session.add(Offer(pharmacy_id=p1.id, product_id=prodA.id, price=Decimal("10.00")))
    session.add(Offer(pharmacy_id=p1.id, product_id=prodB.id, price=Decimal("10.00")))

    session.add(Offer(pharmacy_id=p2.id, product_id=prodA.id, price=Decimal("8.00")))
    session.add(Offer(pharmacy_id=p3.id, product_id=prodB.id, price=Decimal("8.00")))

    session.add(BasketItem(product_id=prodA.id, quantity=1))
    session.add(BasketItem(product_id=prodB.id, quantity=1))
    session.commit()

    basket = session.exec(select(BasketItem)).all()
    optimizer = PriceOptimizer.from_session(session, basket)

    solutions = optimizer.find_best_solutions(max_orders=2)
    solutions.sort(key=lambda x: x.total_cost)

    assert solutions[0].orders[0].pharmacy.name == "P1"
    assert solutions[0].total_cost == Decimal("20.00")
