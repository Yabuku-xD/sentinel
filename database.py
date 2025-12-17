import sqlite3
import datetime
import time
import random

class Database:
    def __init__(self, db_path="portfolio.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                balance REAL,
                position_size INTEGER,
                signal TEXT,
                actual_movement INTEGER,
                pnl REAL
            )
        ''')
        c.execute('SELECT count(*) FROM portfolio')
        if c.fetchone()[0] == 0:
            initial_balance = 10000.0
            c.execute('INSERT INTO portfolio (timestamp, balance, position_size, signal, actual_movement, pnl) VALUES (?, ?, ?, ?, ?, ?)',
                      (datetime.datetime.now().isoformat(), initial_balance, 0, 'INIT', 0, 0.0))
        conn.commit()
        conn.close()

    def log_trade(self, signal, actual_label, pnl_change=0):
        retries = 3
        while retries > 0:
            try:
                conn = sqlite3.connect(self.db_path, timeout=10) 
                c = conn.cursor()
                
                c.execute('SELECT balance, position_size FROM portfolio ORDER BY id DESC LIMIT 1')
                last_row = c.fetchone()
                current_balance = last_row[0] if last_row else 10000.0
                
                market_move_pct = random.uniform(0.005, 0.015) 
                gross_profit = 10000.0 * market_move_pct 
                
                commission = 2.0 
                
                if signal == 'BUY':
                    if actual_label == 1:
                        profit = gross_profit - commission 
                    else:
                        profit = -gross_profit - commission 
                elif signal == 'SELL':
                    if actual_label == 0:
                        profit = gross_profit - commission 
                    else:
                        profit = -gross_profit - commission 
                
                new_balance = current_balance + profit
                
                c.execute('INSERT INTO portfolio (timestamp, balance, position_size, signal, actual_movement, pnl) VALUES (?, ?, ?, ?, ?, ?)',
                          (datetime.datetime.now().isoformat(), new_balance, 0, signal, actual_label, profit))
                
                conn.commit()
                conn.close()
                return new_balance
            except sqlite3.OperationalError as e:
                retries -= 1
                if retries == 0:
                    print(f"DB Error after retries: {e}")
                    raise e
                time.sleep(0.5)
