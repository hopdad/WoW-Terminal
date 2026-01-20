from typing import Dict, Optional, List
from .api import BlizzardAPI

class Recipe:
    def __init__(self, recipe_id: int, api: BlizzardAPI):
        self.recipe_id = recipe_id
        self.api = api
        self.data = self._fetch_recipe()

    def _fetch_recipe(self) -> Dict:
        try:
            data = self.api.fetch(f"/data/wow/recipe/{self.recipe_id}", namespace="static-classic-us")
            return data
        except Exception as e:
            print(f"Error fetching recipe {self.recipe_id}: {e}")
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
            item_data = self.api.fetch(f"/data/wow/item/{item_id}", namespace="static-classic-us")
            return item_data.get("name", f"Item {item_id}")
        except:
            return f"Item {item_id}"

class CraftingCalculator:
    def __init__(self, api: BlizzardAPI, auctions_data: dict):
        self.api = api
        self.auctions = auctions_data

    def get_unit_price(self, item_id: int) -> float:
        """Get min unit_price in copper from auctions (Classic style: use lowest for cost calcs)."""
        min_price = float('inf')
        for auc in self.auctions.get("auctions", []):
            if auc["item"]["id"] == item_id:
                price = auc.get("buyout") or auc.get("unit_price")
                if price:
                    unit = price / auc["quantity"]
                    if unit < min_price:
                        min_price = unit
        return min_price if min_price != float('inf') else 0.0

    def calculate_profit(self, recipe: Recipe, quantity: int = 1) -> Dict:
        if not recipe.data:
            return {"error": "Recipe not loaded"}
        crafted_id = recipe.crafted_item_id
        if not crafted_id:
            return {"error": "No crafted item in recipe"}
        total_cost_copper = 0
        input_details = []
        for reag in recipe.reagents:
            unit_price = self.get_unit_price(reag["item_id"])
            cost = unit_price * reag["quantity"] * quantity
            total_cost_copper += cost
            input_details.append({
                "item_id": reag["item_id"],
                "name": recipe.get_item_name(reag["item_id"]),
                "qty": reag["quantity"] * quantity,
                "unit_price_gold": unit_price / 10000,
                "total_cost_gold": cost / 10000
            })
        sell_price_unit = self.get_unit_price(crafted_id)
        revenue_gold = (sell_price_unit / 10000) * quantity
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
    g = int(amount * 10000)  # To copper
    return f"{g//10000:,}g {(g%10000)//100:02d}s {g%100:02d}c"

def print_crafting_flow(calculation: Dict):
    if "error" in calculation:
        print(calculation["error"])
        return
    print(f"\n=== Crafting Flow: {calculation['crafted_name']} (x{calculation['quantity_crafted']}) ===")
    print("Inputs (Reagents) ───────────────────────► Output")
    print("")
    for inp in calculation["inputs"]:
        print(f"  {inp['name']} x{inp['qty']}   @ {format_gold(inp['unit_price_gold'])} ea   →   {format_gold(inp['total_cost_gold'])}")
    print("\n                          ▼")
    print(f"               {calculation['crafted_name']} x{calculation['quantity_crafted']}")
    print(f"               Sell @ {format_gold(calculation['revenue_gold'] / calculation['quantity_crafted'])} ea")
    print("")
    print(f"Total Cost: {format_gold(calculation['total_cost_gold'])}")
    print(f"Revenue:    {format_gold(calculation['revenue_gold'])}")
    print(f"Profit:     {format_gold(calculation['profit_gold'])}   ({calculation['margin_pct']:+.1f}%)")
    if calculation['margin_pct'] > 10:
        print("   → Strong opportunity!")
    elif calculation['margin_pct'] > 0:
        print("   → Positive margin.")
    else:
        print("   → Loss or break-even.")
