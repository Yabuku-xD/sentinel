import pandas as pd
import time
import json
from datetime import datetime

class DataLoader:
    def __init__(self, csv_path="Combined_News_DJIA.csv"):
        self.csv_path = csv_path
        self.df = pd.read_csv(self.csv_path)
        
    def stream_headlines(self, delay=1.0):
        print(f"Starting replay of {len(self.df)} days...")
        while True: 
            for index, row in self.df.iterrows():
                headlines = []
                for i in range(1, 26):
                    col_name = f"Top{i}"
                    if pd.notna(row[col_name]):
                        headlines.append(str(row[col_name]).strip())
                
                data = {
                    "Date": row["Date"],
                    "Label": int(row["Label"]),
                    "Headlines": headlines,
                    "timestamp": datetime.now().isoformat() 
                }
                
                yield data
                time.sleep(delay)
