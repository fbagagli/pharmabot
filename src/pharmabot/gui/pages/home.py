from nicegui import ui
from pharmabot.database import create_db_and_tables

def init_db_action() -> None:
    """Initialize the database and notify the user."""
    try:
        create_db_and_tables()
        ui.notify("Database initialized successfully", type="positive")
    except Exception as e:
        ui.notify(f"Error initializing database: {e}", type="negative")

def render() -> None:
    """Render the Home page."""
    with ui.card().classes("absolute-center"):
        ui.label("Pharmabot").classes("text-h4 text-center w-full")
        ui.button("Initialize Database", on_click=init_db_action).classes("w-full")
