from nicegui import ui
from pharmabot import database
from pharmabot.services import basket as basket_service
from pharmabot.services import catalog as catalog_service


def refresh_table(table: ui.table) -> None:
    """Refresh the table data from the database."""
    with database.get_session() as session:
        items = basket_service.list_basket_items(session)
        # We need to access item.product inside the session to ensure it's loaded
        table.rows = [
            {
                "id": item.product.id,
                "name": item.product.name,
                "minsan": item.product.minsan,
                "quantity": item.quantity,
            }
            for item in items
        ]
        table.update()


def open_add_dialog(table: ui.table) -> None:
    """Open a dialog to add a product to the basket."""
    # Fetch available products for the selector
    with database.get_session() as session:
        products = catalog_service.list_products(session)
        product_options = {p.id: p.name for p in products}

    with ui.dialog() as dialog, ui.card():
        ui.label("Add to Basket").classes("text-h6")

        product_select = ui.select(
            product_options, label="Product", with_input=True
        ).classes("w-full")

        quantity_input = ui.number(
            "Quantity", value=1, min=1, precision=0
        ).classes("w-full")

        def save():
            product_id = product_select.value
            quantity = int(quantity_input.value or 0)

            if not product_id:
                ui.notify("Please select a product", type="negative")
                return
            if quantity <= 0:
                ui.notify("Quantity must be positive", type="negative")
                return

            with database.get_session() as session:
                try:
                    basket_service.add_item_to_basket(session, product_id, quantity)
                    ui.notify("Item added to basket.", type="positive")
                    refresh_table(table)
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Add", on_click=save)
    dialog.open()


def open_edit_dialog(table: ui.table, row: dict) -> None:
    """Open a dialog to update the quantity of a basket item."""
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Edit Quantity: {row['name']}").classes("text-h6")
        quantity_input = ui.number(
            "Quantity", value=row["quantity"], min=1, precision=0
        ).classes("w-full")

        def save():
            quantity = int(quantity_input.value or 0)
            if quantity <= 0:
                ui.notify("Quantity must be positive", type="negative")
                return

            with database.get_session() as session:
                try:
                    basket_service.update_basket_item_quantity(
                        session, row["id"], quantity
                    )
                    ui.notify("Quantity updated.", type="positive")
                    refresh_table(table)
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=save)
    dialog.open()


def open_delete_dialog(table: ui.table, row: dict) -> None:
    """Open a confirmation dialog to remove an item from the basket."""
    with ui.dialog() as dialog, ui.card():
        ui.label("Confirm Remove").classes("text-h6")
        ui.label(f"Are you sure you want to remove '{row['name']}' from the basket?")

        def delete():
            with database.get_session() as session:
                try:
                    basket_service.remove_item_from_basket(session, row["id"])
                    ui.notify("Item removed from basket.", type="positive")
                    refresh_table(table)
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Remove", color="red", on_click=delete)
    dialog.open()


def render() -> None:
    """Render the Basket page."""
    ui.label("Basket").classes("text-h4 q-mb-md")

    columns = [
        {"name": "id", "label": "ID", "field": "id", "align": "left", "sortable": True},
        {
            "name": "minsan",
            "label": "Minsan",
            "field": "minsan",
            "align": "left",
            "sortable": True,
        },
        {
            "name": "name",
            "label": "Name",
            "field": "name",
            "align": "left",
            "sortable": True,
        },
        {
            "name": "quantity",
            "label": "Quantity",
            "field": "quantity",
            "align": "center",
            "sortable": True,
        },
        {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
    ]

    add_btn = ui.button("Add Item").classes("q-mb-md")

    table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")

    add_btn.on("click", lambda: open_add_dialog(table))

    table.add_slot(
        "body-cell-actions",
        r"""
        <q-td key="actions" :props="props">
            <q-btn icon="edit" flat round dense color="primary" @click="$parent.$emit('edit', props.row)" />
            <q-btn icon="delete" flat round dense color="negative" @click="$parent.$emit('delete', props.row)" />
        </q-td>
    """,
    )

    table.on("edit", lambda e: open_edit_dialog(table, e.args))
    table.on("delete", lambda e: open_delete_dialog(table, e.args))

    refresh_table(table)
