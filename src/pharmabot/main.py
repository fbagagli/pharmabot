import typer
from rich import print
from typing import Optional
from typing_extensions import Annotated
from pharmabot.database import create_db_and_tables, get_session
from pharmabot.models import Product

app = typer.Typer()


@app.command()
def init_db():
    """
    Initialize the database.
    """
    create_db_and_tables()
    print("[green]Database initialized successfully[/green]")


@app.command()
def add_product(
    minsan: str,
    name: Annotated[Optional[str], typer.Option()] = None,
    quantity: Annotated[Optional[int], typer.Option()] = None,
):
    """
    Add a new product or update an existing one.
    """
    if quantity is not None and quantity <= 0:
        print("[red]Quantity must be a positive integer.[/red]")
        raise typer.Exit(code=1)

    with get_session() as session:
        product = session.get(Product, minsan)

        if product:
            # Update existing product
            if name:
                product.name = name
            if quantity:
                product.quantity += quantity
            session.add(product)
            session.commit()
            print(
                f"[green]Updated product: {product.name} (Minsan: {product.minsan}, Quantity: {product.quantity})[/green]"
            )
        else:
            # Create new product
            if not name:
                print("[red]Name is required for new products.[/red]")
                raise typer.Exit(code=1)

            new_quantity = quantity if quantity is not None else 1
            new_product = Product(minsan=minsan, name=name, quantity=new_quantity)
            session.add(new_product)
            session.commit()
            print(
                f"[green]Added product: {new_product.name} (Minsan: {new_product.minsan}, Quantity: {new_product.quantity})[/green]"
            )


if __name__ == "__main__":
    app()
