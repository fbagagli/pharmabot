from typing import Optional
from rich.console import Console
from rich.table import Table
import typer
from typing_extensions import Annotated

from pharmabot import database
from pharmabot.services import scraper as scraper_service

app = typer.Typer()
console = Console()


@app.command(name="scrape-product")
def scrape_product(
    query: Annotated[str, typer.Argument(help="Minsan code or Product Name")],
    provider: Annotated[
        str, typer.Option(help="Scraper provider name")
    ] = "prezzifarmaco",
):
    """
    Search for a product by Minsan code or Product Name.
    """
    offers = scraper_service.scrape_product(query, provider_name=provider)

    if not offers:
        console.print("[yellow]No offers found.[/yellow]")
        return

    table = Table(title=f"Offers for {query}")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Pharmacy", style="magenta")
    table.add_column("Price", justify="right", style="green")
    table.add_column("Shipping", justify="right", style="blue")
    table.add_column("Free Shipping Over", justify="right", style="yellow")

    for idx, offer in enumerate(offers, start=1):
        free_shipping = (
            f"{offer['free_shipping_over']:.2f} €"
            if offer.get("free_shipping_over") is not None
            else "-"
        )
        table.add_row(
            str(idx),
            offer["pharmacy"],
            f"{offer['price']:.2f} €",
            f"{offer['shipping_price']:.2f} €",
            free_shipping,
        )

    console.print(table)


@app.command(name="search", hidden=True)
def search_alias(
    query: Annotated[str, typer.Argument(help="Minsan code or Product Name")],
    provider: Annotated[
        str, typer.Option(help="Scraper provider name")
    ] = "prezzifarmaco",
):
    """Alias for scrape-product."""
    scrape_product(query=query, provider=provider)


@app.command(name="scrape-basket")
def scrape_basket(
    provider: Annotated[
        str, typer.Option(help="Scraper provider name")
    ] = "prezzifarmaco",
    incremental: Annotated[
        bool, typer.Option(help="Only scrape products without offers in DB")
    ] = True,
):
    """
    Scrape all products in the basket and update the database.
    """
    with database.get_session() as session:
        scraper_service.scrape_basket(
            session, provider_name=provider, incremental=incremental
        )


@app.command(name="all", hidden=True)
def all_alias(
    provider: Annotated[
        str, typer.Option(help="Scraper provider name")
    ] = "prezzifarmaco",
    incremental: Annotated[
        bool, typer.Option(help="Only scrape products without offers in DB")
    ] = True,
):
    """Alias for scrape-basket."""
    scrape_basket(provider=provider, incremental=incremental)


@app.command(name="clear-db")
def clear_db():
    """
    Clear all scraped offers and pharmacies from the database.
    """
    with database.get_session() as session:
        scraper_service.clear_database(session)


@app.command(name="clean", hidden=True)
def clean_alias():
    """Alias for clear-db."""
    clear_db()


@app.command(name="list-offers")
def list_offers(
    product_id: Annotated[
        Optional[int], typer.Option(help="Filter by Product ID")
    ] = None,
    pharmacy_id: Annotated[
        Optional[int], typer.Option(help="Filter by Pharmacy ID")
    ] = None,
):
    """
    List stored offers with optional filtering.
    """
    with database.get_session() as session:
        offers = scraper_service.list_offers(
            session, product_id=product_id, pharmacy_id=pharmacy_id
        )

        if not offers:
            console.print("[yellow]No offers found.[/yellow]")
            return

        table = Table(title="Stored Offers")
        table.add_column("Product", style="cyan")
        table.add_column("Pharmacy", style="magenta")
        table.add_column("Price", justify="right", style="green")
        table.add_column("Shipping", justify="right", style="blue")

        for offer in offers:
            shipping_cost = f"{offer.pharmacy.base_shipping_cost:.2f} €"
            table.add_row(
                offer.product.name,
                offer.pharmacy.name,
                f"{offer.price:.2f} €",
                shipping_cost,
            )

        console.print(table)


@app.command(name="list-pharmacies")
def list_pharmacies(
    name: Annotated[
        Optional[str], typer.Option(help="Filter by pharmacy name (case-insensitive)")
    ] = None,
):
    """
    List all pharmacies and their shipping policies.
    """
    with database.get_session() as session:
        pharmacies = scraper_service.list_pharmacies(session, name_filter=name)

        if not pharmacies:
            console.print("[yellow]No pharmacies found.[/yellow]")
            return

        table = Table(title="Pharmacy List")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Pharmacy Name", style="green")
        table.add_column("Base Shipping", justify="right", style="blue")
        table.add_column("Free Shipping Threshold", justify="right", style="yellow")

        for pharmacy in pharmacies:
            base_shipping = f"{pharmacy.base_shipping_cost:.2f} €"
            free_shipping = (
                f"{pharmacy.free_shipping_threshold:.2f} €"
                if pharmacy.free_shipping_threshold is not None
                else "N/A"
            )

            table.add_row(
                str(pharmacy.id),
                pharmacy.name,
                base_shipping,
                free_shipping,
            )

        console.print(table)
