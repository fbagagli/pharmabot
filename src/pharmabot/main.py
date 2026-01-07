import typer
from rich import print
from pharmabot.database import create_db_and_tables
from pharmabot import catalog
from pharmabot import basket

app = typer.Typer()

app.add_typer(catalog.app, name="catalog", help="Manage product catalog.")
app.add_typer(basket.app, name="basket", help="Manage basket items.")


@app.command()
def init_db():
    """
    Initialize the database.
    """
    create_db_and_tables()
    print("[green]Database initialized successfully[/green]")


if __name__ == "__main__":
    app()
