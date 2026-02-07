import pytest
from typer.testing import CliRunner
from sqlmodel import Session
from pharmabot.main import app
from pharmabot.models import ProductCatalog, Pharmacy, Offer
from pharmabot.services.scraper import list_offers

runner = CliRunner()

@pytest.fixture(name="populated_db")
def fixture_populated_db(session: Session):
    # Products
    p1 = ProductCatalog(name="Product A", minsan="111")
    p2 = ProductCatalog(name="Product B", minsan="222")
    session.add(p1)
    session.add(p2)
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    # Pharmacies
    ph1 = Pharmacy(name="Pharmacy 1", base_shipping_cost=5.0)
    ph2 = Pharmacy(name="Pharmacy 2", base_shipping_cost=0.0)
    session.add(ph1)
    session.add(ph2)
    session.commit()
    session.refresh(ph1)
    session.refresh(ph2)

    # Offers
    # Product A from Ph1: 10.0
    # Product A from Ph2: 12.0
    # Product B from Ph1: 20.0
    o1 = Offer(price=10.0, pharmacy_id=ph1.id, product_id=p1.id)
    o2 = Offer(price=12.0, pharmacy_id=ph2.id, product_id=p1.id)
    o3 = Offer(price=20.0, pharmacy_id=ph1.id, product_id=p2.id)
    session.add(o1)
    session.add(o2)
    session.add(o3)
    session.commit()

    return {"products": [p1, p2], "pharmacies": [ph1, ph2], "offers": [o1, o2, o3]}

def test_list_offers_service(session: Session, populated_db):
    # Test all offers
    offers = list_offers(session)
    assert len(offers) == 3
    # Check sorting: Product A first (2 offers), then Product B (1 offer)
    # Among Product A offers, price 10.0 < 12.0
    assert offers[0].price == 10.0
    assert offers[0].product.name == "Product A"
    assert offers[1].price == 12.0
    assert offers[1].product.name == "Product A"
    assert offers[2].price == 20.0
    assert offers[2].product.name == "Product B"

    # Test filter by product_id
    p1_id = populated_db["products"][0].id
    offers_p1 = list_offers(session, product_id=p1_id)
    assert len(offers_p1) == 2
    assert all(o.product_id == p1_id for o in offers_p1)

    # Test filter by pharmacy_id
    ph1_id = populated_db["pharmacies"][0].id
    offers_ph1 = list_offers(session, pharmacy_id=ph1_id)
    assert len(offers_ph1) == 2
    assert all(o.pharmacy_id == ph1_id for o in offers_ph1)


def test_list_offers_cli(session: Session, populated_db):
    # Ensure session uses the same engine/transaction as fixture
    # The conftest.py override_get_session handles patching get_session to return `session`

    result = runner.invoke(app, ["scraper", "list-offers"])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    assert "Product A" in result.stdout
    assert "Product B" in result.stdout
    assert "Pharmacy 1" in result.stdout
    assert "10.00 €" in result.stdout
    assert "5.00 €" in result.stdout

    # Test CLI filtering
    p1_id = populated_db["products"][0].id
    result_filter = runner.invoke(app, ["scraper", "list-offers", "--product-id", str(p1_id)])
    assert result_filter.exit_code == 0
    assert "Product A" in result_filter.stdout
    # Depending on table formatting, Product B should not be present as a row
    # But since I'm checking stdout, I should be careful if "Product B" appears in help or something
    # However, for a table row, it should suffice to check presence.
    # To be safer, I can check specific row count or regex match, but basic string check is good for now.
    assert "Product B" not in result_filter.stdout
