# wow_terminal/quant.py (Added try-except, checks for empty/None)
import pandas as pd
import numpy as np
import json
from .database import Database
from .analyzer import AuctionAnalyzer
from .api import BlizzardAPI
from .calculator import CraftingCalculator, Recipe

# Vendor prices (copper; expand from Wowhead)
VENDOR_PRICES = {  # item_id: vendor_price_copper per unit
    2770: 500,  # Copper Ore 5s (example; adjust)
    10620: 0,   # Thorium no flip
    13463: 0,   # Dreamfoil no
    # Add: 3858 Mithril Ore 5s, etc.
}

# Farms (expected/hr; expand)
FARMS = {
    'ZF Graveyard': {'raw_gold': 200, 'items': {2770: 100}},  # Structure with items dict
    'Thorium Point': {'raw_gold': 150, 'items': {10620: 80}},
    'Dreamfoil Farm (EPL)': {'raw_gold': 100, 'items': {13463: 30}},
}

# Recipes for demand (mat_id: [recipe_ids consuming it])
DEMAND_RECIPES = {
    10620: [17187],  # Thorium Ore -> Arcanite (via Thorium Bar)
    13463: [17570],  # Dreamfoil -> Elixir of the Mongoose
}

def get_item_history(item_id, realm_id, days=30):
    try:
        df = Database.get_price_history(item_id, realm_id, days)
        if df.empty: return df
        df['price'] = df['avg_price'] / 10000
        return df
    except Exception as e:
        print(f"History error: {e}")
        return pd.DataFrame()

def rsi(item_id, realm_id, period=14, days=30):
    try:
        df = get_item_history(item_id, realm_id, days)
        if len(df) < period + 1: return None, pd.DataFrame()
        delta = df['price'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)  # Avoid div zero
        rsi_series = 100 - (100 / (1 + rs))
        return rsi_series.iloc[-1] if not rsi_series.empty else None, pd.DataFrame({'datetime': df['datetime'], 'rsi': rsi_series}).dropna()
    except Exception as e:
        print(f"RSI error: {e}")
        return None, pd.DataFrame()

def volatility(item_id, realm_id, days=30):
    try:
        df = get_item_history(item_id, realm_id, days)
        returns = df['price'].pct_change().dropna()
        return returns.std() * np.sqrt(252) if not returns.empty else 0
    except Exception as e:
        print(f"Vol error: {e}")
        return 0

def sniping_opps(auctions_data, item_id, realm_id, threshold=0.9):
    try:
        stats = AuctionAnalyzer.analyze_item(auctions_data, item_id)
        if not stats: return []
        hist_avg = Database.get_recent_price(item_id, realm_id, hours=168) or stats['avg']
        opps = []
        for auc in auctions_data.get('auctions', []):
            if auc['item']['id'] == item_id:
                price = auc.get('buyout') or auc.get('unit_price', 0)
                qty = auc['quantity'] or 1
                unit_gold = price / qty / 10000
                if unit_gold < hist_avg * threshold:
                    opps.append({
                        'Qty': qty,
                        'Buy Gold': format_gold(unit_gold),
                        'Savings': format_gold(hist_avg - unit_gold),
                        'Auc ID': auc['id']
                    })
        return opps
    except Exception as e:
        print(f"Sniping error: {e}")
        return []

# 1. Sniping
def sniping_opps(auctions_data, item_id, realm_id, threshold=0.9):
    stats = AuctionAnalyzer.analyze_item(auctions_data, item_id)
    if not stats: return []
    hist_avg = Database.get_recent_price(item_id, realm_id, hours=168) or stats['avg']
    opps = []
    for auc in auctions_data.get('auctions', []):
        if auc['item']['id'] == item_id:
            unit_gold = (auc.get('buyout') or auc.get('unit_price', 0)) / auc['quantity'] / 10000
            if unit_gold < hist_avg * threshold:
                opps.append({
                    'Qty': auc['quantity'],
                    'Buy Gold': format_gold(unit_gold),
                    'Savings': format_gold(hist_avg - unit_gold),
                    'Auc ID': auc['id']
                })
    return opps

