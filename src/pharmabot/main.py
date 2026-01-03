import typer
from rich import print
from pharmabot.database import create_db_and_tables

app = typer.Typer()


@app.command()
def init_db():
    """
    Initialize the database.
    """
    create_db_and_tables()
    print("[green]Database initialized successfully[/green]")


if __name__ == "__main__":
    app()
