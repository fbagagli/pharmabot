import logging
from typing import List

from nicegui import run, ui
from pharmabot import database
from pharmabot.services import basket as basket_service
from pharmabot.services.price_optimizer import Solution

# Configure logger
logger = logging.getLogger(__name__)


def format_solution_text(solutions: List[Solution]) -> str:
    """Formats the solutions into a string for saving."""
    output = []

    # Group by order count
    grouped = {}
    for sol in solutions:
        k = sol.order_count
        if k not in grouped:
            grouped[k] = []
        grouped[k].append(sol)

    for k in sorted(grouped.keys()):
        output.append(f"--- Solutions with {k} Order{'s' if k > 1 else ''} ---\n")

        for idx, sol in enumerate(grouped[k], 1):
            output.append(f"Option {idx} (Total: € {sol.total_cost:.2f})")
            for order in sol.orders:
                output.append(f"  Pharmacy: {order.pharmacy.name}")
                output.append(f"  Items Cost: € {order.items_cost:.2f}")
                output.append(f"  Shipping: € {order.shipping_cost:.2f}")
                if order.pharmacy.free_shipping_threshold:
                    output.append(f"  (Free shipping threshold: € {order.pharmacy.free_shipping_threshold:.2f})")
                output.append("  Items:")
                for match in order.items:
                    # We might need product name here.
                    # The Match object has product_id. We rely on the fact that we can't easily fetch names here
                    # without a session unless they are in the match or we pass a map.
                    # The PriceOptimizer.from_session does not seem to attach names to matches directly?
                    # Actually, we can fetch product names before optimization or assume we can't show them in text file easily
                    # without re-fetching.
                    # But wait, the GUI has them. We'll improve this later if needed.
                    output.append(f"    - ID {match.product_id}: x{match.quantity_needed} @ € {match.price:.2f}")
            output.append("") # Empty line between options
        output.append("")

    return "\n".join(output)


def save_results(solutions: List[Solution]) -> None:
    """Downloads the optimization results as a text file."""
    if not solutions:
        ui.notify("No results to save.", type="warning")
        return

    text_content = format_solution_text(solutions)
    ui.download(text_content.encode("utf-8"), "optimization_results.txt")


@ui.refreshable
def render() -> None:
    """Render the Optimization page."""
    if not database.is_connected():
        ui.label("Please connect to a database in the Home tab.").classes(
            "text-lg text-grey-500 q-pa-md"
        )
        return

    # State to hold the latest solutions
    current_solutions: List[Solution] = []

    ui.label("Basket Optimization").classes("text-h4 q-mb-md")

    # --- Configuration Section ---
    with ui.row().classes("w-full items-center gap-4 q-mb-md"):
        max_orders_input = ui.number(
            "Max Orders", value=1, min=1, precision=0
        ).classes("w-32")

        limit_input = ui.input(
            "Limit", value="3", placeholder="e.g. 3 or 5,2"
        ).props('hint="Top N results per order count"').classes("w-48")

        # Tooltip for Limit
        with limit_input:
             ui.tooltip("Comma-separated limits for each order count (e.g., '5,2' means top 5 for 1-order, top 2 for 2-orders).")

        optimize_btn = ui.button("Optimize", icon="rocket")
        save_btn = ui.button(
            "Save Results",
            icon="save",
            color="secondary",
            on_click=lambda: save_results(current_solutions),
        ).props("disabled")

    # --- Results Section ---
    results_container = ui.column().classes("w-full q-mt-md")

    async def run_optimization():
        nonlocal current_solutions
        results_container.clear()
        save_btn.disable()

        # Read inputs
        try:
            max_orders = int(max_orders_input.value or 1)
        except ValueError:
            max_orders = 1

        limit_str = limit_input.value or "3"

        # Define task wrapper
        def _task():
            with database.get_session() as session:
                return basket_service.optimize_basket(session, limit=limit_str, max_orders=max_orders)

        # Run optimization
        with results_container:
            ui.spinner("dots", size="lg").classes("self-center")

        try:
            # Run in thread pool to avoid blocking UI
            solutions = await run.io_bound(_task)
        except Exception as e:
            results_container.clear()
            ui.notify(f"Optimization failed: {e}", type="negative")
            logger.exception("Optimization error")
            return

        results_container.clear()

        if not solutions:
            with results_container:
                ui.label("No solutions found matching the criteria.").classes("text-italic text-grey")
            current_solutions = []
            save_btn.disable()
            return

        # Update state and enable save button
        current_solutions = solutions
        save_btn.enable()

        # Pre-fetch product names for display (optimization: do this once)
        # We need a session for this, or use a cached map.
        # Since solutions don't have product names, we fetch all products in basket.
        product_names = {}
        with database.get_session() as session:
            items = basket_service.list_basket_items(session)
            for item in items:
                product_names[item.product_id] = item.product.name

        # Display Results
        display_results(results_container, solutions, product_names)

    optimize_btn.on("click", run_optimization)


