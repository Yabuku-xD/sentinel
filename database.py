import sqlite3
import datetime
import time
import logging

logger = logging.getLogger("Database")

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
                signal TEXT,
                symbol TEXT,
                quantity INTEGER,
                entry_price REAL,
                exit_price REAL,
                pnl REAL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity INTEGER,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                timestamp TEXT
            )
        ''')

        c.execute('SELECT count(*) FROM portfolio')
        if c.fetchone()[0] == 0:
            initial_balance = 10000.0
            c.execute('''INSERT INTO portfolio 
                (timestamp, balance, signal, symbol, quantity, entry_price, exit_price, pnl) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (datetime.datetime.now().isoformat(), initial_balance, 'INIT', 'CASH', 0, 0.0, 0.0, 0.0))
        
        conn.commit()
        conn.close()

    def get_latest_balance(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT balance FROM portfolio ORDER BY id DESC LIMIT 1')
            row = c.fetchone()
            return row[0] if row else 10000.0

    def add_position(self, symbol, quantity, entry_price, stop_loss, take_profit):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO positions (symbol, quantity, entry_price, stop_loss, take_profit, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (symbol, quantity, entry_price, stop_loss, take_profit, datetime.datetime.now().isoformat()))
            conn.commit()

    def remove_position(self, symbol):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM positions WHERE symbol = ?', (symbol,))
            conn.commit()

    def get_positions(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM positions')
            return [dict(row) for row in c.fetchall()]

    def log_trade(self, signal, symbol, quantity, entry_price, exit_price, pnl):
        retries = 3
        while retries > 0:
            try:
                conn = sqlite3.connect(self.db_path, timeout=10) 
                c = conn.cursor()
                
                current_balance = self.get_latest_balance()
                new_balance = current_balance + pnl
                
                c.execute('''INSERT INTO portfolio 
                    (timestamp, balance, signal, symbol, quantity, entry_price, exit_price, pnl) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (datetime.datetime.now().isoformat(), new_balance, signal, symbol, quantity, entry_price, exit_price, pnl))
                
                conn.commit()
                conn.close()
                return new_balance
            except sqlite3.OperationalError as e:
                retries -= 1
                if retries == 0:
                    logger.error(f"DB Error after retries: {e}")
                    raise e
                time.sleep(0.5)
