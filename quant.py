# wow_terminal/quant.py
import pandas as pd
import numpy as np
from .database import Database

def get_item_history(item_id, realm_id, days=30):
    df = Database.get_price_history(item_id, realm_id, days)
    df['price'] = df['avg_price'] / 10000  # to gold
    return df

def rsi(item_id, realm_id, period=14, days=30):
    """Calculate RSI for the item price history."""
    df = get_item_history(item_id, realm_id, days)
    if len(df) < period + 1:
        return None, None  # Not enough data
    
    delta = df['price'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    
    current_rsi = rsi_series.iloc[-1] if not rsi_series.empty else None
    return current_rsi, pd.DataFrame({
        'datetime': df['datetime'],
        'rsi': rsi_series
    }).dropna()

def volatility(item_id, realm_id, days=30):
    df = get_item_history(item_id, realm_id, days)
    return df['price'].pct_change().std() * np.sqrt(252)  # annualized

def moving_averages(item_id, realm_id, short=7, long=30):
    df = get_item_history(item_id, realm_id)
    df['sma_short'] = df['price'].rolling(short).mean()
    df['sma_long'] = df['price'].rolling(long).mean()
    return df[['datetime', 'price', 'sma_short', 'sma_long']]

def correlation(items_dict):  # items_dict = {item_id: realm_id, ...}
    dfs = []
    for item_id, realm_id in items_dict.items():
        df = get_item_history(item_id, realm_id)
        dfs.append(df.set_index('datetime')['price'].rename(str(item_id)))
    return pd.concat(dfs, axis=1).corr()
