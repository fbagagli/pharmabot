from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from pharmabot.main import app
from pharmabot import gui

runner = CliRunner()

def test_cli_gui_command():
    """Test that the 'gui' command calls run_gui."""
    with patch("pharmabot.gui.run_gui") as mock_run_gui:
        result = runner.invoke(app, ["gui"])
        assert result.exit_code == 0
        mock_run_gui.assert_called_once()

def test_run_gui():
    """Test that run_gui sets up the UI and starts the native app."""
    with patch("pharmabot.gui.create_ui") as mock_create_ui, \
         patch("nicegui.ui.run") as mock_ui_run:

        gui.run_gui()

        mock_create_ui.assert_called_once()
        mock_ui_run.assert_called_once_with(native=True, title="Pharmabot", reload=False)

def test_create_ui():
    """Test that create_ui adds expected elements."""
    with patch("nicegui.ui.card") as mock_card, \
         patch("nicegui.ui.label") as mock_label, \
         patch("nicegui.ui.button") as mock_button:

        # Setup context manager mock for card
        mock_card.return_value.__enter__.return_value = MagicMock()

        gui.create_ui()

        mock_card.assert_called_once()
        mock_label.assert_called_with("Pharmabot")
        mock_button.assert_called_with("Initialize Database", on_click=gui.init_db_action)

def test_init_db_action_success():
    """Test init_db_action on success."""
    with patch("pharmabot.gui.create_db_and_tables") as mock_db, \
         patch("nicegui.ui.notify") as mock_notify:

        gui.init_db_action()

        mock_db.assert_called_once()
        mock_notify.assert_called_with("Database initialized successfully", type="positive")

def test_init_db_action_failure():
    """Test init_db_action on failure."""
    with patch("pharmabot.gui.create_db_and_tables", side_effect=Exception("DB Error")) as mock_db, \
         patch("nicegui.ui.notify") as mock_notify:

        gui.init_db_action()

        mock_db.assert_called_once()
        mock_notify.assert_called_with("Error initializing database: DB Error", type="negative")
