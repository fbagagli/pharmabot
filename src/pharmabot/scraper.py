import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated
from pharmabot.services import scraper as scraper_service
from pharmabot.database import get_session

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
    with get_session() as session:
        scraper_service.scrape_basket(session, headless)
