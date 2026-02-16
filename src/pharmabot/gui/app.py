from nicegui import ui
from pharmabot.gui.pages import home, catalog, basket


def create_ui() -> None:
    """Create the main user interface with tabs and content area."""

    # 1. Create the tabs at the top of the interface
    with ui.tabs().classes("w-full bg-blue-100 text-blue-900") as tabs:
        home_tab = ui.tab("Home", icon="home")
        catalog_tab = ui.tab("Catalog", icon="list")
        basket_tab = ui.tab("Basket", icon="shopping_cart")

    # 2. Create the panels that correspond to the tabs
    # The 'value=home_tab' parameter ensures Home is the active page on load
    with ui.tab_panels(tabs, value=home_tab).classes("w-full p-4"):
        # Panel for the Home page
        with ui.tab_panel(home_tab):
            home.render()

        # Panel for the Catalog page
        with ui.tab_panel(catalog_tab):
            catalog.render()

        # Panel for the Basket page
        with ui.tab_panel(basket_tab):
            basket.render()


def run_gui() -> None:
    """Start the native GUI application."""
    # create_ui must be the first parameter of ui.run, otherwise in native mode
    # the routing mechanism will not work
    ui.run(create_ui, native=True, title="Pharmabot", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    run_gui()
