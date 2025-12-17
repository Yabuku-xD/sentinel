from dataclasses import dataclass
from typing import Optional
from config import Config

@dataclass
class TradeDecision:
    signal: str
    size: int
    stop_loss: float
    take_profit: float

class RiskManager:
    def __init__(self, initial_capital: float = Config.INITIAL_CAPITAL):
        self.capital = initial_capital
        
    def calculate_position_size(self, current_capital: float, price: float, confidence: float) -> int:
        risk_amount = current_capital * Config.RISK_PER_TRADE_PCT
        
        stop_loss_dist = price * Config.STOP_LOSS_PCT
        
        if stop_loss_dist == 0:
            return 0
            
        position_size = int(risk_amount / stop_loss_dist)
        
        max_affordable = int(current_capital / price)
        
        return min(position_size, max_affordable)

    def validate_signal(self, signal: str, confidence: float, current_price: float, current_capital: float) -> Optional[TradeDecision]:
        if signal == "HOLD":
            return None
            
        if confidence < 0.60: 
            return None
            
        size = self.calculate_position_size(current_capital, current_price, confidence)
        
        if size <= 0:
            return None
            
        stop_loss = current_price * (1 - Config.STOP_LOSS_PCT) if signal == "BUY" else current_price * (1 + Config.STOP_LOSS_PCT)
        take_profit = current_price * (1 + Config.TAKE_PROFIT_PCT) if signal == "BUY" else current_price * (1 - Config.TAKE_PROFIT_PCT)
        
        return TradeDecision(
            signal=signal,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

    def check_stop_loss(self, position_type: str, entry_price: float, current_price: float) -> bool:
        if position_type == "LONG":
            return current_price <= entry_price * (1 - Config.STOP_LOSS_PCT)
        elif position_type == "SHORT":
            return current_price >= entry_price * (1 + Config.STOP_LOSS_PCT)
        return False
