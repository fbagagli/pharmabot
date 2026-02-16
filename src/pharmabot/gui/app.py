from nicegui import ui
from pharmabot.gui.pages import home, catalog

def render_sidebar(content_container):
    """Render the sidebar navigation."""
    with ui.left_drawer(value=True).classes("bg-blue-100") as drawer:
        ui.label("Pharmabot Menu").classes("text-h6 q-mb-md")
        ui.separator()

        with ui.column().classes("w-full"):
            ui.button("Home", on_click=lambda: navigate(content_container, home.render)).classes("w-full")
            ui.button("Catalog", on_click=lambda: navigate(content_container, catalog.render)).classes("w-full")

def navigate(container, render_func):
    """Clear the container and render the new page."""
    container.clear()
    with container:
        render_func()

def create_ui() -> None:
    """Create the main user interface with sidebar and content area."""
    # Main content container
    content_container = ui.column().classes("w-full p-4")

    # Render Sidebar passing the container to update
    render_sidebar(content_container)

    # Render initial page (Home)
    navigate(content_container, home.render)

def run_gui() -> None:
    """Start the native GUI application."""
    # We call create_ui inside ui.run context usually, or pass it as the target.
    # But nicegui.ui.run takes a function or just runs existing UI definitions.
    # Best practice for nicegui structure is to define UI, then run.
    create_ui()
    ui.run(native=True, title="Pharmabot", reload=False)

if __name__ in {"__main__", "__mp_main__"}:
    run_gui()
