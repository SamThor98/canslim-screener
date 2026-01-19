import os
import time
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

# Must be called first
st.set_page_config(
    page_title="CANSLIM Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# STYLING
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@400;500;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%);
    }
    
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: #00d4aa !important;
    }
    
    .metric-card {
        background: rgba(0, 212, 170, 0.1);
        border: 1px solid #00d4aa;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    
    .pass-badge {
        background: #00d4aa;
        color: #0f0f23;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 12px;
    }
    
    .fail-badge {
        background: #ff6b6b;
        color: #0f0f23;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 12px;
    }
    
    .stDataFrame {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a3e 0%, #0f0f23 100%);
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# CANSLIM METRICS FUNCTIONS
# ============================================================================
@st.cache_data(ttl=3600)
def get_price_strength(ticker: str, benchmark: str = "SPY") -> float | None:
    """Calculate Relative Strength vs benchmark."""
    try:
        ticker_data = yf.Ticker(ticker).history(period="1y")
        benchmark_data = yf.Ticker(benchmark).history(period="1y")
        
        if ticker_data.empty or benchmark_data.empty or len(ticker_data) < 2:
            return None
        
        ticker_pct = (ticker_data["Close"].iloc[-1] - ticker_data["Close"].iloc[0]) / ticker_data["Close"].iloc[0]
        bench_pct = (benchmark_data["Close"].iloc[-1] - benchmark_data["Close"].iloc[0]) / benchmark_data["Close"].iloc[0]
        
        if bench_pct == 0:
            return None
            
        return float((1 + ticker_pct) / (1 + bench_pct))
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_earnings_growth(ticker: str) -> float | None:
    """Calculate YoY earnings growth."""
    try:
        stock = yf.Ticker(ticker)
        financials = stock.quarterly_financials
        
        if financials is None or financials.empty or "Net Income" not in financials.index:
            return None
        
        net_income = financials.loc["Net Income"]
        if len(net_income) < 5:
            return None
        
        current = net_income.iloc[0]
        year_ago = net_income.iloc[4]
        
        if pd.isna(current) or pd.isna(year_ago) or year_ago == 0:
            return None
        
        return float((current - year_ago) / abs(year_ago))
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_sma_data(ticker: str) -> dict:
    """Get price and SMA data."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        
        if hist.empty or len(hist) < 50:
            return {"current_price": None, "sma_50": None, "sma_200": None, "above_sma": None}
        
        current_price = float(hist["Close"].iloc[-1])
        sma_50 = float(hist["Close"].rolling(50).mean().iloc[-1])
        sma_200 = float(hist["Close"].rolling(200).mean().iloc[-1]) if len(hist) >= 200 else None
        
        return {
            "current_price": current_price,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "above_sma": current_price > sma_50
        }
    except Exception:
        return {"current_price": None, "sma_50": None, "sma_200": None, "above_sma": None}


@st.cache_data(ttl=3600)
def get_company_info(ticker: str) -> dict:
    """Get company information."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
        }
    except Exception:
        return {"name": ticker, "sector": "N/A", "industry": "N/A"}


def run_screen(tickers: list[str], progress_bar) -> pd.DataFrame:
    """Run CANSLIM screen on tickers."""
    results = []
    
    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers), f"Analyzing {ticker}...")
        
        # Get metrics
        earnings = get_earnings_growth(ticker)
        rs = get_price_strength(ticker)
        sma_data = get_sma_data(ticker)
        
        c_pass = earnings is not None and earnings > 0.20
        l_pass = rs is not None and rs > 1.0
        trend_pass = sma_data["above_sma"] is True
        
        if c_pass and l_pass and trend_pass:
            info = get_company_info(ticker)
            results.append({
                "Ticker": ticker,
                "Company": info["name"],
                "Sector": info["sector"],
                "Industry": info["industry"],
                "Earnings Growth %": round(earnings * 100, 1),
                "Relative Strength": round(rs, 2),
                "Price": round(sma_data["current_price"], 2),
                "50-SMA": round(sma_data["sma_50"], 2),
            })
        
        time.sleep(0.3)  # Rate limiting
    
    return pd.DataFrame(results) if results else pd.DataFrame()


# ============================================================================
# CHART FUNCTION
# ============================================================================
def create_chart(ticker: str) -> go.Figure:
    """Create interactive candlestick chart."""
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")
    
    if df.empty:
        return None
    
    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["SMA_200"] = df["Close"].rolling(200).mean()
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price",
        increasing_line_color="#00d4aa", decreasing_line_color="#ff6b6b",
        increasing_fillcolor="#00d4aa", decreasing_fillcolor="#ff6b6b",
    ))
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_50"], mode="lines",
        name="50-Day SMA", line=dict(color="#3b9dff", width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_200"], mode="lines",
        name="200-Day SMA", line=dict(color="#ff4757", width=2)
    ))
    
    fig.update_layout(
        title=f"{ticker} - 1 Year Chart",
        template="plotly_dark",
        paper_bgcolor="#0f0f23",
        plot_bgcolor="#1a1a3e",
        font=dict(color="#c9d1d9"),
        xaxis=dict(rangeslider=dict(visible=False), gridcolor="#30363d"),
        yaxis=dict(gridcolor="#30363d", side="right"),
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        height=500,
    )
    
    return fig


