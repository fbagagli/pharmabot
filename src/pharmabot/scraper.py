import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated
from pharmabot.services import scraper as scraper_service
from pharmabot import database

app = typer.Typer()
console = Console()


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Minsan code or Product Name")],
    headless: Annotated[bool, typer.Option(help="Run in headless mode")] = False,
):
    """
    Search for a product by Minsan code or Product Name.
    """
    offers = scraper_service.scrape_product(query, headless=headless)

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
            str(offer["free_shipping_over"]) if offer["free_shipping_over"] else "-"
        )
        table.add_row(
            str(idx),
            offer["pharmacy"],
            f"{offer['price']:.2f} €",
            f"{offer['shipping_price']:.2f} €",
            free_shipping,
        )

    console.print(table)


@app.command(name="all")
def scrape_all(headless: bool = True):
    """
    Scrape all products in the basket and update the database.
    """
    with database.get_session() as session:
        scraper_service.scrape_basket(session, headless)


@app.command(name="clean")
def scrape_clean():
    """
    Clear all scraped offers and pharmacies from the database.
    """
    with database.get_session() as session:
        scraper_service.clear_database(session)


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
        offers = scraper_service.list_offers(session, product_id, pharmacy_id)

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
