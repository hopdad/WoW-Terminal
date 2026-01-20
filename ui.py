# wow_terminal/ui.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from .api import BlizzardAPI
from .database import Database
from .analyzer import AuctionAnalyzer
from .calculator import Recipe, CraftingCalculator, format_gold, print_crafting_flow  # Note: print_crafting_flow is console; we'll adapt

# Bloomberg-like theme: Dark background, green/red accents
st.markdown("""
    <style>
        .reportview-container {
            background: #000000;
            color: #FFFFFF;
        }
        .sidebar .sidebar-content {
            background: #111111;
        }
        table {
            background: #000000;
            color: #FFFFFF;
            border: 1px solid #333333;
        }
        th {
            background: #222222;
            color: #FFFFFF;
        }
        td {
            border: 1px solid #333333;
        }
        .positive { color: #00FF00; }  /* Green up */
        .negative { color: #FF0000; }  /* Red down */
        .stButton>button {
            background: #004400;
            color: #FFFFFF;
        }
    </style>
""", unsafe_allow_html=True)

def main_ui():
    st.title("WoW Classic Economy Terminal")
    st.markdown("---")  # Bloomberg-like section dividers

    # Sidebar for config (like Bloomberg's command line)
    st.sidebar.header("Controls")
    client_id = st.sidebar.text_input("Client ID", value="YOUR_CLIENT_ID")
    client_secret = st.sidebar.text_input("Client Secret", value="YOUR_CLIENT_SECRET", type="password")
    selected_realm = st.sidebar.selectbox("Realm", ["whitemane", "mankrik", "atiesh"])
    selected_item_id = st.sidebar.selectbox("Item", {10620: "Thorium Ore", 13463: "Dreamfoil"})
    recipe_id = st.sidebar.number_input("Recipe ID", value=17187)  # Transmute Arcanite
    craft_qty = st.sidebar.number_input("Craft Quantity", value=5, min_value=1)
    refresh_button = st.sidebar.button("Refresh Data")

    if client_id == "YOUR_CLIENT_ID" or client_secret == "YOUR_CLIENT_SECRET":
        st.warning("Enter your Blizzard API credentials in the sidebar.")
        return

    api = BlizzardAPI(client_id, client_secret)
    Database.init_db()

    # Fetch realm ID
    realm_id = api.get_connected_realm_id(selected_realm)
    if not realm_id:
        st.error(f"Realm {selected_realm} not found.")
        return

    # Multi-panel layout like Bloomberg (columns)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Market Summary")
        try:
            auctions_data = api.get_auctions(realm_id)
            last_mod = datetime.fromtimestamp(auctions_data['lastModified']/1000)
            st.markdown(f"Last Updated: {last_mod}")

            results = []
            for item_id, item_name in {10620: "Thorium Ore", 13463: "Dreamfoil"}.items():  # All items
                stats = AuctionAnalyzer.analyze_item(auctions_data, item_id)
                if stats:
                    old_price = Database.get_recent_price(item_id, realm_id)
                    change = ((stats['avg'] - old_price) / old_price * 100) if old_price else 0
                    # Store if refresh
                    if refresh_button:
                        Database.store_price(realm_id, item_id, stats, int(datetime.now().timestamp()))

                    change_class = "positive" if change > 0 else "negative"
                    results.append({
                        'Item': item_name,
                        'Min': format_gold(stats['min']),
                        'Avg': format_gold(stats['avg']),
                        'Max': format_gold(stats['max']),
                        'Volume': stats['volume'],
                        'Listings': stats['listings'],
                        '% Change': f"<span class='{change_class}'>{change:+.1f}%</span>"
                    })

            if results:
                df = pd.DataFrame(results)
                st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                st.info("No auction data available.")
        except Exception as e:
            st.error(f"Error fetching auctions: {e}")

    with col2:
        st.subheader("Price History Chart")
        hist = Database.get_price_history(selected_item_id, realm_id)
        if not hist.empty:
            hist['avg_gold'] = hist['avg_price'] / 10000
            fig, ax = plt.subplots()
            ax.plot(hist['datetime'], hist['avg_gold'], color='lime', label='Avg Price')
            ax.set_facecolor('#000000')
            fig.patch.set_facecolor('#000000')
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['left'].set_color('white')
            ax.yaxis.label.set_color('white')
            ax.xaxis.label.set_color('white')
            ax.set_ylabel('Gold')
            ax.set_xlabel('Date')
            st.pyplot(fig)
        else:
            st.info("No historical data yet. Refresh to populate.")

    st.markdown("---")

    st.subheader("Crafting Profit Calculator")
    if auctions_data:
        recipe = Recipe(recipe_id, api)
        if recipe.data:
            calc = CraftingCalculator(api, auctions_data)
            profit = calc.calculate_profit(recipe, quantity=craft_qty)
            
            # Adapt print_crafting_flow to Streamlit
            st.markdown(f"### {profit['crafted_name']} (x{profit['quantity_crafted']})")
            inputs_df = pd.DataFrame(profit['inputs'])
            inputs_df['unit_price_gold'] = inputs_df['unit_price_gold'].apply(format_gold)
            inputs_df['total_cost_gold'] = inputs_df['total_cost_gold'].apply(format_gold)
            st.table(inputs_df[['name', 'qty', 'unit_price_gold', 'total_cost_gold']])

            profit_class = "positive" if profit['profit_gold'] > 0 else "negative"
            st.markdown(f"""
                Total Cost: {format_gold(profit['total_cost_gold'])}  
                Revenue: {format_gold(profit['revenue_gold'])}  
                Profit: <span class='{profit_class}'>{format_gold(profit['profit_gold'])} ({profit['margin_pct']:+.1f}%)</span>
            """, unsafe_allow_html=True)
            
            if profit['margin_pct'] > 10:
                st.success("Strong opportunity!")
            elif profit['margin_pct'] > 0:
                st.info("Positive margin.")
            else:
                st.warning("Loss or break-even.")
        else:
            st.error("Recipe not found.")
    else:
        st.info("Fetch auctions first.")

if __name__ == "__main__":
    main_ui()
