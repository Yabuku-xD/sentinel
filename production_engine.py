import asyncio
import aiohttp
import logging
import json
import time
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import yfinance as yf
import feedparser

from config import Config
from risk_manager import RiskManager
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}'
)
logger = logging.getLogger("RealTimeEngine")

@dataclass
class MarketEvent:
    timestamp: datetime
    type: str 
    data: Dict[str, Any]

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED" 

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = datetime.now()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(json.dumps({"event": "CIRCUIT_OPENED", "reason": "Failure threshold reached"}))

    def record_success(self):
        if self.state == "HALF-OPEN":
            self.state = "CLOSED"
            self.failures = 0
            logger.info(json.dumps({"event": "CIRCUIT_CLOSED", "reason": "Service recovered"}))
        elif self.state == "CLOSED":
            self.failures = 0

    def can_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout:
                self.state = "HALF-OPEN"
                return True
            return False
        return True 

class DataIngestionBase:
    def __init__(self, event_queue: asyncio.Queue):
        self.event_queue = event_queue
    
    async def start(self): pass
    async def stop(self): pass
    async def ingest_loop(self): pass

class LiveIngestion(DataIngestionBase):
    def __init__(self, event_queue: asyncio.Queue):
        super().__init__(event_queue)
        self.session = None
        self.rss_circuit = CircuitBreaker()
        self.price_circuit = CircuitBreaker()
        self.seen_headlines = set()

    async def start(self):
        self.session = aiohttp.ClientSession()
        logger.info(json.dumps({"event": "INGESTION_STARTED", "mode": "LIVE"}))

    async def stop(self):
        if self.session:
            await self.session.close()

    async def fetch_news(self):
        if not self.rss_circuit.can_request():
            return

        url = "https://news.google.com/rss/headlines/section/topic/BUSINESS"
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    self.rss_circuit.record_success()
                    
                    new_events = []
                    for entry in feed.entries[:5]:
                        if entry.title not in self.seen_headlines:
                            self.seen_headlines.add(entry.title)
                            new_events.append(MarketEvent(
                                timestamp=datetime.now(),
                                type="NEWS",
                                data={"title": entry.title, "link": entry.link}
                            ))
                    
                    for event in new_events:
                        await self.event_queue.put(event)
                else:
                    self.rss_circuit.record_failure()
        except Exception as e:
            logger.error(json.dumps({"event": "FETCH_ERROR", "source": "news", "error": str(e)}))
            self.rss_circuit.record_failure()

    async def fetch_price(self):
        if not self.price_circuit.can_request():
            return

        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, lambda: yf.Ticker("^DJI"))
            price = await loop.run_in_executor(None, lambda: ticker.fast_info['last_price'])
            
            self.price_circuit.record_success()
            await self.event_queue.put(MarketEvent(
                timestamp=datetime.now(),
                type="PRICE",
                data={"symbol": "^DJI", "price": price}
            ))
        except Exception as e:
            logger.error(json.dumps({"event": "FETCH_ERROR", "source": "price", "error": str(e)}))
            self.price_circuit.record_failure()

    async def ingest_loop(self):
        while True:
            await asyncio.gather(
                self.fetch_news(),
                self.fetch_price()
            )
            await asyncio.sleep(60)

class ReplayIngestion(DataIngestionBase):
    def __init__(self, event_queue: asyncio.Queue, csv_path="Combined_News_DJIA.csv"):
        super().__init__(event_queue)
        self.csv_path = csv_path
        self.df = pd.read_csv(self.csv_path)
        logger.info(json.dumps({"event": "INGESTION_STARTED", "mode": "REPLAY", "days": len(self.df)}))

    async def ingest_loop(self):
        print(f"Starting replay of {len(self.df)} days...")
        base_price = 10000.0
        
        for index, row in self.df.iterrows():
            headlines = []
            for i in range(1, 26):
                col_name = f"Top{i}"
                if pd.notna(row[col_name]):
                    headlines.append(str(row[col_name]).strip())
            
            for title in headlines[:5]:
                await self.event_queue.put(MarketEvent(
                    timestamp=datetime.now(),
                    type="NEWS",
                    data={"title": title}
                ))
            
            await self.event_queue.put(MarketEvent(
                timestamp=datetime.now(),
                type="PRICE",
                data={"symbol": "^DJI", "price": base_price}
            ))
            
            await asyncio.sleep(0.1)
            
            label = int(row["Label"])
            move = base_price * 0.01 if label == 1 else -base_price * 0.01
            new_price = base_price + move
            
            await self.event_queue.put(MarketEvent(
                timestamp=datetime.now(),
                type="PRICE",
                data={"symbol": "^DJI", "price": new_price}
            ))
            
            base_price = new_price
            await asyncio.sleep(0.5) 

