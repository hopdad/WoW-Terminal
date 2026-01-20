# wow_terminal/calculator.py (Handle missing data)
from typing import Dict, Optional, List
from .api import BlizzardAPI

class Recipe:
    def __init__(self, recipe_id: int, api: BlizzardAPI):
        self.recipe_id = recipe_id
        self.api = api
        self.data = self._fetch_recipe()

    def _fetch_recipe(self) -> Dict:
        try:
            return self.api.fetch(f"/data/wow/recipe/{self.recipe_id}", namespace="static-classic-us")
        except ValueError as e:
            print(f"Recipe fetch error: {e}")
            return {}

    @property
    def name(self) -> str:
        return self.data.get("name", "Unknown Recipe")

    @property
    def crafted_item_id(self) -> Optional[int]:
        ci = self.data.get("crafted_item", {})
        return ci.get("id") if ci else None

    @property
    def reagents(self) -> List[Dict]:
        return [
            {"item_id": r["reagent"]["id"], "quantity": r["quantity"]}
            for r in self.data.get("reagents", [])
        ]

    def get_item_name(self, item_id: int) -> str:
        try:
            return self.api.get_item_details(item_id)["name"]
        except ValueError:
            return f"Item {item_id}"

class CraftingCalculator:
    def __init__(self, api: BlizzardAPI, auctions_data: dict):
        self.api = api
        self.auctions = auctions_data or {"auctions": []}

    def get_unit_price(self, item_id: int) -> float:
        try:
            min_price = float('inf')
            for auc in self.auctions.get("auctions", []):
                if auc["item"]["id"] == item_id:
                    price = auc.get("buyout") or auc.get("unit_price", 0)
                    unit = price / auc["quantity"] if auc["quantity"] else 0
                    min_price = min(min_price, unit)
            return min_price / 10000 if min_price != float('inf') else 0.0
        except ZeroDivisionError:
            return 0.0
        except KeyError:
            return 0.0

    def calculate_profit(self, recipe: Recipe, quantity: int = 1) -> Dict:
        if not recipe.data: return {"error": "Recipe not loaded"}
        crafted_id = recipe.crafted_item_id
        if not crafted_id: return {"error": "No crafted item"}
        total_cost_copper = 0
        input_details = []
        for reag in recipe.reagents:
            unit_price = self.get_unit_price(reag["item_id"])
            cost = unit_price * reag["quantity"] * quantity * 10000  # To copper
            total_cost_copper += cost
            input_details.append({
                "item_id": reag["item_id"],
                "name": recipe.get_item_name(reag["item_id"]),
                "qty": reag["quantity"] * quantity,
                "unit_price_gold": unit_price,
                "total_cost_gold": cost / 10000
            })
        sell_unit = self.get_unit_price(crafted_id)
        revenue_gold = sell_unit * quantity
        total_cost_gold = total_cost_copper / 10000
        profit_gold = revenue_gold - total_cost_gold
        margin_pct = (profit_gold / total_cost_gold * 100) if total_cost_gold > 0 else 0
        return {
            "crafted_name": recipe.get_item_name(crafted_id),
            "crafted_id": crafted_id,
            "quantity_crafted": quantity,
            "total_cost_gold": total_cost_gold,
            "revenue_gold": revenue_gold,
            "profit_gold": profit_gold,
            "margin_pct": margin_pct,
            "inputs": input_details
        }

def format_gold(amount: float) -> str:
    try:
        g = int(amount * 10000)
        return f"{g//10000:,}g {(g%10000)//100:02d}s {g%100:02d}c"
    except ValueError:
        return "0g 00s 00c"

def print_crafting_flow(calculation: Dict):
    # Console version; UI adapts
    pass  # Omitted for brevity, but add try if needed
