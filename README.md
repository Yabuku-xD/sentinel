# Sentinel - Algorithmic Trading System (Hybrid AI)

See, I’ve been where you are.

You spend a whole weekend fueled by coffee and optimism, coding up a trading bot. You backtest it, and—oh my god—it’s a money printer. The equity curve goes straight up to the right. You start mentally picking out colors for your future Porsche.

Then Monday morning hits. You turn it on live... and the market just shreds it.

Why? Because the market changed. The rules you wrote on Saturday didn't apply on Monday.

That frustration is exactly why I built this Hybrid AI system. I wanted to move away from rigid "If/Then" rules—because let’s be honest, markets are organic. They breathe. They throw tantrums. A static script can’t handle that.

Here is the rundown of a system that actually tries to learn alongside you.

## 🚀 The Big Idea: A Bot That Adapts

Most trading bots are stubborn. They follow a rule like "If sentiment is good, Buy." But what if "good sentiment" stops mattering for a week because everyone is focused on interest rates?

This system isn't static. It’s a **Self-Adapting Signal Engine**.

Think of it less like a calculator and more like a junior trader who sits next to you. It watches the news, makes a prediction, and then—this is the key part—it sees if it was right or wrong. If it messed up, it adjusts its own brain immediately.

### The "Hybrid" Brain (How it Works)
We're mashing up two very different types of AI here to create something capable.

1.  **The Reader (FinBERT):** First, we use HuggingFace’s `FinBERT`. Think of this as the eyes. It reads financial news headlines and extracts the "vibe" (sentiment). But it doesn't just count happy words; it understands financial context. It knows that "profit warnings" are bad, even if the word "profit" usually sounds good.
2.  **The Learner (River):** This is the cool part. We use a library called `River` for something called "**Online Machine Learning**." Normal AI needs to go to "school" (training phase) before it can work. River learns on the job. It has no training phase. It learns tick-by-tick. If the market shifts, the model shifts with it.

## 🛠 Under the Hood

I know you might just want to see the charts, but for my fellow tech nerds, here’s what we’re running on:

*   **Engine:** Python 3.11 (Modern).
*   **The Heavy Lifting:** PyTorch, TensorFlow & Transformers (via `tf-keras` for compatibility).
*   **Data:** We pull from Yahoo Finance and RSS feeds.
*   **Architecture:** Asyncio-driven Unified Engine (handling both Live and Replay modes).
*   **Infrastructure:** It’s all wrapped in Docker containers. This keeps the messy dependencies isolated so they don't fight with the other Python projects on your laptop.

### Realism Constraints (Because Brokers Aren't Charities)
I built this simulation to be painful. Why? Because easy backtests are lies.

*   **Slippage & Volatility:** The system simulates the price jumping around by 0.5% to 1.5%. You won't always get the price you clicked.
*   **Transaction Costs:** It deducts **$2.00 per trade**. That little tax kills bad strategies fast.
*   **Risk Management:** We don't just "YOLO" into trades. We use a dedicated `RiskManager` that sizes positions based on capital and enforces Stop Losses.
*   **The Database:** We use SQLite to log everything. It treats every trade like a real transaction.

## 📊 Deployment Guide

### 1. Installation
Ensure you have Docker installed.

```bash
# Clone the repository
git clone https://github.com/yourusername/quant-desk.git
cd quant-desk

# Setup Environment
cp .env.example .env
# Edit .env to tune your risk parameters

# Start the full stack (Engine + Dashboard)
docker-compose up --build
```

### 2. Access the Dashboard
Navigate to **`http://localhost:8501`** in your browser.
You will see the **Live Order Flow**, **Equity Curve**, and **Net Liquidation Value** updating in real-time.

### 3. Operational Modes
The system supports two modes, configurable in `docker-compose.yml`:

*   **`--mode replay` (Default):** High-speed backtest using historical data. Perfect for strategy validation.
*   **`--mode live`:** Connects to live Google News RSS and Yahoo Finance APIs. Polls for new data every 60 seconds.

## 🖥️ Taking It for a Spin

You can run this two ways. Check your `docker-compose.yml` to switch modes.

### 1. Replay Mode (The Time Machine)
This is the default. It takes historical data and fast-forwards through it. It’s great for asking, "Hey, would this have worked last year?" without risking a dime.

### 2. Live Mode (The Real Deal... Sort of)
This connects to live Google News feeds and Yahoo Finance. It polls every 60 seconds.

Once it's running, you just pop open your browser to: `http://localhost:8501`

You’ll see a dashboard with your live order flow and equity curve. It’s... oddly mesmerizing to watch the little AI struggle and succeed in real-time.

## ⚠️ The "Don't Lose Your Shirt" Warning

Okay, real talk time. Put the coffee down for a second.

**Do not take this code and hook it up to your life savings tomorrow.**

I built this as a robust "Paper Trading" engine. It is production-grade code, but the data has limitations you need to know about before you try to act like a hedge fund.

*   **The 15-Minute Lag:** We are using Yahoo Finance's free API. It usually has a 15-minute delay. In the trading world, that is an eternity. If you want to high-frequency trade, you need to pay for a real data socket (like Polygon.io).
*   **Liquidity is a Myth Here:** The bot assumes if it wants to buy stock, there is someone there to sell it. In real life, buying huge amounts moves the price against you.
*   **Google doesn't like bots:** If you poll the news too aggressively (like every 5 seconds), Google will ban your IP. Keep it chill.

## FAQ / Defense

**"Why do my results vary so much?"**
> Because markets are noisy! If this bot made exactly $100 every single day, I’d be lying to you. The variance you see ($50 profit one day, $150 the next) is actually a sign the simulation is working correctly.

**"How does it actually learn?"**
> Incremental Learning. Most models are trained once and then slowly get stupid as the world changes. This model updates its weights after every single trade. It’s constantly asking, "Did I get that right?" and adjusting.

## 📄 License
MIT License. Built for educational and portfolio demonstration purposes.
