import asyncio
import aiohttp
import logging
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import yfinance as yf
import feedparser

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}'
)
logger = logging.getLogger("RealTimeEngine")

# --- Architecture Components ---

@dataclass
class MarketEvent:
    timestamp: datetime
    type: str # 'NEWS', 'PRICE', 'SYSTEM'
    data: Dict[str, Any]

class CircuitBreaker:
    """
    Prevents cascading failures when external APIs are down or slow.
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED" # CLOSED (Normal), OPEN (Broken), HALF-OPEN (Testing)

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
        return True # HALF-OPEN

class AsyncDataIngestion:
    """
    Handles concurrent fetching of data from multiple sources.
    """
    def __init__(self, event_queue: asyncio.Queue):
        self.event_queue = event_queue
        self.session = None
        self.rss_circuit = CircuitBreaker()
        self.price_circuit = CircuitBreaker()
        self.seen_headlines = set()

    async def start(self):
        self.session = aiohttp.ClientSession()
        logger.info(json.dumps({"event": "INGESTION_STARTED"}))

    async def stop(self):
        if self.session:
            await self.session.close()

    async def fetch_news(self):
        """Async fetch of RSS feed"""
        if not self.rss_circuit.can_request():
            return

        url = "https://news.google.com/rss/headlines/section/topic/BUSINESS"
        try:
            # Note: feedparser is synchronous, in a real high-perf app we'd use an async XML parser
            # or offload to a thread. For now, we simulate async fetch.
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
        """Async fetch of price data"""
        # In a real app, this would use a websocket connection to Polygon/Alpaca
        if not self.price_circuit.can_request():
            return

        try:
            # Simulating async non-blocking IO call
            # yfinance is blocking, so we run it in an executor
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

class ExecutionEngine:
    """
    Abstraction layer for order execution.
    Allows swapping 'Paper Trading' for 'Live Broker' easily.
    """
    def __init__(self):
        self.positions = {}
        self.balance = 10000.0

    async def execute_order(self, signal: str, confidence: float, price: float):
        """
        Executes an order asynchronously.
        """
        logger.info(json.dumps({
            "event": "ORDER_SUBMITTED", 
            "signal": signal, 
            "confidence": confidence,
            "price": price
        }))
        
        # Simulate network latency for execution
        await asyncio.sleep(0.5)
        
        # Simple execution logic
        if signal == "BUY":
            self.balance -= price
            self.positions["^DJI"] = self.positions.get("^DJI", 0) + 1
        elif signal == "SELL":
            self.balance += price
            self.positions["^DJI"] = self.positions.get("^DJI", 0) - 1
            
        logger.info(json.dumps({
            "event": "ORDER_FILLED", 
            "new_balance": self.balance,
            "positions": self.positions
        }))

class FeedbackLoop:
    """
    Stores predictions and checks later if they were correct to update the model.
    This enables 'Online Learning' in a live environment.
    """
    def __init__(self, validation_window_seconds: int = 300):
        self.pending_predictions = [] # List of (timestamp, features, predicted_signal, entry_price)
        self.validation_window = validation_window_seconds

    def record_prediction(self, features: dict, signal: str, price: float):
        self.pending_predictions.append({
            "timestamp": datetime.now(),
            "features": features,
            "signal": signal,
            "entry_price": price
        })

    def check_outcomes(self, current_price: float) -> List[Dict]:
        """
        Returns a list of completed learning examples: {'features': ..., 'label': ...}
        """
        ready_to_learn = []
        remaining = []
        
        cutoff_time = datetime.now() - timedelta(seconds=self.validation_window)
        
        for pred in self.pending_predictions:
            if pred['timestamp'] < cutoff_time:
                # Time to validate!
                # Label logic: 1 if profitable, 0 if not
                is_profitable = False
                if pred['signal'] == "BUY":
                    is_profitable = current_price > pred['entry_price']
                elif pred['signal'] == "SELL":
                    is_profitable = current_price < pred['entry_price']
                
                label = 1 if is_profitable else 0
                ready_to_learn.append({"features": pred['features'], "label": label})
                
                logger.info(json.dumps({
                    "event": "LEARNING_UPDATE", 
                    "signal": pred['signal'], 
                    "entry": pred['entry_price'], 
                    "exit": current_price,
                    "label": label
                }))
            else:
                remaining.append(pred)
                
        self.pending_predictions = remaining
        return ready_to_learn

class StrategyEngine:
    """
    Holds the AI models.
    """
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
        # Simple logic for demo
        prob = self.learner.predict_proba_one({'sentiment': sentiment_score}).get(1, 0.5)
        if prob > 0.6: return "BUY", prob
        if prob < 0.4: return "SELL", prob
        return "HOLD", prob

    def learn(self, features: dict, label: int):
        self.learner.learn_one(features, label)

class RealTimeCore:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.ingestion = AsyncDataIngestion(self.queue)
        self.execution = ExecutionEngine()
        self.strategy = None
        self.feedback = FeedbackLoop(validation_window_seconds=60) # Short window for demo
        self.running = False

    async def run(self):
        self.running = True
        await self.ingestion.start()
        
        # Load heavy models in executor to not block the loop
        loop = asyncio.get_event_loop()
        self.strategy = await loop.run_in_executor(None, StrategyEngine)

        # Create background tasks
        ingest_task = asyncio.create_task(self.ingest_loop())
        process_task = asyncio.create_task(self.process_loop())
        
        logger.info("System Online. Waiting for events...")
        
        try:
            await asyncio.gather(ingest_task, process_task)
        except asyncio.CancelledError:
            logger.info("System shutting down...")
        finally:
            await self.ingestion.stop()

    async def ingest_loop(self):
        """Loop to constantly fetch data based on intervals"""
        while self.running:
            # We can run these concurrently
            await asyncio.gather(
                self.ingestion.fetch_news(),
                self.ingestion.fetch_price()
            )
            # Fetch rate limit / polling interval
            await asyncio.sleep(5) 

    async def process_loop(self):
        """Event Processing Loop"""
        while self.running:
            event = await self.queue.get()
            
            if event.type == "NEWS":
                sentiment = self.strategy.analyze_sentiment(event.data['title'])
                logger.info(json.dumps({"event": "SENTIMENT_ANALYSIS", "score": sentiment, "title": event.data['title'][:30] + "..."}))
                self.strategy.latest_sentiment = sentiment
                
            elif event.type == "PRICE":
                current_price = event.data['price']
                
                # 1. Check if we can learn from past trades
                learning_batch = self.feedback.check_outcomes(current_price)
                for example in learning_batch:
                    self.strategy.learn(example['features'], example['label'])
                
                # 2. Make new prediction
                signal, conf = self.strategy.predict(self.strategy.latest_sentiment)
                
                if signal != "HOLD":
                    # Record this prediction so we can learn from it later
                    features = {'sentiment': self.strategy.latest_sentiment}
                    self.feedback.record_prediction(features, signal, current_price)
                    
                    await self.execution.execute_order(signal, conf, current_price)
            
            self.queue.task_done()

if __name__ == "__main__":
    system = RealTimeCore()
    try:
        asyncio.run(system.run())
    except KeyboardInterrupt:
        pass
