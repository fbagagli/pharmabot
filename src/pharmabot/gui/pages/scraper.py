from nicegui import ui, run
from pharmabot.services import scraper as scraper_service
from pharmabot import database
from rich.console import Console
import asyncio


class NiceGUILogWriter:
    def __init__(self, log_element):
        self.log_element = log_element

    def write(self, text):
        # rich sends ansi codes if terminal is forced, but we want plain text or html?
        # ui.log displays plain text. rich's console(file=...) with force_terminal=False will strip colors.
        # If we want colors, we might need a different approach, but plain text is safer for now.
        if text.strip():
            self.log_element.push(text.strip())

    def flush(self):
        pass


@ui.refreshable
def render():
    if not database.is_connected():
        ui.label("Please connect to a database in the Home tab.").classes(
            "text-lg text-grey-500 q-pa-md"
        )
        return

    # Container for the content
    content = ui.column().classes("w-full h-full")

    def show_main_view():
        content.clear()
        with content:
            ui.label("Scraper Dashboard").classes("text-2xl font-bold mb-4")

            with ui.row().classes("w-full items-center gap-4"):
                query_input = ui.input("Product Name or Minsan").classes("w-64")
                headless_checkbox = ui.checkbox("Headless", value=False)

                async def run_search():
                    query = query_input.value
                    if not query:
                        ui.notify("Please enter a query", type="warning")
                        return

                    log.clear()
                    ui.notify(f"Searching for {query}...", type="info")

                    # Setup Log Capture
                    log_writer = NiceGUILogWriter(log)
                    # force_terminal=False ensures plain text output for ui.log
                    temp_console = Console(file=log_writer, force_terminal=False)
                    original_console = scraper_service.console
                    scraper_service.console = temp_console

                    try:
                        # Run in executor to avoid blocking the event loop
                        offers = await run.io_bound(
                            scraper_service.scrape_product,
                            query=query,
                            headless=headless_checkbox.value,
                            wait_for_input=False
                        )

                        if offers:
                            ui.notify(f"Found {len(offers)} offers!", type="positive")
                            # Display results immediately
                            with results_container:
                                results_container.clear()
                                ui.label(f"Results for '{query}':").classes("text-lg font-bold mt-4")
                                table = ui.table(
                                    columns=[
                                        {'name': 'pharmacy', 'label': 'Pharmacy', 'field': 'pharmacy'},
                                        {'name': 'price', 'label': 'Price', 'field': 'price'},
                                        {'name': 'shipping', 'label': 'Shipping', 'field': 'shipping_price'},
                                        {'name': 'free_over', 'label': 'Free Shipping Over', 'field': 'free_shipping_over'},
                                    ],
                                    rows=offers,
                                ).classes("w-full")
                        else:
                            ui.notify("No offers found.", type="warning")
                            results_container.clear()

                    except Exception as e:
                        ui.notify(f"Error: {str(e)}", type="negative")
                        log.push(f"Error: {str(e)}")
                    finally:
                        scraper_service.console = original_console

                ui.button("Search", on_click=run_search).props("icon=search")

                async def run_scrape_basket():
                    log.clear()
                    results_container.clear()
                    ui.notify("Starting basket scrape...", type="info")

                    log_writer = NiceGUILogWriter(log)
                    temp_console = Console(file=log_writer, force_terminal=False)
                    original_console = scraper_service.console
                    scraper_service.console = temp_console

                    try:
                        # We need to wrap the session usage in the thread carefully.
                        # Since session is not thread-safe, we should create it inside the thread or pass it carefully.
                        # scrape_basket takes a session.
                        # run.io_bound runs in a thread pool.
                        # We should probably define a wrapper function that creates the session.

                        def _scrape_task(headless_val):
                            with database.get_session() as session:
                                scraper_service.scrape_basket(
                                    session,
                                    headless=headless_val,
                                    wait_for_input=False
                                )

                        await run.io_bound(_scrape_task, headless_checkbox.value)

                        ui.notify("Basket scraping complete!", type="positive")
                    except Exception as e:
                        ui.notify(f"Error: {str(e)}", type="negative")
                        log.push(f"Error: {str(e)}")
                    finally:
                        scraper_service.console = original_console

                ui.button("Scrape Basket", on_click=run_scrape_basket).props("icon=shopping_cart")

                async def run_clean_db():
                    log.clear()
                    results_container.clear()
                    ui.notify("Clearing database...", type="info")

                    log_writer = NiceGUILogWriter(log)
                    temp_console = Console(file=log_writer, force_terminal=False)
                    original_console = scraper_service.console
                    scraper_service.console = temp_console

                    try:
                        def _clean_task():
                            with database.get_session() as session:
                                scraper_service.clear_database(session)

                        await run.io_bound(_clean_task)
                        ui.notify("Database cleared!", type="positive")
                    except Exception as e:
                        ui.notify(f"Error: {str(e)}", type="negative")
                        log.push(f"Error: {str(e)}")
                    finally:
                        scraper_service.console = original_console

                ui.button("Cleanup", on_click=run_clean_db).props("icon=delete_sweep color=red")

            # Logs
            ui.label("Logs").classes("text-lg font-bold mt-4")
            log = ui.log().classes("w-full h-64 border rounded bg-gray-100 p-2 font-mono text-xs").style("white-space: pre-wrap;")

            # Results container for immediate search results
            results_container = ui.column().classes("w-full")

            # Navigation to Log Views
            ui.separator().classes("my-4")
            with ui.row().classes("gap-4"):
                ui.button("View Offers Log", on_click=show_offers_view).props("outline icon=list")
                ui.button("View Pharmacies Log", on_click=show_pharmacies_view).props("outline icon=local_pharmacy")

    def show_offers_view():
        content.clear()
        with content:
            with ui.row().classes("items-center mb-4"):
                ui.button("Back", on_click=show_main_view).props("icon=arrow_back flat")
                ui.label("Scraped Offers Log").classes("text-2xl font-bold")

            with database.get_session() as session:
                offers = scraper_service.list_offers(session)

                rows = []
                for offer in offers:
                    rows.append({
                        'product': offer.product.name,
                        'pharmacy': offer.pharmacy.name,
                        'price': f"{offer.price:.2f} €",
                        'shipping': f"{offer.pharmacy.base_shipping_cost:.2f} €"
                    })

                ui.table(
                    columns=[
                        {'name': 'product', 'label': 'Product', 'field': 'product', 'sortable': True},
                        {'name': 'pharmacy', 'label': 'Pharmacy', 'field': 'pharmacy', 'sortable': True},
                        {'name': 'price', 'label': 'Price', 'field': 'price', 'sortable': True},
                        {'name': 'shipping', 'label': 'Shipping', 'field': 'shipping', 'sortable': True},
                    ],
                    rows=rows,
                    pagination=10
                ).classes("w-full")

    def show_pharmacies_view():
        content.clear()
        with content:
            with ui.row().classes("items-center mb-4"):
                ui.button("Back", on_click=show_main_view).props("icon=arrow_back flat")
                ui.label("Scraped Pharmacies Log").classes("text-2xl font-bold")

            with database.get_session() as session:
                pharmacies = scraper_service.list_pharmacies(session)

                rows = []
                for p in pharmacies:
                    free_ship = f"{p.free_shipping_threshold:.2f} €" if p.free_shipping_threshold is not None else "N/A"
                    rows.append({
                        'id': p.id,
                        'name': p.name,
                        'base_shipping': f"{p.base_shipping_cost:.2f} €",
                        'free_shipping': free_ship
                    })

                ui.table(
                    columns=[
                        {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True},
                        {'name': 'name', 'label': 'Name', 'field': 'name', 'sortable': True},
                        {'name': 'base_shipping', 'label': 'Base Shipping', 'field': 'base_shipping', 'sortable': True},
                        {'name': 'free_shipping', 'label': 'Free Shipping Threshold', 'field': 'free_shipping', 'sortable': True},
                    ],
                    rows=rows,
                    pagination=10
                ).classes("w-full")

    # Initialize Main View
    show_main_view()
