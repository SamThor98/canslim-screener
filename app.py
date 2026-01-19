import os
import time
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

# Import from existing modules to avoid duplication
from canslim_metrics import get_price_strength, get_earnings_growth
from screener_logic import get_sma_trend
from fetcher import (
    fetch_company_metadata, 
    get_tickers_by_index, 
    get_tickers_by_sector,
    get_top_tickers_by_market_cap,
    get_available_indices,
    get_available_sectors,
)
from visualizer import show_interactive_chart
from config import config
from logger_config import get_logger, setup_logging
from utils import validate_ticker, normalize_tickers, clean_fetched_tickers, deduplicate_tickers
from api_validation import validate_api_keys

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Validate API keys on startup
validate_api_keys()

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
# CANSLIM METRICS FUNCTIONS (wrapped for Streamlit caching)
# ============================================================================
@st.cache_data(ttl=config.cache_ttl)
def get_price_strength_cached(ticker: str, benchmark: str = None) -> float | None:
    """Cached wrapper for get_price_strength."""
    benchmark = benchmark or config.benchmark_ticker
    try:
        return get_price_strength(ticker, benchmark)
    except Exception as e:
        logger.error(f"Error getting price strength for {ticker}: {e}", exc_info=True)
        return None


@st.cache_data(ttl=config.cache_ttl)
def get_earnings_growth_cached(ticker: str) -> float | None:
    """Cached wrapper for get_earnings_growth."""
    try:
        return get_earnings_growth(ticker)
    except Exception as e:
        logger.error(f"Error getting earnings growth for {ticker}: {e}", exc_info=True)
        return None


@st.cache_data(ttl=config.cache_ttl)
def get_sma_data_cached(ticker: str) -> dict:
    """Get price and SMA data using existing function."""
    try:
        is_above_sma, current_price, sma_50 = get_sma_trend(ticker, period=config.sma_period)
        
        # Get 200-day SMA if we have enough data
        sma_200 = None
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=config.history_period)
            if len(hist) >= config.sma_200_period:
                sma_200 = float(hist["Close"].rolling(config.sma_200_period).mean().iloc[-1])
        except Exception:
            pass
        
        return {
            "current_price": current_price,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "above_sma": is_above_sma
        }
    except Exception as e:
        logger.error(f"Error getting SMA data for {ticker}: {e}", exc_info=True)
        return {"current_price": None, "sma_50": None, "sma_200": None, "above_sma": None}


@st.cache_data(ttl=config.cache_ttl)
def get_company_info_cached(ticker: str) -> dict:
    """Get company information using existing function."""
    try:
        metadata = fetch_company_metadata(ticker)
        return {
            "name": metadata.name,
            "sector": metadata.sector or "N/A",
            "industry": metadata.industry or "N/A",
        }
    except Exception as e:
        logger.error(f"Error getting company info for {ticker}: {e}", exc_info=True)
        return {"name": ticker, "sector": "N/A", "industry": "N/A"}


def run_screen(tickers: list[str], progress_bar) -> pd.DataFrame:
    """Run CANSLIM screen on tickers."""
    results = []
    
    logger.info(f"Starting CANSLIM screen for {len(tickers)} tickers")
    
    # Validate tickers
    valid_tickers = [t for t in tickers if validate_ticker(t)]
    if len(valid_tickers) < len(tickers):
        invalid = set(tickers) - set(valid_tickers)
        logger.warning(f"Invalid tickers filtered out: {invalid}")
    
    if not valid_tickers:
        logger.warning("No valid tickers to screen")
        return pd.DataFrame()
    
    logger.info(f"Screening {len(valid_tickers)} valid tickers")
    
    for i, ticker in enumerate(valid_tickers):
        try:
            progress_bar.progress((i + 1) / len(valid_tickers), f"Analyzing {ticker}...")
            
            # Get metrics using cached wrappers
            earnings = get_earnings_growth_cached(ticker)
            rs = get_price_strength_cached(ticker)
            sma_data = get_sma_data_cached(ticker)
            
            # Check CANSLIM criteria using config thresholds
            # Use bool() to handle numpy boolean types
            c_pass = earnings is not None and earnings > config.earnings_growth_threshold
            l_pass = rs is not None and rs > config.relative_strength_threshold
            trend_pass = bool(sma_data["above_sma"]) if sma_data["above_sma"] is not None else False
            
            if c_pass and l_pass and trend_pass:
                info = get_company_info_cached(ticker)
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
                logger.info(f"[PASS] {ticker} passed all CANSLIM criteria")
            else:
                # Log first few failures for debugging
                if i < 5:
                    logger.info(f"[FAIL] {ticker}: C={c_pass}({earnings}), L={l_pass}({rs}), T={trend_pass}")
            
            # Rate limiting
            time.sleep(config.rate_limit_delay)
            
        except Exception as e:
            logger.error(f"Error screening {ticker}: {e}", exc_info=True)
            continue
    
    logger.info(f"Screening complete: {len(results)} stocks passed out of {len(valid_tickers)}")
    return pd.DataFrame(results) if results else pd.DataFrame()


