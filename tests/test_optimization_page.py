import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open, AsyncMock

# 1. Mock nicegui BEFORE importing the module
mock_ui = MagicMock()
mock_run = MagicMock()
mock_nicegui = MagicMock()
mock_nicegui.ui = mock_ui
mock_nicegui.run = mock_run
sys.modules["nicegui"] = mock_nicegui

# Now we can import the module under test
from pharmabot.gui.pages import optimization
from pharmabot.services.price_optimizer import Solution, Order, InventoryMatch
from pharmabot.models import Pharmacy

class TestOptimizationPage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Reset mocks
        mock_ui.reset_mock()
        mock_run.reset_mock()

        # Setup run.io_bound to be awaitable
        # It should execute the function passed to it
        async def side_effect_io_bound(func, *args, **kwargs):
            return func(*args, **kwargs)
        mock_run.io_bound = AsyncMock(side_effect=side_effect_io_bound)

        # Setup common return values for UI elements
        # We need to handle method chaining: ui.number().classes() -> returns the element
        self.mock_max_orders = MagicMock()
        self.mock_max_orders.value = 2
        # Configure chaining
        self.mock_max_orders.classes.return_value = self.mock_max_orders
        self.mock_max_orders.props.return_value = self.mock_max_orders

        self.mock_limit = MagicMock()
        self.mock_limit.value = "3"
        self.mock_limit.classes.return_value = self.mock_limit
        self.mock_limit.props.return_value = self.mock_limit

        # Mock UI elements creation
        mock_ui.number.return_value = self.mock_max_orders
        mock_ui.input.return_value = self.mock_limit

        self.mock_optimize_btn = MagicMock()
        self.mock_optimize_btn.on.return_value = self.mock_optimize_btn # chaining

        self.mock_save_btn = MagicMock()
        self.mock_save_btn.classes.return_value = self.mock_save_btn
        self.mock_save_btn.props.return_value = self.mock_save_btn
        self.mock_save_btn.on.return_value = self.mock_save_btn

        mock_ui.button.side_effect = [self.mock_optimize_btn, self.mock_save_btn] # First call optimize, second save

        self.mock_results_container = MagicMock()
        self.mock_results_container.classes.return_value = self.mock_results_container
        mock_ui.column.return_value = self.mock_results_container

    @patch("pharmabot.gui.pages.optimization.basket_service")
    @patch("pharmabot.gui.pages.optimization.database")
    async def test_run_optimization_click(self, mock_database, mock_basket_service):
        """Test that clicking optimize triggers the service."""
        # Setup mocks
        mock_session = MagicMock()
        mock_database.get_session.return_value.__enter__.return_value = mock_session

        # Mock solutions
        sol = Solution(orders=[], total_cost=10.0) # simplified
        mock_basket_service.optimize_basket.return_value = [sol]

        # Capture the callback
        optimization.render()

        # Get the registered callback from optimize_btn.on("click", ...)
        # optimize_btn.on call args: ("click", run_optimization)
        # Note: optimize_btn is created via ui.button("Optimize", ...) which is the 1st call

        # Verify ui.button calls
        # 1. Optimize
        # 2. Save
        self.assertEqual(mock_ui.button.call_count, 2)

        # Retrieve the callback
        args, _ = self.mock_optimize_btn.on.call_args
        event_name, callback = args
        self.assertEqual(event_name, "click")

        # Simulate click - await the callback
        await callback()

        # Verify run.io_bound was called
        # mock_run.io_bound is an AsyncMock, so we can assert awaited
        mock_run.io_bound.assert_awaited()

        # Verify service call
        # The service call happens inside the function passed to io_bound
        # Since our side_effect executes it, the mock should be called
        mock_database.get_session.assert_called()
        mock_basket_service.optimize_basket.assert_called_with(mock_session, limit="3", max_orders=2)

    @patch("tkinter.Tk")
    @patch("tkinter.filedialog.asksaveasfilename")
    def test_save_results(self, mock_asksaveas, mock_tk):
        """Test saving results to file."""
        # Setup data
        pharmacy = Pharmacy(name="TestPharm", base_shipping_cost=5.0)
        match = InventoryMatch(product_id=1, price=10.0, quantity_needed=2, subtotal=20.0)
        order = Order(
            pharmacy=pharmacy,
            items=[match],
            items_cost=20.0,
            shipping_cost=5.0,
            total_cost=25.0
        )
        sol = Solution(orders=[order], total_cost=25.0)

        # Mock file dialog
        mock_asksaveas.return_value = "/tmp/test_results.txt"

        # Mock open
        with patch("builtins.open", mock_open()) as mock_file:
            optimization.save_results([sol])

            mock_asksaveas.assert_called()
            mock_file.assert_called_with("/tmp/test_results.txt", "w", encoding="utf-8")

            # Check written content
            handle = mock_file()
            written = handle.write.call_args[0][0]
            self.assertIn("TestPharm", written)
            self.assertIn("Total: € 25.00", written)

    def test_format_solution_text(self):
        """Test the text formatting logic."""
        pharmacy = Pharmacy(name="PharmaA", base_shipping_cost=3.0, free_shipping_threshold=50.0)
        match = InventoryMatch(product_id=101, price=12.50, quantity_needed=2, subtotal=25.00)
        order = Order(
            pharmacy=pharmacy,
            items=[match],
            items_cost=25.00,
            shipping_cost=3.00,
            total_cost=28.00
        )
        sol = Solution(orders=[order], total_cost=28.00)

        text = optimization.format_solution_text([sol])

        self.assertIn("--- Solutions with 1 Order ---", text)
        self.assertIn("Option 1 (Total: € 28.00)", text)
        self.assertIn("Pharmacy: PharmaA", text)
        self.assertIn("Items Cost: € 25.00", text)
        self.assertIn("Shipping: € 3.00", text)
        self.assertIn("Free shipping threshold: € 50.00", text)
        self.assertIn("ID 101: x2 @ € 12.50", text)

if __name__ == "__main__":
    unittest.main()
