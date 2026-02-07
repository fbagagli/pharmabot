from decimal import Decimal
from typing import List, Dict, Set, Optional, Tuple
from itertools import combinations
from pydantic import BaseModel
from sqlmodel import Session, select
from pharmabot.models import Pharmacy, Offer, BasketItem

# --- Data Structures (Pydantic) ---


class BasketContent(BaseModel):
    items: Dict[int, int]


class InventoryMatch(BaseModel):
    product_id: int
    price: Decimal
    quantity_needed: int
    subtotal: Decimal


class PharmacyInventory(BaseModel):
    """
    Represents what a single pharmacy has in stock matching the basket.
    """
    pharmacy: Pharmacy
    matches: List[InventoryMatch]
    product_ids: Set[int] = set()

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.product_ids = {m.product_id for m in self.matches}

    def has_product(self, product_id: int) -> bool:
        return product_id in self.product_ids

    def get_match(self, product_id: int) -> Optional[InventoryMatch]:
        for m in self.matches:
            if m.product_id == product_id:
                return m
        return None


class Order(BaseModel):
    """
    Represents a finalized order from a specific pharmacy.
    """
    pharmacy: Pharmacy
    items: List[InventoryMatch]
    items_cost: Decimal
    shipping_cost: Decimal
    total_cost: Decimal

    class Config:
        arbitrary_types_allowed = True


class Solution(BaseModel):
    """
    Represents a complete solution (potentially multi-order).
    """
    orders: List[Order]
    total_cost: Decimal

    @property
    def order_count(self) -> int:
        return len(self.orders)

    def __lt__(self, other):
        return self.total_cost < other.total_cost


# --- The Logic Class ---


