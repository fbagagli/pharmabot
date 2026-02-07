import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated
from typing import Optional

from pharmabot import database
from pharmabot.services import catalog as catalog_service

app = typer.Typer()
console = Console()


@app.command()
def add(
    name: Annotated[str, typer.Option("--name", help="Name of the product")],
    minsan: Annotated[
        Optional[str], typer.Option("--minsan", help="Minsan code of the product")
    ] = None,
):
    """
    Add a new product to the catalog.
    """
    with database.get_session() as session:
        try:
            product = catalog_service.add_product(session, name, minsan)
            console.print(
                f"[green]Product '{name}' added successfully (ID: {product.id}).[/green]"
            )
        except catalog_service.ProductAlreadyExistsError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def remove(
    product_id: Annotated[int, typer.Argument(help="ID of the product to remove")],
):
    """
    Remove a product from the catalog.
    """
    with database.get_session() as session:
        try:
            catalog_service.remove_product(session, product_id)
            console.print(f"[green]Product {product_id} removed successfully.[/green]")
        except catalog_service.ProductNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command(name="list")
def list_products():
    """
    List all products in the catalog.
    """
    with database.get_session() as session:
        products = catalog_service.list_products(session)

        table = Table(title="Product Catalog")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Minsan", style="magenta")
        table.add_column("Name", style="green")

        if not products:
            console.print(table)
            return

        for product in products:
            minsan_str = product.minsan if product.minsan else "N/A"
            table.add_row(str(product.id), minsan_str, product.name)

        console.print(table)


@app.command()
def update(
    product_id: Annotated[int, typer.Argument(help="ID of the product to update")],
    name: Annotated[str, typer.Option("--name", help="New name of the product")],
):
    """
    Update a product's name in the catalog.
    """
    with database.get_session() as session:
        try:
            catalog_service.update_product(session, product_id, name)
            console.print(f"[green]Product {product_id} updated successfully.[/green]")
        except catalog_service.ProductNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)
