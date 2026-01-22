import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from pharmabot import database
from pharmabot.services import basket as basket_service

app = typer.Typer()
console = Console()


@app.command()
def add(
    product_id: Annotated[int, typer.Argument(help="ID of the product to add")],
    quantity: Annotated[int, typer.Option(help="Quantity to add")] = 1,
):
    """
    Add a product to the basket.
    """
    with database.get_session() as session:
        try:
            basket_service.add_item_to_basket(session, product_id, quantity)
            console.print(
                f"[green]Product {product_id} added to basket (quantity added: {quantity}).[/green]"
            )
        except basket_service.ProductNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def update(
    product_id: Annotated[int, typer.Argument(help="ID of the product to update")],
    quantity: Annotated[int, typer.Option(help="New quantity for the product")],
):
    """
    Update the quantity of a product in the basket.
    """
    with database.get_session() as session:
        try:
            basket_service.update_basket_item_quantity(session, product_id, quantity)
            console.print(
                f"[green]Product {product_id} quantity updated to {quantity}.[/green]"
            )
        except basket_service.ItemNotPresentError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def remove(
    product_id: Annotated[int, typer.Argument(help="ID of the product to remove")],
):
    """
    Remove a product from the basket.
    """
    with database.get_session() as session:
        try:
            basket_service.remove_item_from_basket(session, product_id)
            console.print(f"[green]Product {product_id} removed from basket.[/green]")
        except basket_service.ItemNotPresentError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command(name="list")
def list_items():
    """
    List all items in the basket.
    """
    with database.get_session() as session:
        items = basket_service.list_basket_items(session)

        table = Table(title="Basket")
        table.add_column("Minsan", style="magenta")
        table.add_column("Quantity", justify="right", style="cyan")
        table.add_column("Name", style="green")

        if not items:
            console.print("No items in basket.")
            return

        for item in items:
            # BasketItem has a relationship to ProductCatalog named 'product'
            # We assume it is eagerly loaded or lazily loaded. Since we are in a session context, lazy load should work.
            table.add_row(item.product.minsan, str(item.quantity), item.product.name)

        console.print(table)


@app.command(name="optimize")
def optimize_basket(limit: int = 3):
    with database.get_session() as session:
        winners = basket_service.optimize_basket(session, limit)

        if not winners:
            console.print("No single pharmacy has all the items in stock.")
            return

        table = Table(title="Optimization Results")
        table.add_column("Pharmacy Name", style="green")
        table.add_column("Items Price", justify="right")
        table.add_column("Actual Shipping", justify="right")
        table.add_column("Total Price", justify="right", style="bold")
        table.add_column("Base Shipping", justify="right")
        table.add_column("Free Shipping Threshold", justify="right")

        for opt in winners:
            items_cost = f"€ {opt.items_cost:.2f}"
            actual_shipping = f"€ {opt.shipping_cost:.2f}"
            total_cost = f"€ {opt.total_cost:.2f}"

            base_shipping = f"€ {opt.pharmacy.base_shipping_cost:.2f}"

            threshold = opt.pharmacy.free_shipping_threshold
            threshold_str = f"€ {threshold:.2f}" if threshold is not None else "N/A"

            table.add_row(
                opt.pharmacy.name,
                items_cost,
                actual_shipping,
                total_cost,
                base_shipping,
                threshold_str,
            )

        console.print(table)
