from typing import Callable, Optional
from nicegui import ui
from pharmabot import database


def render(on_connect: Optional[Callable] = None) -> None:
    """Render the Home page."""
    with ui.card().classes("w-full"):
        ui.label("Database Connection").classes("text-h6")

        # Default path
        db_path_input = ui.input("Database Path", value="pharmabot.db").classes(
            "w-full"
        )

        def connect():
            path = db_path_input.value
            if not path:
                ui.notify("Please enter a database path", type="negative")
                return

            try:
                # Initialize/Connect
                database.init_db(path)
                ui.notify(f"Connected to database: {path}", type="positive")

                # Refresh UI
                if on_connect:
                    on_connect()

            except Exception as e:
                ui.notify(f"Error connecting to database: {e}", type="negative")

        with ui.row().classes("w-full gap-4"):
            ui.button("Connect / Create", on_click=connect).props("icon=check").classes(
                "w-full"
            )
