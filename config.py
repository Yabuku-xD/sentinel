import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 10000.0))
    COMMISSION_PER_TRADE = float(os.getenv("COMMISSION_PER_TRADE", 2.0))
    SLIPPAGE_PCT_MIN = float(os.getenv("SLIPPAGE_PCT_MIN", 0.0005))
    SLIPPAGE_PCT_MAX = float(os.getenv("SLIPPAGE_PCT_MAX", 0.0015))
    RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", 0.02))
    STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", 0.02))
    TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", 0.04))
    
    DB_PATH = os.getenv("DB_PATH", "portfolio.db")
