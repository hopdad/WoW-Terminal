import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_FILE = 'wow_economy.db'

class Database:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                timestamp INTEGER,
                realm_id INTEGER,
                item_id INTEGER,
                min_price REAL,
                avg_price REAL,
                max_price REAL,
                volume INTEGER,
                PRIMARY KEY (timestamp, realm_id, item_id)
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def store_price(realm_id: int, item_id: int, stats: Dict, timestamp: int):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prices (timestamp, realm_id, item_id, min_price, avg_price, max_price, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, realm_id, item_id, stats['min'], stats['avg'], stats['max'], stats['volume']))
        conn.commit()
        conn.close()

    @staticmethod
    def get_recent_price(item_id: int, realm_id: int, hours: int = 24) -> Optional[float]:
        conn = sqlite3.connect(DB_FILE)
        cutoff = int((datetime.now() - timedelta(hours=hours)).timestamp())
        df = pd.read_sql_query(
            "SELECT avg_price FROM prices WHERE item_id=? AND realm_id=? AND timestamp > ? ORDER BY timestamp DESC LIMIT 1",
            conn, params=(item_id, realm_id, cutoff)
        )
        conn.close()
        return df['avg_price'].iloc[0] if not df.empty else None

    @staticmethod
    def get_price_history(item_id: int, realm_id: int, days: int = 7) -> pd.DataFrame:
        conn = sqlite3.connect(DB_FILE)
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
        df = pd.read_sql_query(
            "SELECT timestamp, avg_price FROM prices WHERE item_id=? AND realm_id=? AND timestamp > ? ORDER BY timestamp",
            conn, params=(item_id, realm_id, cutoff)
        )
        conn.close()
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        return df
