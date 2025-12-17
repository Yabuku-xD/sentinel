import streamlit as st
import pandas as pd
import sqlite3
import time
import plotly.graph_objects as go

st.set_page_config(
    page_title="QuantDesk | Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono:wght@500&display=swap');

    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: 'Inter', sans-serif;
    }

    section[data-testid="stSidebar"] {
        background-color: #010409;
        border-right: 1px solid #30363d;
    }
    
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 15px;
        min-height: 120px;
    }
    div[data-testid="stMetricLabel"] {
        color: #8b949e;
        font-size: 0.9rem;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff;
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #30363d;
        border-radius: 6px;
    }
    
    .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

def load_data():
    try:
        conn = sqlite3.connect("portfolio.db", timeout=5)
        df = pd.read_sql_query("SELECT * FROM portfolio", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

with st.sidebar:
    st.title("⚡ QuantDesk")
    st.caption("Event-Driven Backtesting System")
    st.markdown("---")
    
    st.subheader("System Status")
    st.success("● Engine Online")
    st.info("● Database Connected")
    
    st.markdown("---")
    st.markdown("### Strategy Config")
    st.code("""
Sentiment: FinBERT (AI)
Threshold: Dynamic (Online Learning)
Assets:    $100/trade
Asset:     ^DJI
    """, language="yaml")
    
    st.markdown("---")
    st.caption("v1.3.2-stable")

st.title("Portfolio Telemetry")
st.markdown("Live feed of the **Sentiment-Alpha Strategy** executing on simulated market data.")
st.markdown("---")

st.markdown("""
<style>
.metric-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 2rem;
}
.metric-card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 15px;
    color: white;
}
.metric-label {
    color: #8b949e;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
}
.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    font-weight: 700;
}
.metric-delta {
    font-size: 0.9rem;
    margin-top: 0.5rem;
}
.delta-pos { color: #3fb950; }
.delta-neg { color: #f85149; }
.delta-neutral { color: #8b949e; }
</style>
""", unsafe_allow_html=True)

metrics_placeholder = st.empty()

st.subheader("Equity Curve")
chart_placeholder = st.empty()

st.subheader("Order Flow (Live)")
table_placeholder = st.empty()

while True:
    df = load_data()
    
    if not df.empty:
        current_balance = df['balance'].iloc[-1]
        start_balance = df['balance'].iloc[0]
        total_pnl = current_balance - start_balance
        pnl_pct = (total_pnl / start_balance) * 100
        
        last_trade = df.iloc[-1]
        last_signal = last_trade['signal']
        
        bal_delta_color = "delta-pos" if pnl_pct >= 0 else "delta-neg"
        sig_color = "delta-pos" if last_signal == "BUY" else "delta-neg" if last_signal == "SELL" else "delta-neutral"
        
        metrics_html = f"""
        <div class="metric-container">
            <div class="metric-card">
                <div class="metric-label">Net Liquidation Value</div>
                <div class="metric-value">${current_balance:,.2f}</div>
                <div class="metric-delta {bal_delta_color}">{pnl_pct:+.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total PnL</div>
                <div class="metric-value">${total_pnl:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{len(df)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Latest Signal</div>
                <div class="metric-value">{last_signal}</div>
                <div class="metric-delta {sig_color}">{"Active" if last_signal != "HOLD" else "Waiting"}</div>
            </div>
        </div>
        """
        metrics_placeholder.markdown(metrics_html, unsafe_allow_html=True)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index, 
            y=df['balance'],
            fill='tozeroy',
            mode='lines',
            line=dict(width=2, color='#58a6ff'),
            fillcolor='rgba(88, 166, 255, 0.1)',
            name='Equity'
        ))
        fig.add_hline(y=10000, line_dash="dash", line_color="#8b949e", opacity=0.5)

        fig.update_layout(
            autosize=True,
            height=350,
            margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8b949e'),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=True, gridcolor='#30363d', zeroline=False),
            hovermode="x unified"
        )
        chart_placeholder.plotly_chart(fig, use_container_width=True)
        
        recent_trades = df.tail(8)[['timestamp', 'signal', 'actual_movement', 'pnl']].sort_index(ascending=False)
        
        def color_pnl(val):
            if val > 0: return 'color: #3fb950; font-weight: 600;' 
            if val < 0: return 'color: #f85149; font-weight: 600;' 
            return 'color: #8b949e;'

        styled_df = recent_trades.style.map(color_pnl, subset=['pnl'])\
            .format({'pnl': "${:,.2f}"})
            
        table_placeholder.dataframe(
            styled_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "timestamp": st.column_config.TextColumn("Time", width="medium"),
                "signal": st.column_config.TextColumn("Side", width="small"),
                "actual_movement": st.column_config.TextColumn("Mkt Move", width="small"),
                "pnl": st.column_config.TextColumn("P&L", width="small")
            }
        )
        
    time.sleep(1)
