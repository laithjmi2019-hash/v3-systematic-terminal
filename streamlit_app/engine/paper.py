from data.database import get_connection, update_paper_portfolio
import pandas as pd

def get_live_holdings():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM paper_port", conn)
    conn.close()
    return df.to_dict('records')

def execute_rebalance(holdings):
    # holdings format: [{"ticker": "AAPL", "date": "2024-01-01", "weight": 0.2, "entry_price": 150}]
    update_paper_portfolio(holdings)
    return True
