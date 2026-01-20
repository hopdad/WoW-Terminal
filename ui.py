import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from .api import BlizzardAPI
from .database import Database
from .analyzer import AuctionAnalyzer
from .calculator import Recipe, CraftingCalculator, format_gold
from .quant import *

st.markdown("""
<style>
    .stApp { background-color: #000; color: #fff; }
    [data-testid="stSidebar"] { background-color: #111; }
    .stTabs button { color: #fff; }
    .positive { color: lime; } .negative { color: red; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def fetch_multi_auctions(api, realms):
    data = {}
    for r in realms:
        rid = api.get_connected_realm_id(r)
        if rid: data[r] = api.get_auctions(rid)
    return data

def main_ui():
    st.title("WoW Classic Economy Terminal")
    # Sidebar (old + new options)
    st.sidebar.header("Settings")
    client_id = st.sidebar.text_input("Client ID", "YOUR_CLIENT_ID")
    client_secret = st.sidebar.text_input("Client Secret", type="password")
    realm = st.sidebar.selectbox("Realm", ["whitemane", "mankrik", "atiesh"])
    item_id = st.sidebar.selectbox("Item ID", [10620, 13463, 12360])
    recipe_id = st.sidebar.number_input("Recipe ID", 17187)
    craft_qty = st.sidebar.number_input("Craft Qty", 5)
    if st.sidebar.button("Refresh"):
        st.session_state.auctions = api.get_auctions(api.get_connected_realm_id(realm))
        st.session_state.multi_auctions = fetch_multi_auctions(api, ["whitemane", "mankrik", "atiesh"])
        st.rerun()

    api = BlizzardAPI(client_id, client_secret)
    Database.init_db()
    auctions = st.session_state.get('auctions')
    multi_auctions = st.session_state.get('multi_auctions', {})

    if not auctions: return

    # Tabs (old market/chart in first, new in others)
    tabs = st.tabs(["Market & Chart", "Sniping", "Vendor Flips", "Farms", "Arb", "Posting", "Demand", "Health", "News", "Backtest", "Portfolio"])

    with tabs[0]:
        # Old Market Summary
        results = []
        for iid in [10620, 13463, 12360]:
            stats = AuctionAnalyzer.analyze_item(auctions, iid)
            if stats:
                old_p = Database.get_recent_price(iid, api.get_connected_realm_id(realm))
                change = ((stats['avg'] - old_p) / old_p * 100) if old_p else 0
                change_class = "positive" if change > 0 else "negative"
                results.append({
                    'Item': api.get_item_details(iid)['name'],
                    'Min': format_gold(stats['min']),
                    'Avg': format_gold(stats['avg']),
                    'Max': format_gold(stats['max']),
                    'Volume': stats['volume'],
                    '% Change': f"<span class='{change_class}'>{change:+.1f}%</span>"
                })
        if results: st.markdown(pd.DataFrame(results).to_html(escape=False), unsafe_allow_html=True)

        # Old Chart with RSI
        hist = get_item_history(item_id, api.get_connected_realm_id(realm))
        if not hist.empty:
            fig, ax1 = plt.subplots()
            ax1.plot(hist['datetime'], hist['price'], 'lime')
            ax1.set_ylabel('Gold', color='lime')
            _, rsi_df = rsi(item_id, api.get_connected_realm_id(realm))
            if not rsi_df.empty:
                ax2 = ax1.twinx()
                ax2.plot(rsi_df['datetime'], rsi_df['rsi'], 'cyan')
                ax2.set_ylabel('RSI', color='cyan')
                ax2.axhline(70, color='red', ls='--')
                ax2.axhline(30, color='green', ls='--')
            fig.patch.set_facecolor('#000')
            ax1.set_facecolor('#000')
            ax1.tick_params(colors='white')
            ax2.tick_params(colors='white')
            st.pyplot(fig)

    with tabs[1]:  # Sniping
        opps = sniping_opps(auctions, item_id, api.get_connected_realm_id(realm))
        if opps: st.table(opps)
        else: st.info("No snipes found.")

    with tabs[2]:  # Flips
        flips = vendor_flips(auctions, api)
        if flips: st.table(flips)
        else: st.info("No flips.")

    with tabs[3]:  # Farms
        gphs = {k: farm_gph(k, lambda iid: get_unit_price(auctions, iid)) for k in FARMS}
        st.table(pd.DataFrame.from_dict(gphs, orient='index', columns=['GPH']).sort_values('GPH', ascending=False))

    with tabs[4]:  # Arb
        if multi_auctions: st.table(realm_arb(item_id, multi_auctions))
        else: st.info("Refresh for multi-realm.")

    with tabs[5]:  # Posting
        stats = AuctionAnalyzer.analyze_item(auctions, item_id)
        if stats:
            vol = volatility(item_id, api.get_connected_realm_id(realm))
            sugg = post_price(stats, vol)
            st.metric("Suggested Price", format_gold(sugg))

    with tabs[6]:  # Demand
        demand = mat_demand(item_id, auctions, api)
        st.metric("Demand Volume", demand)

    with tabs[7]:  # Health
        health = economy_health(auctions)
        st.json(health)

    with tabs[8]:  # News
        st.table(RECENT_NEWS)

    with tabs[9]:  # Backtest
        bt = backtest_strategy(item_id, api.get_connected_realm_id(realm))
        if not bt.empty: st.line_chart(bt.set_index('datetime'))

    with tabs[10]:  # Portfolio
        pos_json = st.text_area("Positions e.g. [{'item_id':10620, 'qty':100, 'buy_price':8.5}]")
        if pos_json:
            try:
                positions = json.loads(pos_json)
                val = portfolio_value(positions, lambda iid: get_unit_price(auctions, iid))
                st.json(val)
            except: st.error("Invalid JSON.")

    # Old Crafting (always visible)
    st.markdown("---")
    st.subheader("Crafting Calculator")
    recipe = Recipe(recipe_id, api)
    if recipe.data:
        calc = CraftingCalculator(api, auctions)
        profit = calc.calculate_profit(recipe, craft_qty)
        inputs_df = pd.DataFrame(profit['inputs'])
        inputs_df['unit_price_gold'] = inputs_df['unit_price_gold'].apply(format_gold)
        inputs_df['total_cost_gold'] = inputs_df['total_cost_gold'].apply(format_gold)
        st.table(inputs_df[['name', 'qty', 'unit_price_gold', 'total_cost_gold']])
        profit_class = "positive" if profit['profit_gold'] > 0 else "negative"
        st.markdown(f"Total Cost: {format_gold(profit['total_cost_gold'])} | Revenue: {format_gold(profit['revenue_gold'])} | Profit: <span class='{profit_class}'>{format_gold(profit['profit_gold'])} ({profit['margin_pct']:+.1f}%)</span>", unsafe_allow_html=True)
    else: st.info("Invalid recipe.")

if __name__ == "__main__":
    main_ui()
