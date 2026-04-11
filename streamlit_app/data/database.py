import sqlite3
import pandas as pd
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "history.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prices 
                 (ticker TEXT, date TEXT, close REAL, UNIQUE(ticker, date) ON CONFLICT IGNORE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS financials 
                 (ticker TEXT, date TEXT, data_json TEXT, UNIQUE(ticker, date) ON CONFLICT REPLACE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS paper_port 
                 (ticker TEXT, date_added TEXT, weight REAL, entry_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS paper_history 
                 (date TEXT, port_value REAL)''')
    conn.commit()
    conn.close()

def save_prices(df: pd.DataFrame):
    if df.empty: return
    conn = get_connection()
    df.to_sql('prices', conn, if_exists='append', index=False)
    conn.close()

def save_financials(ticker: str, results: list):
    conn = get_connection()
    c = conn.cursor()
    for row in results:
        c.execute("INSERT INTO financials (ticker, date, data_json) VALUES (?, ?, ?)",
                  (ticker, row['date'], json.dumps(row)))
    conn.commit()
    conn.close()

def get_price_history(ticker: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT date, close FROM prices WHERE ticker = ? ORDER BY date ASC", conn, params=(ticker,))
    conn.close()
    return df

def get_financial_history(ticker: str) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT data_json FROM financials WHERE ticker = ? ORDER BY date DESC", (ticker,))
    rows = c.fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows]

# Paper functions
def update_paper_portfolio(holdings: list):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM paper_port")
    for h in holdings:
         c.execute("INSERT INTO paper_port (ticker, date_added, weight, entry_price) VALUES (?, ?, ?, ?)",
                   (h['ticker'], h['date'], h['weight'], h['entry_price']))
    conn.commit()
    conn.close()

init_db()
