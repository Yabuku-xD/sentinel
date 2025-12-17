import time
import argparse
import torch
from transformers import pipeline
from river import compose, linear_model, preprocessing, metrics
from data_loader import DataLoader
from live_loader import LiveLoader
from database import Database

def run_engine(mode='replay'):
    print(f"Initializing Engine in {mode.upper()} mode...")
    
    print("Loading FinBERT Model...")
    sentiment_pipeline = pipeline("text-classification", model="ProsusAI/finbert", device=-1)
    
    print("Initializing Online Learner (River)...")
    model = compose.Pipeline(
        preprocessing.StandardScaler(),
        linear_model.LogisticRegression()
    )
    metric = metrics.Accuracy()
    
    if mode == 'live':
        loader = LiveLoader()
        delay = 60 
    else:
        loader = DataLoader()
        delay = 0.5 
        
    db = Database()
    stream_source = loader.stream_live(poll_interval=delay) if mode == 'live' else loader.stream_headlines(delay=delay)

    print("Starting Stream...")
    
    for day_data in stream_source:
        date = day_data['Date']
        label = day_data['Label']
        headlines = day_data['Headlines']
        
        valid_headlines = headlines[:5]
        if not valid_headlines: continue

        results = sentiment_pipeline(valid_headlines)
        
        daily_sentiment_accum = 0.0
        for res in results:
            score = res['score']
            if res['label'] == 'positive': daily_sentiment_accum += score
            elif res['label'] == 'negative': daily_sentiment_accum -= score
            
        avg_sentiment = daily_sentiment_accum / len(valid_headlines)
        
        features = {'sentiment': avg_sentiment}
        
        try:
            prediction_score = model.predict_proba_one(features).get(1, 0.5)
        except:
            prediction_score = 0.5
            
        signal = "HOLD"
        if prediction_score > 0.55:
            signal = "BUY"
        elif prediction_score < 0.45:
            signal = "SELL"
            
        if label is None:
            print(f"[{date}] LIVE Signal: {signal} (Model Conf: {prediction_score:.2f})")
            db.log_trade(signal, -1) 
        else:
            if signal != "HOLD":
                new_bal = db.log_trade(signal, label)
                print(f"[{date}] Signal: {signal} (Conf: {prediction_score:.2f}) | Actual: {label} | Bal: ${new_bal:.2f}")
            else:
                print(f"[{date}] Signal: HOLD (Conf: {prediction_score:.2f}) | Actual: {label} | Skipped")
                
            model.learn_one(features, label)
            metric.update(label, prediction_score > 0.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['replay', 'live'], default='replay', help="Run in 'replay' or 'live' mode")
    args = parser.parse_args()
    
    run_engine(mode=args.mode)