def display_results(container: ui.column, solutions: List[Solution], product_names: dict):
    """Helper to render the solutions in the container."""

    # Group by order count
    grouped = {}
    for sol in solutions:
        k = sol.order_count
        if k not in grouped:
            grouped[k] = []
        grouped[k].append(sol)

    with container:
        for k in sorted(grouped.keys()):
            with ui.expansion(f"Solutions with {k} Order{'s' if k > 1 else ''}", icon="shopping_bag").classes("w-full bg-grey-200").props("default-opened"):

                # If k=1, show a simple table
                if k == 1:
                    render_single_order_table(grouped[k], product_names)
                else:
                    # For k > 1, show detailed cards
                    render_multi_order_cards(grouped[k], product_names)


def render_single_order_table(solutions: List[Solution], product_names: dict):
    columns = [
        {"name": "pharmacy", "label": "Pharmacy", "field": "pharmacy", "align": "left"},
        {"name": "items_cost", "label": "Items Cost", "field": "items_cost", "align": "right"},
        {"name": "shipping", "label": "Shipping", "field": "shipping", "align": "right"},
        {"name": "total", "label": "Total", "field": "total", "align": "right", "sortable": True},
        {"name": "details", "label": "Details", "field": "details", "align": "left"},
    ]

    rows = []
    for sol in solutions:
        order = sol.orders[0]
        threshold = order.pharmacy.free_shipping_threshold
        t_str = f"Free > €{threshold:.2f}" if threshold is not None else "No free ship"

        rows.append({
            "pharmacy": order.pharmacy.name,
            "items_cost": f"€ {order.items_cost:.2f}",
            "shipping": f"€ {order.shipping_cost:.2f}",
            "total": sol.total_cost, # Keep as number for sorting? Or format string.
            "total_fmt": f"€ {sol.total_cost:.2f}", # for display
            "details": f"Base: €{order.pharmacy.base_shipping_cost:.2f}, {t_str}"
        })

    # Custom slot for Total to show formatted value
    table = ui.table(columns=columns, rows=rows, pagination=10).classes("w-full")
    table.add_slot("body-cell-total", r'''
        <q-td key="total" :props="props">
            {{ props.row.total_fmt }}
        </q-td>
    ''')


def render_multi_order_cards(solutions: List[Solution], product_names: dict):
    for idx, sol in enumerate(solutions, 1):
        with ui.card().classes("w-full q-mb-sm"):
            with ui.row().classes("w-full items-center justify-between bg-blue-50 p-2"):
                ui.label(f"Option {idx}").classes("text-bold")
                ui.label(f"Total: € {sol.total_cost:.2f}").classes("text-h6 text-primary")

            # Show breakdown per pharmacy
            with ui.row().classes("w-full q-pa-sm"):
                for order in sol.orders:
                    with ui.column().classes("col p-2 border rounded m-1"):
                        ui.label(order.pharmacy.name).classes("text-bold text-lg")

                        # Costs
                        ui.label(f"Items: € {order.items_cost:.2f}").classes("text-sm")
                        ui.label(f"Shipping: € {order.shipping_cost:.2f}").classes("text-sm")
                        ui.label(f"Subtotal: € {order.total_cost:.2f}").classes("text-bold")

                        ui.separator().classes("my-2")

                        # Items list
                        with ui.scroll_area().classes("h-32 w-full"):
                            for match in order.items:
                                p_name = product_names.get(match.product_id, f"Product {match.product_id}")
                                ui.label(f"{p_name} (x{match.quantity_needed})").classes("text-xs")
                                ui.label(f"€ {match.price:.2f} ea").classes("text-xs text-grey")
