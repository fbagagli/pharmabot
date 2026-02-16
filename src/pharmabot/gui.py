import asyncio
from typing import Optional

from nicegui import ui


class Database:
    _instance: Optional["Database"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    async def initialize_db(self) -> None:
        """
        Simulates an asynchronous database initialization task.
        """
        # Simulate async work
        await asyncio.sleep(1)
        # In a real scenario, this would interact with the database logic
        print("Database initialized successfully (simulated).")


def create_layout():
    # Basic App Structure
    with ui.header(elevated=True).classes("bg-primary text-white"):
        ui.label("Pharmabot").classes("text-h6")

    with ui.column().classes("w-full items-center justify-center gap-4 p-8"):
        ui.label("Database Management").classes("text-2xl font-bold")

        # Instantiate the singleton
        db = Database()

        async def on_init_click():
            # Use ui.notification to have a dismissible notification
            notification = ui.notification(
                "Initializing database...", type="info", timeout=None
            )
            await db.initialize_db()
            notification.dismiss()
            ui.notify("Database initialized successfully!", type="positive")

        # GUI Interaction
        ui.button("Initialize Database", on_click=on_init_click).props("icon=storage")


def main():
    create_layout()
    # Run as a native desktop window
    ui.run(native=True, reload=False, title="Pharmabot")


if __name__ in {"__main__", "__mp_main__"}:
    main()