# ============================================================================
# CHART FUNCTION
# ============================================================================
def create_chart(ticker: str) -> go.Figure:
    """Create interactive candlestick chart."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=config.history_period)
        
        if df.empty:
            logger.warning(f"No data available for {ticker}")
            return None
        
        df["SMA_50"] = df["Close"].rolling(config.sma_period).mean()
        sma_200_series = df["Close"].rolling(config.sma_200_period).mean() if len(df) >= config.sma_200_period else None
        
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
            increasing_line_color="#00d4aa", decreasing_line_color="#ff6b6b",
            increasing_fillcolor="#00d4aa", decreasing_fillcolor="#ff6b6b",
        ))
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df["SMA_50"], mode="lines",
            name=f"{config.sma_period}-Day SMA", line=dict(color="#3b9dff", width=2)
        ))
        
        if sma_200_series is not None:
            fig.add_trace(go.Scatter(
                x=df.index, y=sma_200_series, mode="lines",
                name=f"{config.sma_200_period}-Day SMA", line=dict(color="#ff4757", width=2)
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
    except Exception as e:
        logger.error(f"Error creating chart for {ticker}: {e}", exc_info=True)
        return None


# ============================================================================
# AI CHAT FUNCTION
# ============================================================================
def get_ai_response(messages: list, ticker: str, metrics: dict) -> str:
    """Get response from OpenAI."""
    if not config.is_openai_configured():
        return (
            "⚠️ **OpenAI API key not configured.**\n\n"
            "To enable AI analysis:\n"
            "1. Create a `.env` file in the project root\n"
            "2. Add: `OPENAI_API_KEY=sk-your-key-here`\n"
            "3. Restart the app"
        )
    
    api_key = config.OPENAI_API_KEY
    
    try:
        client = OpenAI(api_key=api_key)
        
        system_prompt = f"""You are a veteran growth stock trader. Analyze {ticker} based on these CANSLIM metrics:
{chr(10).join(f'- {k}: {v}' for k, v in metrics.items())}

