from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from pharmabot.main import app
import pharmabot.gui
from pharmabot.gui import app as gui_app
from pharmabot.gui.pages import home

runner = CliRunner()

def test_cli_gui_command():
    """Test that the 'gui' command calls run_gui."""
    # Since main.py does `from pharmabot import gui`, and calls `gui.run_gui()`,
    # we patch `pharmabot.gui.run_gui`.
    # However, since gui is a package now, run_gui is an attribute of the package module.
    with patch("pharmabot.gui.run_gui") as mock_run_gui:
        result = runner.invoke(app, ["gui"])
        assert result.exit_code == 0
        mock_run_gui.assert_called_once()

def test_run_gui():
    """Test that run_gui sets up the UI and starts the native app."""
    # This is in pharmabot.gui.app
    with patch("pharmabot.gui.app.create_ui") as mock_create_ui, \
         patch("nicegui.ui.run") as mock_ui_run:

        gui_app.run_gui()

        mock_create_ui.assert_called_once()
        mock_ui_run.assert_called_once_with(native=True, title="Pharmabot", reload=False)

def test_create_ui():
    """Test that create_ui adds expected elements (sidebar and navigation)."""
    # This tests app.create_ui
    with patch("nicegui.ui.column") as mock_column, \
         patch("pharmabot.gui.app.render_sidebar") as mock_sidebar, \
         patch("pharmabot.gui.app.navigate") as mock_navigate:

        # Mock the return value of chained .classes() call
        mock_container = mock_column.return_value.classes.return_value

        gui_app.create_ui()

        mock_column.assert_called_once()
        mock_sidebar.assert_called_once()
        mock_navigate.assert_called_once_with(mock_container, home.render)

def test_home_render():
    """Test that home.render adds expected elements."""
    with patch("nicegui.ui.card") as mock_card, \
         patch("nicegui.ui.label") as mock_label, \
         patch("nicegui.ui.button") as mock_button:

        # Setup context manager mock for card
        mock_card.return_value.__enter__.return_value = MagicMock()

        home.render()

        mock_card.assert_called_once()
        mock_label.assert_called_with("Pharmabot")
        # Ensure classes called
        # We can't easily check chained calls like .classes() unless we mock the return value.
        # But we can check button call arguments.
        mock_button.assert_called_with("Initialize Database", on_click=home.init_db_action)

def test_init_db_action_success():
    """Test init_db_action on success."""
    with patch("pharmabot.gui.pages.home.create_db_and_tables") as mock_db, \
         patch("nicegui.ui.notify") as mock_notify:

        home.init_db_action()

        mock_db.assert_called_once()
        mock_notify.assert_called_with("Database initialized successfully", type="positive")

def test_init_db_action_failure():
    """Test init_db_action on failure."""
    with patch("pharmabot.gui.pages.home.create_db_and_tables", side_effect=Exception("DB Error")) as mock_db, \
         patch("nicegui.ui.notify") as mock_notify:

        home.init_db_action()

        mock_db.assert_called_once()
        mock_notify.assert_called_with("Error initializing database: DB Error", type="negative")
