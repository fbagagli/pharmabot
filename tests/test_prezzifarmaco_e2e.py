from decimal import Decimal
import pytest
from sqlmodel import Session, select

from pharmabot.models import BasketItem, Offer, ProductCatalog
from pharmabot.services.scraper import scrape_basket, scrape_product


@pytest.mark.e2e
def test_prezzifarmaco_e2e_single_product():
    """Live E2E test: scrape a single product (NeoBianacid) from prezzifarmaco.it."""
    offers = scrape_product("925512636")
    assert len(offers) > 0, "Expected at least one offer for NeoBianacid (925512636)"

    for offer in offers:
        assert isinstance(offer, dict)
        assert "pharmacy" in offer and bool(offer["pharmacy"].strip())
        assert offer["price"] > 0
        assert offer["shipping_price"] >= 0
        if offer.get("free_shipping_over") is not None:
            assert offer["free_shipping_over"] >= 0


@pytest.mark.e2e
def test_prezzifarmaco_e2e_basket_and_incremental(session: Session):
    """Live E2E test: populate basket with two real MINSANs, scrape them, verify DB,

    and verify that incremental scraping skips already scraped products.
    """
    # 1. Add ProductCatalog items for both MINSANs
    p1 = ProductCatalog(
        minsan="925512636",
        name="NeoBianacid 45 compresse masticabili",
    )
    p2 = ProductCatalog(
        minsan="034246025",
        name="Nurofen Influenza e Raffreddore 24 compresse",
    )
    session.add(p1)
    session.add(p2)
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    # 2. Add BasketItem entries
    b1 = BasketItem(product_id=p1.id, quantity=1)
    b2 = BasketItem(product_id=p2.id, quantity=2)
    session.add(b1)
    session.add(b2)
    session.commit()

    # 3. Call scrape_basket with incremental=True
    created_offers = scrape_basket(
        session, provider_name="prezzifarmaco", incremental=True
    )
    assert len(created_offers) > 0

    # 4. Assert offers saved to DB for both products
    p1_offers = session.exec(select(Offer).where(Offer.product_id == p1.id)).all()
    p2_offers = session.exec(select(Offer).where(Offer.product_id == p2.id)).all()
    assert len(p1_offers) > 0, "No offers saved to DB for NeoBianacid"
    assert len(p2_offers) > 0, "No offers saved to DB for Nurofen"

    # 5. Verify prices > 0, pharmacy names not empty, shipping prices >= 0
    all_saved_offers = p1_offers + p2_offers
    for offer in all_saved_offers:
        assert offer.price > Decimal("0.00")
        assert offer.pharmacy is not None
        assert bool(offer.pharmacy.name and offer.pharmacy.name.strip())
        assert offer.pharmacy.base_shipping_cost >= Decimal("0.00")
        if offer.pharmacy.free_shipping_threshold is not None:
            assert offer.pharmacy.free_shipping_threshold >= Decimal("0.00")

    # 6. Test incremental scraping skips already scraped products
    second_run_offers = scrape_basket(
        session, provider_name="prezzifarmaco", incremental=True
    )
    assert len(second_run_offers) == 0, "Incremental run should skip existing products"

    p1_offers_after = session.exec(select(Offer).where(Offer.product_id == p1.id)).all()
    p2_offers_after = session.exec(select(Offer).where(Offer.product_id == p2.id)).all()
    assert len(p1_offers_after) == len(p1_offers)
    assert len(p2_offers_after) == len(p2_offers)