Answer questions briefly, focusing on risk and technical strength. Be concise and actionable."""
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = client.chat.completions.create(
            model=config.openai_model,
            messages=full_messages,
            temperature=config.openai_temperature,
            max_tokens=config.openai_max_tokens,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting AI response: {e}", exc_info=True)
        return f"Error: {str(e)}"


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # Connection Status Indicator
        st.subheader("🔌 Connection Status")
        
        col1, col2 = st.columns(2)
        with col1:
            if config.is_openai_configured():
                st.markdown("🟢 **OpenAI**")
            else:
                st.markdown("🔴 **OpenAI**")
        with col2:
            if config.is_sec_configured():
                st.markdown("🟢 **SEC**")
            else:
                st.markdown("🔴 **SEC**")
        
        # Show missing keys warning
        missing_keys = config.get_missing_keys()
        if missing_keys:
            with st.expander("⚠️ Missing Configuration", expanded=False):
                st.warning(
                    f"Missing: {', '.join(missing_keys)}\n\n"
                    "**To configure:**\n"
                    "1. Create a `.env` file in the project root\n"
                    "2. Add your keys:\n"
                    "```\n"
                    "OPENAI_API_KEY=sk-your-key\n"
                    "SEC_API_USER_AGENT=Name email@example.com\n"
                    "```\n"
                    "3. Restart the app"
                )
        
        st.divider()
        
        # Stock Screener - Multi-mode selection
        st.subheader("📊 Stock Screener")
        
        # Selection mode
        scan_mode = st.radio(
            "Scan Mode",
            ["📈 Index Scan", "🏭 Sector Scan", "✏️ Manual Entry"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        # Initialize tickers list
        tickers = []
        scan_source = ""
        
        if scan_mode == "📈 Index Scan":
            # Index selection dropdown
            available_indices = get_available_indices()
            selected_index = st.selectbox(
                "Select Index",
                available_indices,
                help="Fetch all components from selected index"
            )
            scan_source = selected_index
            
            # Limit slider for large indices
            scan_limit = st.slider(
                "Limit (Top N by Market Cap)",
                min_value=10,
                max_value=500,
                value=config.default_screen_limit,
                step=10,
                help="Limit to top stocks by market cap to avoid rate limits"
            )
            
            if selected_index == "Russell 2000":
                st.warning("⚠️ Russell 2000 requires premium data. Consider using Sector Scan.")
        
        elif scan_mode == "🏭 Sector Scan":
            # Sector selection dropdown
            available_sectors = get_available_sectors()
            selected_sector = st.selectbox(
                "Select Sector",
                available_sectors,
                help="Screen stocks within a specific sector"
            )
            scan_source = selected_sector
            
            # Limit slider for sector scan
            scan_limit = st.slider(
                "Limit (Top N by Market Cap)",
                min_value=10,
                max_value=100,
                value=min(config.default_screen_limit, 50),
                step=5,
                help="Limit to top stocks by market cap"
            )
        
        else:  # Manual Entry
            default_tickers = "NVDA, PLTR, AMD, TSLA, CELH, MSFT, GOOGL, META"
            ticker_input = st.text_area(
                "Enter tickers (comma-separated)", 
                default_tickers,
                help="Enter stock symbols separated by commas"
            )
            tickers = normalize_tickers(ticker_input)
            scan_limit = len(tickers)  # No limit for manual
            scan_source = "Manual"
            
            if ticker_input and not tickers:
                st.warning("⚠️ No valid tickers found. Please enter valid ticker symbols (e.g., AAPL, MSFT).")
        
        # Run button
        run_screen_btn = st.button("🔍 Run CANSLIM Screen", type="primary", use_container_width=True)
        
        st.divider()
        st.caption("CANSLIM Criteria:")
        st.caption(f"• (C) Earnings Growth > {config.earnings_growth_threshold * 100:.0f}%")
        st.caption(f"• (L) Relative Strength > {config.relative_strength_threshold:.1f}")
        st.caption(f"• (T) Price > {config.sma_period}-day SMA")
    
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
        
        # Fetch tickers based on scan mode
        progress = st.progress(0)
        status_text = st.empty()
        
        try:
            if scan_mode == "📈 Index Scan":
                status_text.text(f"Fetching {scan_source} components...")
                progress.progress(0.1)
                
                raw_tickers = get_tickers_by_index(scan_source)
                raw_tickers = clean_fetched_tickers(raw_tickers)
                
                if len(raw_tickers) > scan_limit:
                    status_text.text(f"Filtering to top {scan_limit} by market cap...")
                    progress.progress(0.2)
                    tickers = get_top_tickers_by_market_cap(raw_tickers, scan_limit)
                else:
                    tickers = raw_tickers
                
                st.info(f"📊 Loaded {len(tickers)} tickers from {scan_source}")
            
            elif scan_mode == "🏭 Sector Scan":
                status_text.text(f"Fetching {scan_source} sector stocks...")
                progress.progress(0.1)
                
                sector_stocks = get_tickers_by_sector(scan_source, limit=scan_limit)
                tickers = [t[0] for t in sector_stocks]  # Extract just tickers
                tickers = clean_fetched_tickers(tickers)
                
                st.info(f"🏭 Loaded {len(tickers)} tickers from {scan_source} sector")
            
            # Manual mode already has tickers populated
            elif scan_mode == "✏️ Manual Entry":
                st.info(f"✏️ Screening {len(tickers)} manually entered tickers")
            
            # Deduplicate
            tickers = deduplicate_tickers(tickers)
            
            if not tickers:
                st.error("❌ No valid tickers to screen. Please check your selection.")
                progress.empty()
                status_text.empty()
            else:
                status_text.text(f"Screening {len(tickers)} stocks...")
                progress.progress(0.3)
                
                results = run_screen(tickers, progress)
                st.session_state["screen_results"] = results
                
                progress.empty()
                status_text.empty()
        
        except Exception as e:
            logger.error(f"Error during screening: {e}", exc_info=True)
            st.error(f"❌ Error: {str(e)}")
            progress.empty()
            status_text.empty()
    
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
                     delta="PASS" if row['Earnings Growth %'] > config.earnings_growth_threshold * 100 else None)
        with col2:
            st.metric("Relative Strength", row['Relative Strength'],
                     delta="PASS" if row['Relative Strength'] > config.relative_strength_threshold else None)
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