# ============================================================================
# AI CHAT FUNCTION
# ============================================================================
def get_ai_response(messages: list, ticker: str, metrics: dict) -> str:
    """Get response from OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY") or st.session_state.get("openai_key")
    
    if not api_key:
        return "Please enter your OpenAI API key in the sidebar to enable AI analysis."
    
    try:
        client = OpenAI(api_key=api_key)
        
        system_prompt = f"""You are a veteran growth stock trader. Analyze {ticker} based on these CANSLIM metrics:
{chr(10).join(f'- {k}: {v}' for k, v in metrics.items())}

Answer questions briefly, focusing on risk and technical strength. Be concise and actionable."""
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=full_messages,
            temperature=0.7,
            max_tokens=500,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # API Key input
        api_key = st.text_input("OpenAI API Key", type="password", 
                                help="Required for AI analyst feature")
        if api_key:
            st.session_state["openai_key"] = api_key
        
        st.divider()
        
        # Ticker input
        st.subheader("📊 Stock Screener")
        default_tickers = "NVDA, PLTR, AMD, TSLA, CELH, MSFT, GOOGL, META"
        ticker_input = st.text_area("Enter tickers (comma-separated)", default_tickers)
        tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
        
        run_screen_btn = st.button("🔍 Run CANSLIM Screen", type="primary", use_container_width=True)
        
        st.divider()
        st.caption("CANSLIM Criteria:")
        st.caption("• (C) Earnings Growth > 20%")
        st.caption("• (L) Relative Strength > 1.0")
        st.caption("• (T) Price > 50-day SMA")
    
    # Main content
    st.title("📈 CANSLIM Stock Screener")
    st.markdown("*Find high-growth stocks with strong momentum*")
    
    # Initialize session state
    if "screen_results" not in st.session_state:
        st.session_state["screen_results"] = pd.DataFrame()
    if "selected_ticker" not in st.session_state:
        st.session_state["selected_ticker"] = None
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []
    
    # Run screening
    if run_screen_btn:
        st.session_state["chat_messages"] = []
        st.session_state["selected_ticker"] = None
        
        with st.spinner("Running CANSLIM screen..."):
            progress = st.progress(0)
            results = run_screen(tickers, progress)
            st.session_state["screen_results"] = results
            progress.empty()
    
    # Display results
    if not st.session_state["screen_results"].empty:
        st.success(f"✅ {len(st.session_state['screen_results'])} stocks passed all criteria!")
        
        st.dataframe(
            st.session_state["screen_results"],
            use_container_width=True,
            hide_index=True,
        )
        
        # Stock selection
        st.divider()
        passing_tickers = st.session_state["screen_results"]["Ticker"].tolist()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            selected = st.selectbox("Select a stock to analyze:", passing_tickers)
        with col2:
            analyze_btn = st.button("📊 Deep Dive", type="primary")
        
        if analyze_btn:
            st.session_state["selected_ticker"] = selected
            st.session_state["chat_messages"] = []
    
    elif run_screen_btn:
        st.warning("No stocks passed all CANSLIM criteria. Try different tickers.")
    
    # Deep dive section
    if st.session_state["selected_ticker"]:
        ticker = st.session_state["selected_ticker"]
        st.divider()
        st.header(f"🔬 Deep Dive: {ticker}")
        
        # Get metrics for this ticker
        row = st.session_state["screen_results"][
            st.session_state["screen_results"]["Ticker"] == ticker
        ].iloc[0]
        
        metrics = {
            "Company": row["Company"],
            "Sector": row["Sector"],
            "Industry": row["Industry"],
            "Earnings Growth": f"{row['Earnings Growth %']}%",
            "Relative Strength": row["Relative Strength"],
            "Current Price": f"${row['Price']}",
            "50-Day SMA": f"${row['50-SMA']}",
        }
        
        # Metrics cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Earnings Growth", f"{row['Earnings Growth %']}%", 
                     delta="PASS" if row['Earnings Growth %'] > 20 else None)
        with col2:
            st.metric("Relative Strength", row['Relative Strength'],
                     delta="PASS" if row['Relative Strength'] > 1 else None)
        with col3:
            st.metric("Current Price", f"${row['Price']}")
        with col4:
            st.metric("50-Day SMA", f"${row['50-SMA']}")
        
        # Chart
        st.subheader("📈 Price Chart")
        chart = create_chart(ticker)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        
        # AI Chat
        st.subheader("🤖 AI Analyst Chat")
        
        # Display chat history
        for msg in st.session_state["chat_messages"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        # Chat input
        if prompt := st.chat_input(f"Ask about {ticker}..."):
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = get_ai_response(
                        st.session_state["chat_messages"],
                        ticker,
                        metrics
                    )
                    st.write(response)
            
            st.session_state["chat_messages"].append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
