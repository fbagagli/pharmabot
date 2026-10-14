from decimal import Decimal
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.orm import joinedload
from sqlmodel import Session, delete, select

from pharmabot.models import BasketItem, Offer, Pharmacy, ProductCatalog
from pharmabot.services.scraping import get_scraper_provider

console = Console()


def scrape_product(query: str, provider_name: str = "prezzifarmaco") -> list[dict]:
    """Execute scraping for a single query using the specified scraper provider.

    Returns a list of offer dictionaries.
    """
    provider = get_scraper_provider(provider_name)
    offers = provider.scrape(query)
    return [offer.to_dict() for offer in offers]


def scrape_basket(
    session: Session,
    provider_name: str = "prezzifarmaco",
    incremental: bool = True,
) -> list[Offer]:
    """Scrape product offers for all items in the basket.

    - Fetches BasketItems from DB.
    - If empty, prints a message and returns.
    - If incremental: filters out products that already have offers in the DB.
    - For each item, determines query = product.minsan if product.minsan else product.name.
    - Calls provider .scrape(query).
    - For each offer:
      Find or create Pharmacy(name=..., base_shipping_cost=..., free_shipping_threshold=...).
      Create Offer(price=..., pharmacy=pharmacy, product=product).
      Commit to session.
    - Return the list of created offers.
    """
    console.print(Panel("Starting Basket Scraping...", style="bold magenta"))

    basket_items = session.exec(select(BasketItem)).all()
    if not basket_items:
        console.print("[red]Basket is empty. Nothing to scrape.[/]")
        return []

    created_offers: list[Offer] = []
    provider = get_scraper_provider(provider_name)

    existing_offer_product_ids: set[int] = set()
    if incremental:
        existing_offer_product_ids = set(session.exec(select(Offer.product_id)).all())

    for item in basket_items:
        product = session.get(ProductCatalog, item.product_id)
        if not product:
            console.print(f"[red]Product for basket item {item.id} not found.[/]")
            continue

        if incremental and product.id in existing_offer_product_ids:
            console.print(
                f"[yellow]Skipping {product.name} (already has offers in DB).[/]"
            )
            continue

        query = product.minsan if product.minsan else product.name
        console.print(
            f"\n[bold cyan]Scraping product: {product.name} (Query: {query})[/]"
        )

        try:
            scraped_offers = provider.scrape(query)
        except Exception as e:
            console.print(f"[bold red]Error scraping {product.name}:[/bold red] {e}")
            continue

        if not scraped_offers:
            console.print(f"[yellow]No offers found for {product.name}[/]")
            continue

        console.print(
            f"[green]Found {len(scraped_offers)} offers for {product.name}. Saving to DB...[/]"
        )

        if not incremental and product.id is not None:
            session.exec(delete(Offer).where(Offer.product_id == product.id))
            session.commit()

        for scraped in scraped_offers:
            if isinstance(scraped, dict):
                pharm_name = scraped["pharmacy"]
                raw_price = scraped["price"]
                raw_shipping = scraped.get("shipping_price", 0)
                raw_threshold = scraped.get("free_shipping_over")
            else:
                pharm_name = scraped.pharmacy_name
                raw_price = scraped.price
                raw_shipping = scraped.shipping_price
                raw_threshold = scraped.free_shipping_over

            price = Decimal(str(raw_price))
            shipping_cost = (
                Decimal(str(raw_shipping)) if raw_shipping is not None else Decimal(0)
            )
            threshold = (
                Decimal(str(raw_threshold)) if raw_threshold is not None else None
            )

            pharmacy = session.exec(
                select(Pharmacy).where(Pharmacy.name == pharm_name)
            ).first()
            if not pharmacy:
                pharmacy = Pharmacy(
                    name=pharm_name,
                    base_shipping_cost=shipping_cost,
                    free_shipping_threshold=threshold,
                )
                session.add(pharmacy)
                session.commit()
                session.refresh(pharmacy)
            else:
                pharmacy.base_shipping_cost = shipping_cost
                pharmacy.free_shipping_threshold = threshold
                session.add(pharmacy)
                session.commit()
                session.refresh(pharmacy)

            offer = Offer(
                price=price,
                pharmacy=pharmacy,
                product=product,
            )
            session.add(offer)
            created_offers.append(offer)

        session.commit()

    console.print(Panel("Basket Scraping Complete!", style="bold green"))
    return created_offers


def clear_database(session: Session) -> None:
    """Delete all Offer and Pharmacy records from the database."""
    console.print("[yellow]Clearing all offers and pharmacies...[/]")
    session.exec(delete(Offer))
    session.exec(delete(Pharmacy))
    session.commit()
    console.print("[green]✔ Database cleared.[/]")


def list_offers(
    session: Session,
    product_id: Optional[int] = None,
    pharmacy_id: Optional[int] = None,
) -> list[Offer]:
    """Query Offer table with optional filtering by product or pharmacy."""
    statement = (
        select(Offer)
        .join(ProductCatalog)
        .join(Pharmacy)
        .options(joinedload(Offer.product), joinedload(Offer.pharmacy))
    )

    if product_id is not None:
        statement = statement.where(Offer.product_id == product_id)
    if pharmacy_id is not None:
        statement = statement.where(Offer.pharmacy_id == pharmacy_id)

    statement = statement.order_by(ProductCatalog.name, Offer.price)
    results = session.exec(statement).all()
    return list(results)


def list_pharmacies(
    session: Session,
    name_filter: Optional[str] = None,
) -> list[Pharmacy]:
    """Query Pharmacy table with optional name filtering (case-insensitive)."""
    statement = select(Pharmacy)
    if name_filter:
        statement = statement.where(Pharmacy.name.ilike(f"%{name_filter}%"))
    statement = statement.order_by(Pharmacy.name)
    results = session.exec(statement).all()
    return list(results)
