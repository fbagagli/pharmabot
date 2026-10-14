import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from pharmabot import database
from pharmabot.services import basket as basket_service

app = typer.Typer()
console = Console()


@app.command()
def add(
    product_id: Annotated[int, typer.Argument(help="ID of the product to add")],
    quantity: Annotated[int, typer.Option(help="Quantity to add")] = 1,
):
    """
    Add a product to the basket.
    """
    with database.get_session() as session:
        try:
            basket_service.add_item_to_basket(session, product_id, quantity)
            console.print(
                f"[green]Product {product_id} added to basket (quantity added: {quantity}).[/green]"
            )
        except basket_service.ProductNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def update(
    product_id: Annotated[int, typer.Argument(help="ID of the product to update")],
    quantity: Annotated[int, typer.Option(help="New quantity for the product")],
):
    """
    Update the quantity of a product in the basket.
    """
    with database.get_session() as session:
        try:
            basket_service.update_basket_item_quantity(session, product_id, quantity)
            console.print(
                f"[green]Product {product_id} quantity updated to {quantity}.[/green]"
            )
        except basket_service.ItemNotPresentError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def remove(
    product_id: Annotated[int, typer.Argument(help="ID of the product to remove")],
):
    """
    Remove a product from the basket.
    """
    with database.get_session() as session:
        try:
            basket_service.remove_item_from_basket(session, product_id)
            console.print(f"[green]Product {product_id} removed from basket.[/green]")
        except basket_service.ItemNotPresentError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command(name="list")
def list_items():
    """
    List all items in the basket.
    """
    with database.get_session() as session:
        items = basket_service.list_basket_items(session)

        table = Table(title="Basket")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Minsan", style="magenta")
        table.add_column("Quantity", justify="right", style="cyan")
        table.add_column("Name", style="green")

        if not items:
            console.print("No items in basket.")
            return

        for item in items:
            # BasketItem has a relationship to ProductCatalog named 'product'
            # We assume it is eagerly loaded or lazily loaded. Since we are in a session context, lazy load should work.
            minsan_str = item.product.minsan if item.product.minsan else "N/A"
            table.add_row(
                str(item.product.id), minsan_str, str(item.quantity), item.product.name
            )

        console.print(table)


@app.command(name="optimize")
def optimize_basket(
    limit: Annotated[
        str, typer.Option(help="Limit results per order count (e.g. '3' or '5,2,1')")
    ] = "3",
    max_orders: Annotated[
        int, typer.Option(help="Maximum number of pharmacies to use")
    ] = 1,
):
    """
    Optimize basket by finding the best combination of pharmacies to minimize total cost.
    """
    with database.get_session() as session:
        # Pre-fetch product names for display
        basket_items = basket_service.list_basket_items(session)
        if not basket_items:
            console.print("Basket is empty.")
            return

        product_names = {item.product_id: item.product.name for item in basket_items}

        with console.status("Optimizing basket...", spinner="dots"):
            winners = basket_service.optimize_basket(
                session, limit=limit, max_orders=max_orders
            )

        if not winners:
            console.print("No solutions found that cover all items.")
            return

        # Group by order count
        grouped = {}
        for sol in winners:
            k = sol.order_count
            if k not in grouped:
                grouped[k] = []
            grouped[k].append(sol)

        for k in sorted(grouped.keys()):
            console.print(
                f"\n[bold cyan]Solutions with {k} Order{'s' if k > 1 else ''}[/bold cyan]"
            )
            solutions = grouped[k]

            if k == 1:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Pharmacy", style="green")
                table.add_column("Items Price", justify="right")
                table.add_column("Shipping", justify="right")
                table.add_column("Total Price", justify="right", style="bold")
                table.add_column("Details", style="dim")

                for sol in solutions:
                    order = sol.orders[0]
                    items_cost = f"€ {order.items_cost:.2f}"
                    actual_shipping = f"€ {order.shipping_cost:.2f}"
                    total_cost = f"€ {sol.total_cost:.2f}"

                    threshold = order.pharmacy.free_shipping_threshold
                    t_str = (
                        f"Free > €{threshold:.2f}"
                        if threshold is not None
                        else "No free ship"
                    )
                    base_s = f"Base: €{order.pharmacy.base_shipping_cost:.2f}"
                    details = f"{base_s}, {t_str}"

                    table.add_row(
                        order.pharmacy.name,
                        items_cost,
                        actual_shipping,
                        total_cost,
                        details,
                    )
                console.print(table)
            else:
                for idx, sol in enumerate(solutions, 1):
                    console.print(
                        f"\n[bold]Option {idx} (Total: € {sol.total_cost:.2f})[/bold]"
                    )
                    t = Table(show_header=True, header_style="yellow")
                    t.add_column("Pharmacy", style="green")
                    t.add_column("Items", style="white")
                    t.add_column("Subtotal", justify="right")
                    t.add_column("Shipping", justify="right")
                    t.add_column("Total", justify="right")

                    for order in sol.orders:
                        # Build item list string
                        item_list = []
                        for m in order.items:
                            p_name = product_names.get(
                                m.product_id, f"ID:{m.product_id}"
                            )
                            item_list.append(f"{p_name} (x{m.quantity_needed})")

                        items_str = "\n".join(item_list)

                        t.add_row(
                            order.pharmacy.name,
                            items_str,
                            f"€ {order.items_cost:.2f}",
                            f"€ {order.shipping_cost:.2f}",
                            f"€ {order.total_cost:.2f}",
                        )
                    console.print(t)