# 2. Vendor Flips
def vendor_flips(auctions_data, api):
    try:
    flips = []
    for auc in auctions_data.get('auctions', []):
        iid = auc['item']['id']
        if iid in VENDOR_PRICES and VENDOR_PRICES[iid] > 0:
            unit_gold = (auc.get('buyout') or auc.get('unit_price', 0)) / auc['quantity'] / 10000
            vendor_gold = VENDOR_PRICES[iid] / 10000
            if unit_gold < vendor_gold:
                name = api.get_item_details(iid)['name']
                profit = (vendor_gold - unit_gold) * auc['quantity']
                flips.append({
                    'Item': name,
                    'Buy': format_gold(unit_gold * auc['quantity']),
                    'Vendor': format_gold(vendor_gold * auc['quantity']),
                    'Profit': format_gold(profit)
                })
return flips
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 3. Farms GPH
def farm_gph(farm_key, get_unit_func):
    try:
    if farm_key not in FARMS: return 0
    farm = FARMS[farm_key]
    mat_val = sum(get_unit_func(iid) * qty for iid, qty in farm['items'].items())
    return farm['raw_gold'] + mat_val
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 4. Arb (needs multi auctions)
def realm_arb(item_id, realm_auctions):  # {realm: auctions_data}
        try:
    prices = {}
    for realm, data in realm_auctions.items():
        stats = AuctionAnalyzer.analyze_item(data, item_id)
        if stats: prices[realm] = stats['avg']
    if len(prices) < 2: return pd.DataFrame()
    df = pd.DataFrame(list(prices.items()), columns=['Realm', 'Avg Gold'])
    min_p = df['Avg Gold'].min()
    df['Spread %'] = ((df['Avg Gold'] - min_p) / min_p * 100).round(1)
    return df[df['Spread %'] > 15].sort_values('Spread %', ascending=False)
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 5. Posting
def post_price(stats, vol):
        try:
    if vol > 0.2: return stats['min'] * 0.95
    return stats['min'] * 0.99 - 0.0001  # Undercut
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 6. Demand
def mat_demand(mat_id, auctions_data, api):
        try:
    demand_vol = 0
    for rid in DEMAND_RECIPES.get(mat_id, []):
        recipe = Recipe(rid, api)
        if recipe.crafted_item_id:
            stats = AuctionAnalyzer.analyze_item(auctions_data, recipe.crafted_item_id)
            demand_vol += stats.get('volume', 0) if stats else 0
    return demand_vol
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 7. Health
def economy_health(auctions_data):
        try:
    listings = len(auctions_data.get('auctions', []))
    return {
        'Listings': listings,
        'Vol Index': 50,  # Placeholder; avg RSI or vol
        'Health': 'Stable' if listings > 10000 else 'Low Activity'
    }
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 8. News (static; fetch via tool later)
RECENT_NEWS = [{'title': 'TBC Prep: Stock Thorium!', 'impact': 'High'}]

# 9. Backtest
def backtest_strategy(item_id, realm_id, days=30):
        try:
    df = get_item_history(item_id, realm_id, days)
    if len(df) < 2: return pd.DataFrame()
    df['returns'] = df['price'].pct_change()
    df['cum_ret'] = (1 + df['returns']).cumprod() - 1
    return df[['datetime', 'price', 'cum_ret']].dropna()
    except Exception as e:
        print(f"Flips error: {e}")
        return []

# 10. Portfolio
def portfolio_value(positions, get_unit_func):
        try:
    if not positions: return {'cost': 0, 'current': 0, 'pnl': 0}
    cost = sum(p.get('buy_price', 0) * p.get('qty', 0) for p in positions)
    current = sum(get_unit_func(p['item_id']) * p['qty'] for p in positions)
    return {'cost': cost, 'current': current, 'pnl': current - cost}
    except Exception as e:
        print(f"Flips error: {e}")
        return []
