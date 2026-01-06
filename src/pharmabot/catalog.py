import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from pharmabot import database
from pharmabot.services import catalog as catalog_service

app = typer.Typer()
console = Console()


@app.command()
def add(
    minsan: str,
    name: Annotated[str, typer.Option("--name", help="Name of the product")],
):
    """
    Add a new product to the catalog.
    """
    with database.get_session() as session:
        try:
            catalog_service.add_product(session, minsan, name)
            console.print(f"[green]Product {minsan} added successfully.[/green]")
        except catalog_service.ProductAlreadyExistsError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def remove(minsan: str):
    """
    Remove a product from the catalog.
    """
    with database.get_session() as session:
        try:
            catalog_service.remove_product(session, minsan)
            console.print(f"[green]Product {minsan} removed successfully.[/green]")
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
            table.add_row(str(product.id), product.minsan, product.name)

        console.print(table)


@app.command()
def update(
    minsan: str,
    name: Annotated[str, typer.Option("--name", help="New name of the product")],
):
    """
    Update a product's name in the catalog.
    """
    with database.get_session() as session:
        try:
            catalog_service.update_product(session, minsan, name)
            console.print(f"[green]Product {minsan} updated successfully.[/green]")
        except catalog_service.ProductNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)
