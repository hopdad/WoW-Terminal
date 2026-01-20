import pandas as pd
from typing import Dict, Optional

class AuctionAnalyzer:
    @staticmethod
    def analyze_item(auctions_data: dict, item_id: int) -> Optional[Dict]:
        auctions = auctions_data.get("auctions", [])
        item_auctions = [a for a in auctions if a["item"]["id"] == item_id]
        if not item_auctions:
            return None
        prices_copper = []
        quantities = []
        for auc in item_auctions:
            price = auc.get("buyout") or auc.get("unit_price")
            if price:
                prices_copper.append(price / auc["quantity"])  # unit price per item
                quantities.append(auc["quantity"])
        if not prices_copper:
            return None
        df = pd.DataFrame({"price": prices_copper, "qty": quantities})
        stats = {
            "min": df["price"].min() / 10000,
            "avg": df["price"].mean() / 10000,
            "max": df["price"].max() / 10000,
            "volume": df["qty"].sum(),
            "listings": len(item_auctions)
        }
        return stats