class ExecutionEngine:
    def __init__(self):
        self.db = Database(Config.DB_PATH)
        self.balance = self.db.get_latest_balance()
        # Load open positions from DB for persistence
        self.positions = {} 
        for pos in self.db.get_positions():
            # pos is a Row object or dict depending on factory
            self.positions[pos['symbol']] = {
                'symbol': pos['symbol'],
                'quantity': pos['quantity'],
                'entry_price': pos['entry_price'],
                'stop_loss': pos['stop_loss'],
                'take_profit': pos['take_profit']
            }
        self.risk_manager = RiskManager(self.balance)

    async def execute_order(self, signal: str, confidence: float, price: float):
        decision = self.risk_manager.validate_signal(signal, confidence, price, self.balance)
        
        if not decision:
            logger.info(json.dumps({
                "event": "ORDER_REJECTED", 
                "reason": "Risk Management", 
                "signal": signal,
                "confidence": confidence
            }))
            return

        logger.info(json.dumps({
            "event": "ORDER_SUBMITTED", 
            "signal": decision.signal, 
            "size": decision.size,
            "stop_loss": decision.stop_loss,
            "price": price
        }))
        
        await asyncio.sleep(0.1)
        
        cost = decision.size * price
        symbol = "^DJI" # Default for this system
        
        if decision.signal == "BUY":
            if self.balance < cost: return
            
            self.balance -= cost
            
            # Calculate new average entry if position exists
            current_pos = self.positions.get(symbol, {'quantity': 0, 'entry_price': 0.0})
            current_qty = current_pos['quantity']
            current_avg = current_pos['entry_price']
            
            new_qty = current_qty + decision.size
            if new_qty > 0:
                new_avg = ((current_avg * current_qty) + cost) / new_qty
            else:
                new_avg = price
                
            self.positions[symbol] = {
                'symbol': symbol,
                'quantity': new_qty,
                'entry_price': new_avg,
                'stop_loss': decision.stop_loss,
                'take_profit': decision.take_profit
            }
            
            self.db.add_position(symbol, new_qty, new_avg, decision.stop_loss, decision.take_profit)
            
        elif decision.signal == "SELL":
            # Treat SELL as closing the position
            await self.close_position(symbol, price, "SIGNAL_SELL")
            
        logger.info(json.dumps({
            "event": "ORDER_FILLED", 
            "new_balance": self.balance,
            "positions": self.positions
        }))

    async def monitor_risk(self, current_price: float):
        """Checks all open positions against Stop Loss and Take Profit levels."""
        to_close = []
        for symbol, pos in self.positions.items():
            if pos['quantity'] > 0:
                if current_price <= pos['stop_loss']:
                    to_close.append((symbol, "STOP_LOSS"))
                elif current_price >= pos['take_profit']:
                    to_close.append((symbol, "TAKE_PROFIT"))
        
        for symbol, reason in to_close:
            await self.close_position(symbol, current_price, reason)

    async def close_position(self, symbol: str, price: float, reason: str):
        pos = self.positions.get(symbol)
        if not pos: return
        
        qty = pos['quantity']
        if qty == 0: return

        revenue = qty * price
        self.balance += revenue
        
        pnl = revenue - (pos['entry_price'] * qty)
        
        # Log to DB using new signature
        self.db.log_trade(reason, symbol, qty, pos['entry_price'], price, pnl)
        self.db.remove_position(symbol)
        
        del self.positions[symbol]
        
        logger.info(json.dumps({
            "event": "POSITION_CLOSED", 
            "symbol": symbol, 
            "reason": reason, 
            "pnl": pnl,
            "final_balance": self.balance
        }))

    def log_completed_trade(self, signal: str, label: int):
        # Deprecated: The system now logs trades on close_position.
        # Keeping for compatibility with FeedbackLoop if needed, but FeedbackLoop calls this.
        # FeedbackLoop tracks *predictions*, not necessarily *executed trades* (pnl).
        # We can leave this empty or update it to just log prediction accuracy.
        pass

