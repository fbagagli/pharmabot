from nicegui import ui
from pharmabot import database
from pharmabot.services import catalog as catalog_service


def refresh_table(table: ui.table) -> None:
    """Refresh the table data from the database."""
    with database.get_session() as session:
        products = catalog_service.list_products(session)
        table.rows = [
            {"id": p.id, "minsan": p.minsan, "name": p.name} for p in products
        ]
        table.update()


def open_add_dialog(table: ui.table) -> None:
    """Open a dialog to add a new product."""
    with ui.dialog() as dialog, ui.card():
        ui.label("Add Product").classes("text-h6")
        name_input = ui.input("Name").classes("w-full")
        minsan_input = ui.input("Minsan").classes("w-full")

        def save():
            name = name_input.value
            minsan = minsan_input.value or None
            if not name:
                ui.notify("Name is required", type="negative")
                return

            with database.get_session() as session:
                try:
                    catalog_service.add_product(session, name, minsan)
                    ui.notify(f"Product '{name}' added.", type="positive")
                    refresh_table(table)
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=save)
    dialog.open()


def open_edit_dialog(table: ui.table, row: dict) -> None:
    """Open a dialog to edit an existing product."""
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Edit Product {row['id']}").classes("text-h6")
        name_input = ui.input("Name", value=row["name"]).classes("w-full")

        def save():
            new_name = name_input.value
            if not new_name:
                ui.notify("Name is required", type="negative")
                return

            with database.get_session() as session:
                try:
                    catalog_service.update_product(session, row["id"], new_name)
                    ui.notify("Product updated.", type="positive")
                    refresh_table(table)
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=save)
    dialog.open()


def open_delete_dialog(table: ui.table, row: dict) -> None:
    """Open a confirmation dialog to delete a product."""
    with ui.dialog() as dialog, ui.card():
        ui.label("Confirm Delete").classes("text-h6")
        ui.label(f"Are you sure you want to delete '{row['name']}'?")

        def delete():
            with database.get_session() as session:
                try:
                    catalog_service.remove_product(session, row["id"])
                    ui.notify("Product deleted.", type="positive")
                    refresh_table(table)
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Delete", color="red", on_click=delete)
    dialog.open()


def render() -> None:
    """Render the Catalog page."""
    ui.label("Product Catalog").classes("text-h4 q-mb-md")

    # Add Button
    # Note: Pass table to open_add_dialog, but table isn't defined yet.
    # We can define table first, or use a lambda that captures the table variable.
    # Since table needs to be refreshed, we need access to it.

    # Table definition
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
        {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
    ]

    # Create the button first to put it on top, but bind the click later.
    add_btn = ui.button("Add Product").classes("q-mb-md")

    table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")

    # Bind the button action now that table exists
    add_btn.on("click", lambda: open_add_dialog(table))

    # Define slots for Actions column
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