class PriceOptimizer:
    def __init__(self, basket: BasketContent, inventories: List[PharmacyInventory]):
        self.basket = basket
        self.inventories = inventories
        # Pre-process: Map product_id to list of inventories that have it
        self.product_availability = {pid: [] for pid in self.basket.items}
        for inv in self.inventories:
            for match in inv.matches:
                self.product_availability[match.product_id].append(inv)

    @classmethod
    def from_session(
        cls, session: Session, basket_items: List[BasketItem]
    ) -> "PriceOptimizer":
        basket_map = {b.product_id: b.quantity for b in basket_items}
        product_ids = list(basket_map.keys())
        basket_content = BasketContent(items=basket_map)

        # Fetch offers + pharmacy info
        statement = (
            select(Offer, Pharmacy)
            .join(Pharmacy)
            .where(Offer.product_id.in_(product_ids))
        )
        results = session.exec(statement).all()

        grouped_data = {}
        for offer, pharmacy in results:
            if pharmacy.id not in grouped_data:
                grouped_data[pharmacy.id] = {"pharmacy": pharmacy, "offers": []}
            grouped_data[pharmacy.id]["offers"].append(offer)

        inventories = []
        for pid, data in grouped_data.items():
            pharmacy = data["pharmacy"]
            offers = data["offers"]

            matches = []
            for offer in offers:
                qty = basket_map[offer.product_id]
                cost = offer.price * qty
                matches.append(
                    InventoryMatch(
                        product_id=offer.product_id,
                        price=offer.price,
                        quantity_needed=qty,
                        subtotal=cost,
                    )
                )

            inventories.append(
                PharmacyInventory(
                    pharmacy=pharmacy,
                    matches=matches,
                )
            )

        return cls(basket=basket_content, inventories=inventories)

    def find_best_solutions(self, max_orders: int = 1, limits: Dict[int, int] = None) -> List[Solution]:
        """
        Returns the top solutions grouped by number of orders.
        """
        if limits is None:
            limits = {k: 3 for k in range(1, max_orders + 1)}

        all_solutions = []

        # We process each k independently to ensure we respect the per-k limits
        for k in range(1, max_orders + 1):
            if k not in limits:
                continue

            limit = limits[k]
            solutions_k = self._find_solutions_for_k_orders(k, limit)
            all_solutions.extend(solutions_k)

        return all_solutions

    def _get_pruned_inventories(self, top_n: int = 5) -> List[PharmacyInventory]:
        """
        Returns a subset of inventories that are competitive.
        For each product, pick top N cheapest pharmacies.
        Union of these sets.
        """
        kept_ids = set()
        pruned_list = []

        for pid, inv_list in self.product_availability.items():
            # Sort by price of this product
            sorted_inv = sorted(inv_list, key=lambda inv: inv.get_match(pid).price)

            # Keep top N
            for inv in sorted_inv[:top_n]:
                if inv.pharmacy.id not in kept_ids:
                    kept_ids.add(inv.pharmacy.id)
                    pruned_list.append(inv)

        return pruned_list

    def _find_solutions_for_k_orders(self, k: int, limit: int) -> List[Solution]:
        """
        Find best solutions using exactly k pharmacies (or fewer if some end up empty).
        However, strictly speaking, we iterate combinations of size k.
        """
        # If k=1, we can just iterate all inventories (or pruned ones)
        # But to be consistent and safe, we use pruned for combinatorial search.

        if k == 1:
            relevant_inventories = self.inventories
        else:
            # For combinations, prune to avoid explosion
            relevant_inventories = self._get_pruned_inventories(top_n=5)

        candidates = []

        # Iterate combinations
        for combo in combinations(relevant_inventories, k):
            # Check coverage
            if not self._covers_all_items(combo):
                continue

            # Solve assignment for this combination
            solution = self._solve_assignment(combo)
            if solution:
                candidates.append(solution)

        # Sort by total cost
        candidates.sort()

        # Filter: strictly k orders
        valid_k_solutions = [s for s in candidates if s.order_count == k]

        return valid_k_solutions[:limit]

    def _covers_all_items(self, inventories: Tuple[PharmacyInventory, ...]) -> bool:
        covered_ids = set()
        for inv in inventories:
            covered_ids.update(inv.product_ids)
        return len(covered_ids) == len(self.basket.items)

    def _solve_assignment(self, inventories: Tuple[PharmacyInventory, ...]) -> Optional[Solution]:
        """
        Find the optimal assignment of items to the given set of pharmacies.
        Returns a Solution object or None if no valid assignment found.
        """
        items = list(self.basket.items.keys())
        # recursive solver
        # state: index in items list, current_assignments {pharmacy_index: [item_matches]}

        best_solution = None
        min_total_cost = Decimal('Infinity')

        # Map product_id to available inventories (subset)
        # item_options: List of (item_id, List[Tuple[inv_index, InventoryMatch]])
        item_options = []
        for pid in items:
            opts = []
            for idx, inv in enumerate(inventories):
                match = inv.get_match(pid)
                if match:
                    opts.append((idx, match))
            item_options.append((pid, opts))

        # Optimization: Sort items by number of options (ascending) to reduce branching early?
        item_options.sort(key=lambda x: len(x[1]))

        # Current state
        # assignments: list of selected matches per pharmacy index
        current_assignments = [[] for _ in range(len(inventories))]

        def backtrack(item_idx: int):
            nonlocal min_total_cost, best_solution

            # Base case
            if item_idx == len(items):
                # All items assigned. Calculate cost.
                return calculate_solution()

            pid, options = item_options[item_idx]

            # Try each option
            for inv_idx, match in options:
                # Add to assignment
                current_assignments[inv_idx].append(match)

                # Pruning?
                # Calculate current partial cost?
                # Shipping thresholds make cost non-monotonic (adding item can reduce shipping).
                # But Lower Bound is possible:
                # LB = current_items_cost + sum(min_price(remaining_items))
                # For shipping: assume best case (0) for remaining, or based on current totals.
                # Given strict "shipping sensitivity", better not prune aggressively unless
                # we are sure.
                # With k small and items small, simple recursion might be fast enough.

                backtrack(item_idx + 1)

                # Backtrack
                current_assignments[inv_idx].pop()

        def calculate_solution():
            nonlocal min_total_cost, best_solution

            orders = []
            total_c = Decimal(0)

            for idx, assigned_matches in enumerate(current_assignments):
                if not assigned_matches:
                    continue

                inv = inventories[idx]
                items_c = sum(m.subtotal for m in assigned_matches)

                # Shipping
                shipping = inv.pharmacy.base_shipping_cost
                if (
                    inv.pharmacy.free_shipping_threshold is not None
                    and items_c >= inv.pharmacy.free_shipping_threshold
                ):
                    shipping = Decimal(0)

                order_total = items_c + shipping

                orders.append(Order(
                    pharmacy=inv.pharmacy,
                    items=assigned_matches[:], # copy
                    items_cost=items_c,
                    shipping_cost=shipping,
                    total_cost=order_total
                ))
                total_c += order_total

            if total_c < min_total_cost:
                min_total_cost = total_c
                best_solution = Solution(orders=orders, total_cost=total_c)

        backtrack(0)
        return best_solution
