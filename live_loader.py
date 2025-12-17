import feedparser
import time
from datetime import datetime
import yfinance as yf

class LiveLoader:
    def __init__(self):
        self.rss_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS"
        self.last_seen_titles = set()
        
    def fetch_news(self):
        feed = feedparser.parse(self.rss_url)
        headlines = []
        
        for entry in feed.entries[:10]: 
            title = entry.title
            if title not in self.last_seen_titles:
                headlines.append(title)
                self.last_seen_titles.add(title)
                
        return headlines

    def get_market_status(self):
        try:
            ticker = yf.Ticker("^DJI")
            price = ticker.fast_info['last_price']
            return price
        except:
            return 0.0

    def stream_live(self, poll_interval=60):
        print(f"Starting LIVE feed from {self.rss_url}...")
        
        while True:
            headlines = self.fetch_news()
            price = self.get_market_status()
            timestamp = datetime.now().isoformat()
            
            if headlines:
                print(f"[{timestamp}] Fetched {len(headlines)} new headlines.")
                
                data = {
                    "Date": timestamp,
                    "Label": None, 
                    "Headlines": headlines,
                    "timestamp": timestamp,
                    "market_price": price
                }
                
                yield data
            else:
                print(f"[{timestamp}] No new news. Market Price: {price}")
                
            time.sleep(poll_interval)
