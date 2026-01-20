import pandas as pd
from datetime import datetime
from .api import BlizzardAPI
from .database import Database
from .analyzer import AuctionAnalyzer
from .calculator import Recipe, CraftingCalculator, print_crafting_flow, format_gold

def main():
    client_id = "YOUR_CLIENT_ID"  # Replace
    client_secret = "YOUR_CLIENT_SECRET"  # Replace

    Database.init_db()
    api = BlizzardAPI(client_id, client_secret)

    # Popular US Classic Era realms (PvP/PvE mix)
    realm_names = ["whitemane", "mankrik", "atiesh"]
    realm_ids = {}
    for name in realm_names:
        rid = api.get_connected_realm_id(name)
        if rid:
            realm_ids[name] = rid

    if not realm_ids:
        print("No realms found. Check API or realm names.")
        return

    # Classic high-value items (e.g., ores/herbs for crafting/transmutes)
    items = {
        10620: "Thorium Ore",  # Key for bars, engineering
        13463: "Dreamfoil",    # For high-end pots/elixirs
    }

    timestamp = int(datetime.now().timestamp())

    results = []
    auctions_data = None  # Use last fetched for calc

    for realm_name, realm_id in realm_ids.items():
        print(f"\nFetching auctions for {realm_name} (ID: {realm_id})...")
        try:
            auctions_data = api.get_auctions(realm_id)
            print(f"Last modified: {datetime.fromtimestamp(auctions_data['lastModified']/1000)}")
        except Exception as e:
            print(f"Error: {e}")
            continue

        for item_id, item_name in items.items():
            stats = AuctionAnalyzer.analyze_item(auctions_data, item_id)
            if stats:
                old_price = Database.get_recent_price(item_id, realm_id)
                change = ((stats['avg'] - old_price) / old_price * 100) if old_price else 0
                Database.store_price(realm_id, item_id, stats, timestamp)

                results.append({
                    'Realm': realm_name,
                    'Item': item_name,
                    'Min': format_gold(stats['min']),
                    'Avg': format_gold(stats['avg']),
                    'Max': format_gold(stats['max']),
                    'Volume': stats['volume'],
                    'Listings': stats['listings'],
                    '% Change (24h)': f"{change:+.1f}%"
                })
            else:
                print(f"No auctions for {item_name}")

    if results:
        df = pd.DataFrame(results)
        print("\n=== CURRENT MARKET SUMMARY ===")
        print(df.to_string(index=False))

    from .quant import volatility, moving_averages, correlation

# Example
thorium_id = 10620
print(f"Thorium Ore Volatility (annualized): {volatility(thorium_id, sample_realm):.2f}")
ma_df = moving_averages(thorium_id, sample_realm)
print(ma_df.tail())

    # Example history for first item/realm
    if realm_ids:
        sample_item = 10620
        sample_realm = list(realm_ids.values())[0]
        hist = Database.get_price_history(sample_item, sample_realm)
        if not hist.empty:
            print(f"\n=== 7-DAY HISTORY: {list(items.values())[0]} on {list(realm_ids.keys())[0]} ===")
            hist['avg_gold'] = hist['avg_price'] / 10000
            print(hist[['datetime', 'avg_gold']].to_string(index=False))

    # Crafting Example: Transmute Arcanite (x5, as cooldown allows batches over time)
    if auctions_data:
        example_recipe_id = 17187  # Transmute: Arcanite
        recipe = Recipe(example_recipe_id, api)
        if recipe.data:
            calc = CraftingCalculator(api, auctions_data)
            profit = calc.calculate_profit(recipe, quantity=5)
            print_crafting_flow(profit)

if __name__ == "__main__":
    main()
