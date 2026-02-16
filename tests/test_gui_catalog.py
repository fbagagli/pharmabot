from unittest.mock import patch, MagicMock, call
from pharmabot.gui.pages import catalog
from pharmabot.models import ProductCatalog

def test_catalog_render():
    """Test that catalog page renders correctly."""
    with patch("nicegui.ui.label") as mock_label, \
         patch("nicegui.ui.button") as mock_button, \
         patch("nicegui.ui.table") as mock_table, \
         patch("pharmabot.gui.pages.catalog.refresh_table") as mock_refresh:

        # Setup mocks
        # add_btn = ui.button().classes()
        mock_add_btn = mock_button.return_value.classes.return_value

        catalog.render()

        # Verify elements created
        mock_label.assert_called_with("Product Catalog")
        mock_button.assert_called_with("Add Product")
        mock_table.assert_called_once()

        # Verify button click handler attached
        # Note: on('click', ...) is called on the object returned by .classes()
        assert mock_add_btn.on.call_count == 1
        call_args = mock_add_btn.on.call_args
        assert call_args[0][0] == 'click'

        # table is ui.table().classes()
        mock_table_instance = mock_table.return_value.classes.return_value

        # Verify table slots and events
        mock_table_instance.add_slot.assert_called_once()
        # Verify table events
        assert mock_table_instance.on.call_count >= 2

        mock_refresh.assert_called_once_with(mock_table_instance)

def test_refresh_table():
    """Test table refresh fetches data and updates table."""
    mock_table = MagicMock()
    products = [
        ProductCatalog(id=1, name="P1", minsan="M1"),
        ProductCatalog(id=2, name="P2", minsan=None)
    ]

    with patch("pharmabot.database.get_session") as mock_get_session, \
         patch("pharmabot.services.catalog.list_products", return_value=products) as mock_list:

        # Setup context manager
        session_mock = MagicMock()
        mock_get_session.return_value.__enter__.return_value = session_mock

        catalog.refresh_table(mock_table)

        mock_list.assert_called_once_with(session_mock)

        expected_rows = [
            {"id": 1, "minsan": "M1", "name": "P1"},
            {"id": 2, "minsan": None, "name": "P2"}
        ]
        assert mock_table.rows == expected_rows
        mock_table.update.assert_called_once()

def test_open_add_dialog_save_success():
    """Test opening add dialog and saving successfully."""
    mock_table = MagicMock()

    with patch("nicegui.ui.dialog") as mock_dialog, \
         patch("nicegui.ui.card"), \
         patch("nicegui.ui.label"), \
         patch("nicegui.ui.input") as mock_input, \
         patch("nicegui.ui.button") as mock_button, \
         patch("nicegui.ui.notify") as mock_notify, \
         patch("pharmabot.database.get_session") as mock_get_session, \
         patch("pharmabot.services.catalog.add_product") as mock_add_product, \
         patch("pharmabot.gui.pages.catalog.refresh_table") as mock_refresh:

        # Setup input values
        name_input = MagicMock()
        name_input.value = "New Product"
        # Ensure classes() returns self so .value works on the result
        name_input.classes.return_value = name_input

        minsan_input = MagicMock()
        minsan_input.value = "123"
        minsan_input.classes.return_value = minsan_input

        mock_input.side_effect = [name_input, minsan_input] # First call Name, second Minsan

        # Setup dialog context
        dialog_instance = mock_dialog.return_value.__enter__.return_value

        # Call function
        catalog.open_add_dialog(mock_table)

        # Verify UI setup
        mock_dialog.assert_called()
        mock_input.assert_any_call("Name")
        mock_input.assert_any_call("Minsan")

        # Find the Save button callback
        # ui.button("Save", on_click=save) is called inside
        # We need to extract the 'save' function passed to on_click
        save_callback = None
        for call_args in mock_button.call_args_list:
            if call_args.kwargs.get('on_click') and call_args.args and call_args.args[0] == "Save":
                save_callback = call_args.kwargs['on_click']
                break

        assert save_callback is not None

        # Execute save
        save_callback()

        # Verify service call
        mock_add_product.assert_called_once() # Args check is tricky due to session mock
        mock_notify.assert_called_with("Product 'New Product' added.", type="positive")
        mock_refresh.assert_called_with(mock_table)
        dialog_instance.close.assert_called()

def test_open_edit_dialog_save_success():
    """Test opening edit dialog and saving successfully."""
    mock_table = MagicMock()
    row = {'id': 1, 'name': 'Old Name', 'minsan': 'M1'}

    with patch("nicegui.ui.dialog") as mock_dialog, \
         patch("nicegui.ui.card"), \
         patch("nicegui.ui.label"), \
         patch("nicegui.ui.input") as mock_input, \
         patch("nicegui.ui.button") as mock_button, \
         patch("nicegui.ui.notify") as mock_notify, \
         patch("pharmabot.database.get_session") as mock_get_session, \
         patch("pharmabot.services.catalog.update_product") as mock_update_product, \
         patch("pharmabot.gui.pages.catalog.refresh_table") as mock_refresh:

        name_input = MagicMock()
        name_input.value = "New Name"
        name_input.classes.return_value = name_input
        mock_input.return_value = name_input

        dialog_instance = mock_dialog.return_value.__enter__.return_value

        catalog.open_edit_dialog(mock_table, row)

        mock_input.assert_called_with("Name", value="Old Name")

        save_callback = None
        for call_args in mock_button.call_args_list:
            if call_args.kwargs.get('on_click') and call_args.args and call_args.args[0] == "Save":
                save_callback = call_args.kwargs['on_click']
                break

        assert save_callback is not None
        save_callback()

        mock_update_product.assert_called_once()
        mock_notify.assert_called_with("Product updated.", type="positive")
        mock_refresh.assert_called_with(mock_table)
        dialog_instance.close.assert_called()

def test_open_delete_dialog_confirm_success():
    """Test opening delete dialog and confirming deletion."""
    mock_table = MagicMock()
    row = {'id': 1, 'name': 'To Delete', 'minsan': 'M1'}

    with patch("nicegui.ui.dialog") as mock_dialog, \
         patch("nicegui.ui.card"), \
         patch("nicegui.ui.label"), \
         patch("nicegui.ui.button") as mock_button, \
         patch("nicegui.ui.notify") as mock_notify, \
         patch("pharmabot.database.get_session") as mock_get_session, \
         patch("pharmabot.services.catalog.remove_product") as mock_remove_product, \
         patch("pharmabot.gui.pages.catalog.refresh_table") as mock_refresh:

        dialog_instance = mock_dialog.return_value.__enter__.return_value

        catalog.open_delete_dialog(mock_table, row)

        delete_callback = None
        for call_args in mock_button.call_args_list:
            if call_args.kwargs.get('on_click') and call_args.args and call_args.args[0] == "Delete":
                delete_callback = call_args.kwargs['on_click']
                break

        assert delete_callback is not None
        delete_callback()

        mock_remove_product.assert_called_once()
        mock_notify.assert_called_with("Product deleted.", type="positive")
        mock_refresh.assert_called_with(mock_table)
        dialog_instance.close.assert_called()
