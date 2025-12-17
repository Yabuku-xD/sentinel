import unittest
import sqlite3
import os
from unittest.mock import patch
from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_portfolio.db"
        self.db = Database(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except PermissionError:
                pass 

    @patch('random.uniform')
    def test_log_trade_buy_profit(self, mock_uniform):
        mock_uniform.return_value = 0.01
        
        new_balance = self.db.log_trade("BUY", 1)
        
        self.assertAlmostEqual(new_balance, 10098.0)
        
        conn = sqlite3.connect(self.test_db)
        c = conn.cursor()
        c.execute("SELECT balance, pnl FROM portfolio ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        
        self.assertAlmostEqual(row[0], 10098.0)
        self.assertAlmostEqual(row[1], 98.0)

    @patch('random.uniform')
    def test_log_trade_buy_loss(self, mock_uniform):
        mock_uniform.return_value = 0.01
        
        new_balance = self.db.log_trade("BUY", 0)
        
        self.assertAlmostEqual(new_balance, 9898.0)

    @patch('random.uniform')
    def test_log_trade_sell_profit(self, mock_uniform):
        mock_uniform.return_value = 0.01
        
        new_balance = self.db.log_trade("SELL", 0)
        self.assertAlmostEqual(new_balance, 10098.0)

if __name__ == '__main__':
    unittest.main()