class FeedbackLoop:
    def __init__(self, execution_engine: ExecutionEngine, validation_window_seconds: int = 300):
        self.pending_predictions = [] 
        self.validation_window = validation_window_seconds
        self.execution = execution_engine

    def record_prediction(self, features: dict, signal: str, price: float):
        self.pending_predictions.append({
            "timestamp": datetime.now(),
            "features": features,
            "signal": signal,
            "entry_price": price
        })

    def check_outcomes(self, current_price: float) -> List[Dict]:
        ready_to_learn = []
        remaining = []
        
        for pred in self.pending_predictions:
            price_change_pct = (current_price - pred['entry_price']) / pred['entry_price']
            
            resolved = False
            label = None
            
            if abs(price_change_pct) > 0.005: 
                resolved = True
                if pred['signal'] == "BUY":
                    label = 1 if current_price > pred['entry_price'] else 0
                else: 
                    label = 1 if current_price < pred['entry_price'] else 0
            
            time_diff = (datetime.now() - pred['timestamp']).total_seconds()
            if time_diff > self.validation_window:
                resolved = True
                label = 0 
                
            if resolved:
                ready_to_learn.append({"features": pred['features'], "label": label})
                
                self.execution.log_completed_trade(pred['signal'], label)
                
                logger.info(json.dumps({
                    "event": "PREDICTION_VALIDATED", 
                    "signal": pred['signal'], 
                    "entry": pred['entry_price'], 
                    "exit": current_price,
                    "pnl_pct": price_change_pct,
                    "label": label
                }))
            else:
                remaining.append(pred)
                
        self.pending_predictions = remaining
        return ready_to_learn

class StrategyEngine:
    def __init__(self):
        from transformers import pipeline
        from river import compose, linear_model, preprocessing
        
        logger.info("Loading AI Models...")
        self.sentiment_pipeline = pipeline("text-classification", model="ProsusAI/finbert", device=-1)
        self.learner = compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LogisticRegression()
        )
        self.latest_sentiment = 0.5

    def analyze_sentiment(self, text: str) -> float:
        result = self.sentiment_pipeline(text)[0]
        score = result['score'] if result['label'] == 'positive' else -result['score']
        return score

    def predict(self, sentiment_score: float) -> str:
        prob = self.learner.predict_proba_one({'sentiment': sentiment_score}).get(1, 0.5)
        if prob > 0.6: return "BUY", prob
        if prob < 0.4: return "SELL", prob
        return "HOLD", prob

    def learn(self, features: dict, label: int):
        self.learner.learn_one(features, label)

class RealTimeCore:
    def __init__(self, mode='replay'):
        self.queue = asyncio.Queue()
        self.mode = mode
        
        if self.mode == 'live':
            self.ingestion = LiveIngestion(self.queue)
            self.validation_window = 300 
        else:
            self.ingestion = ReplayIngestion(self.queue)
            self.validation_window = 2 
            
        self.execution = ExecutionEngine()
        self.strategy = None
        self.feedback = FeedbackLoop(self.execution, validation_window_seconds=self.validation_window)
        self.running = False

    async def run(self):
        self.running = True
        await self.ingestion.start()
        
        loop = asyncio.get_event_loop()
        self.strategy = await loop.run_in_executor(None, StrategyEngine)

        ingest_task = asyncio.create_task(self.ingestion.ingest_loop())
        process_task = asyncio.create_task(self.process_loop())
        
        logger.info(f"System Online ({self.mode.upper()}). Waiting for events...")
        
        try:
            await asyncio.gather(ingest_task, process_task)
        except asyncio.CancelledError:
            logger.info("System shutting down...")
        finally:
            await self.ingestion.stop()

    async def process_loop(self):
        while self.running:
            event = await self.queue.get()
            
            if event.type == "NEWS":
                sentiment = self.strategy.analyze_sentiment(event.data['title'])
                logger.info(json.dumps({"event": "SENTIMENT_ANALYSIS", "score": sentiment, "title": event.data['title'][:30] + "..."}))
                self.strategy.latest_sentiment = sentiment
                
            elif event.type == "PRICE":
                current_price = event.data['price']
                
                # Active Risk Check (Crucial for Real-Time)
                await self.execution.monitor_risk(current_price)
                
                learning_batch = self.feedback.check_outcomes(current_price)
                for example in learning_batch:
                    self.strategy.learn(example['features'], example['label'])
                
                signal, conf = self.strategy.predict(self.strategy.latest_sentiment)
                
                if signal != "HOLD":
                    features = {'sentiment': self.strategy.latest_sentiment}
                    
                    self.feedback.record_prediction(features, signal, current_price)
                    
                    await self.execution.execute_order(signal, conf, current_price)
            
            self.queue.task_done()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['replay', 'live'], default='replay', help="Run in 'replay' or 'live' mode")
    args = parser.parse_args()
    
    system = RealTimeCore(mode=args.mode)
    try:
        asyncio.run(system.run())
    except KeyboardInterrupt:
        pass
