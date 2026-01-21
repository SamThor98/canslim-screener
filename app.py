import os
import time
import base64
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from openai import OpenAI

# Import from existing modules to avoid duplication
from canslim_metrics import get_price_strength, get_earnings_growth, calculate_operating_leverage, get_institutional_sponsorship
from screener_logic import get_sma_trend, validate_trend_template
from ai_analyst import analyze_company_story
from fetcher import (
    fetch_company_metadata, 
    fetch_latest_10q,
    get_tickers_by_index, 
    get_tickers_by_sector,
    get_top_tickers_by_market_cap,
    get_available_indices,
    get_available_sectors,
    get_sector_performance,
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
    page_title="Logan Screener — Growth Stock Analysis",
    page_icon="🦬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# LOAD LOGO AS BASE64 FOR EMBEDDING
# ============================================================================
def get_logo_base64():
    """Load logo as base64 for embedding in HTML."""
    try:
        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

logo_b64 = get_logo_base64()

# ============================================================================
# OLD LOGAN CAPITAL STYLING
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700;9..144,900&family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    
    /* CSS Variables */
    :root {
        --cream: #F5F1E8;
        --cream-dark: #EBE5D6;
        --dark: #1a1a1a;
        --dark-alt: #2a2a2a;
        --forest: #1A3A2E;
        --forest-light: #2D5A4A;
        --gold: #C9A962;
        --text: #1a1a1a;
        --text-muted: #5a5a5a;
        --border: rgba(26, 26, 26, 0.1);
        --border-light: rgba(26, 26, 26, 0.05);
        --success: #2D5A4A;
        --warning: #C9A962;
        --error: #8B3A3A;
    }
    
    /* Main App Background */
    .stApp {
        background: var(--cream) !important;
    }
    
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Fraunces', serif !important;
        color: var(--dark) !important;
        letter-spacing: -0.5px;
    }
    
    h1 {
        font-size: 3rem !important;
        font-weight: 700 !important;
        letter-spacing: -2px !important;
    }
    
    h2 {
        font-size: 2rem !important;
        font-weight: 600 !important;
    }
    
    h3 {
        font-size: 1.5rem !important;
        font-weight: 600 !important;
    }
    
    /* Body text */
    p, span, div, label {
        font-family: 'DM Sans', sans-serif !important;
        color: var(--text);
    }
    
    /* Muted text */
    .text-muted, .stCaption, small {
        color: var(--text-muted) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Section Labels */
    .section-label {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 2.5px;
        color: var(--text-muted) !important;
        margin-bottom: 0.5rem;
        display: block;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.7) !important;
        border-right: 1px solid var(--border) !important;
    }
    
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
    
    /* Cards / Containers */
    .logan-card {
        background: rgba(255, 255, 255, 0.7);
        border: 1px solid var(--border);
        padding: 2rem;
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .logan-card:hover {
        border-color: var(--dark);
        background: rgba(255, 255, 255, 0.9);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
    }
    
    /* Metrics display */
    .metric-container {
        background: rgba(255, 255, 255, 0.5);
        border: 1px solid var(--border);
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .metric-container:hover {
        border-color: var(--dark);
    }
    
    .metric-value {
        font-family: 'Fraunces', serif !important;
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--dark);
        letter-spacing: -1px;
        margin-bottom: 0.25rem;
    }
    
    .metric-label {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.7rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    
    /* Pass/Fail badges */
    .pass-badge {
        background: var(--forest);
        color: var(--cream);
        padding: 0.4rem 1rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: inline-block;
    }
    
    .fail-badge {
        background: var(--error);
        color: var(--cream);
        padding: 0.4rem 1rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: inline-block;
    }
    
    /* Buttons */
    .stButton > button {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        background: var(--dark) !important;
        color: var(--cream) !important;
        border: 1px solid var(--dark) !important;
        border-radius: 0 !important;
        padding: 0.7rem 1.8rem !important;
        transition: all 0.3s ease !important;
        clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
    }
    
    .stButton > button:hover {
        background: var(--cream) !important;
        color: var(--dark) !important;
    }
    
    /* Primary button override */
    .stButton > button[kind="primary"] {
        background: var(--forest) !important;
        border-color: var(--forest) !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: var(--forest-light) !important;
        border-color: var(--forest-light) !important;
        color: var(--cream) !important;
    }
    
    /* Input fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        font-family: 'DM Sans', sans-serif !important;
        background: rgba(255, 255, 255, 0.7) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0 !important;
        color: var(--text) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--dark) !important;
        box-shadow: none !important;
    }
    
    /* DataFrame styling */
    .stDataFrame {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    
    .stDataFrame table {
        background: rgba(255, 255, 255, 0.9) !important;
        border: 1px solid var(--border) !important;
    }
    
    .stDataFrame th {
        background: var(--forest) !important;
        color: var(--cream) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
    }
    
    .stDataFrame td {
        font-family: 'DM Sans', sans-serif !important;
        background: rgba(255, 255, 255, 0.9) !important;
        color: var(--text) !important;
        border-bottom: 1px solid var(--border-light) !important;
    }
    
    .stDataFrame tr:hover td {
        background: rgba(245, 241, 232, 1) !important;
    }
    
    /* DataFrame container */
    [data-testid="stDataFrame"] > div {
        background: transparent !important;
    }
    
    /* Glide data grid (new Streamlit tables) */
    .glideDataEditor {
        background: var(--cream) !important;
    }
    
    .dvn-scroller {
        background: var(--cream) !important;
    }
    
    /* Dividers */
    hr {
        border: none !important;
        border-top: 1px solid var(--border) !important;
        margin: 2rem 0 !important;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-family: 'Fraunces', serif !important;
        color: var(--dark) !important;
        font-weight: 700 !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.7rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        color: var(--text-muted) !important;
    }
    
    [data-testid="stMetricDelta"] {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    
    /* Chat messages */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.7) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0 !important;
    }
    
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
        background: var(--forest) !important;
    }
    
    .stChatMessage [data-testid="chatAvatarIcon-user"] {
        background: var(--dark) !important;
    }
    
    /* Chat input */
    .stChatInput > div {
        background: rgba(255, 255, 255, 0.9) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0 !important;
    }
    
    .stChatInput input {
        background: transparent !important;
        color: var(--text) !important;
    }
    
    .stChatInput button {
        background: var(--forest) !important;
        color: var(--cream) !important;
    }
    
    /* Progress bar */
    .stProgress > div > div > div {
        background: var(--forest) !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        color: var(--dark) !important;
        background: rgba(255, 255, 255, 0.5) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Radio buttons */
    .stRadio > div {
        background: transparent !important;
    }
    
    .stRadio label {
        font-family: 'DM Sans', sans-serif !important;
    }
    
    /* Slider */
    .stSlider > div > div > div > div {
        background: var(--forest) !important;
    }
    
    /* Success/Warning/Error messages */
    .stSuccess {
        background: rgba(45, 90, 74, 0.1) !important;
        border-left: 4px solid var(--forest) !important;
        color: var(--dark) !important;
    }
    
    .stWarning {
        background: rgba(201, 169, 98, 0.1) !important;
        border-left: 4px solid var(--gold) !important;
        color: var(--dark) !important;
    }
    
    .stError {
        background: rgba(139, 58, 58, 0.1) !important;
        border-left: 4px solid var(--error) !important;
        color: var(--dark) !important;
    }
    
    .stInfo {
        background: rgba(26, 26, 26, 0.05) !important;
        border-left: 4px solid var(--dark) !important;
        color: var(--dark) !important;
    }
    
    /* Selectbox */
    [data-baseweb="select"] {
        font-family: 'DM Sans', sans-serif !important;
    }
    
    /* ============================================ */
    /* FIX DARK POPUPS - Dropdown Menus & Modals */
    /* ============================================ */
    
    /* Dropdown menu container */
    [data-baseweb="popover"] {
        background: var(--cream) !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1) !important;
    }
    
    /* Dropdown menu list */
    [data-baseweb="menu"] {
        background: var(--cream) !important;
        border: none !important;
    }
    
    /* Dropdown menu items */
    [data-baseweb="menu"] ul {
        background: var(--cream) !important;
    }
    
    [data-baseweb="menu"] li {
        background: var(--cream) !important;
        color: var(--text) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background: rgba(26, 26, 26, 0.05) !important;
    }
    
    /* Selected option in dropdown */
    [data-baseweb="menu"] li[aria-selected="true"] {
        background: var(--forest) !important;
        color: var(--cream) !important;
    }
    
    /* Selectbox dropdown options */
    div[data-baseweb="select"] > div {
        background: rgba(255, 255, 255, 0.7) !important;
        border-color: var(--border) !important;
    }
    
    /* Multiselect tags */
    [data-baseweb="tag"] {
        background: var(--forest) !important;
        color: var(--cream) !important;
    }
    
    /* Toast/notification popups */
    [data-baseweb="toast"] {
        background: var(--cream) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Modal/Dialog backgrounds */
    [data-baseweb="modal"] {
        background: var(--cream) !important;
    }
    
    [data-baseweb="modal"] > div {
        background: var(--cream) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Tooltip styling */
    [data-baseweb="tooltip"] {
        background: var(--dark) !important;
        color: var(--cream) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    
    /* Streamlit specific popover/tooltip */
    .stTooltipIcon {
        color: var(--text-muted) !important;
    }
    
    div[data-testid="stTooltipContent"] {
        background: var(--cream) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    
    /* Date picker popup */
    [data-baseweb="calendar"] {
        background: var(--cream) !important;
        color: var(--text) !important;
    }
    
    /* Popover content */
    div[data-baseweb="popover"] > div {
        background: var(--cream) !important;
    }
    
    /* List options */
    ul[role="listbox"] {
        background: var(--cream) !important;
    }
    
    ul[role="listbox"] li {
        background: var(--cream) !important;
        color: var(--text) !important;
    }
    
    ul[role="listbox"] li:hover {
        background: rgba(26, 26, 26, 0.05) !important;
    }
    
    /* Option highlighted */
    li[aria-selected="true"],
    li[data-highlighted="true"] {
        background: var(--forest) !important;
        color: var(--cream) !important;
    }
    
    /* Autocomplete dropdown */
    [data-baseweb="list"] {
        background: var(--cream) !important;
    }
    
    [data-baseweb="list-item"] {
        background: var(--cream) !important;
        color: var(--text) !important;
    }
    
    [data-baseweb="list-item"]:hover {
        background: rgba(26, 26, 26, 0.05) !important;
    }
    
    /* Logo header */
    .logo-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .logo-header img {
        height: 50px;
        width: auto;
        opacity: 0.9;
    }
    
    .logo-text {
        font-family: 'Fraunces', serif;
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--dark);
        letter-spacing: -0.5px;
    }
    
    /* Stats grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .stat-item {
        background: rgba(255, 255, 255, 0.5);
        border: 1px solid var(--border);
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .stat-item:hover {
        border-color: var(--dark);
        background: rgba(255, 255, 255, 0.8);
    }
    
    .stat-value {
        font-family: 'Fraunces', serif;
        font-size: 2rem;
        font-weight: 700;
        color: var(--dark);
        margin-bottom: 0.25rem;
    }
    
    .stat-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.65rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    
    /* Stock card */
    .stock-card {
        background: rgba(255, 255, 255, 0.7);
        border: 1px solid var(--border);
        padding: 2rem;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .stock-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
        transition: left 0.5s ease;
    }
    
    .stock-card:hover::before {
        left: 100%;
    }
    
    .stock-card:hover {
        border-color: var(--dark);
        background: rgba(255, 255, 255, 0.9);
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
    }
    
    .stock-ticker {
        font-family: 'Fraunces', serif;
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--dark);
        margin-bottom: 0.5rem;
    }
    
    .stock-name {
        font-family: 'DM Sans', sans-serif;
        font-size: 1rem;
        color: var(--text-muted);
        margin-bottom: 1rem;
    }
    
    .stock-tag {
        display: inline-block;
        padding: 0.4rem 1rem;
        background: var(--dark);
        color: var(--cream);
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Connection indicators */
    .connection-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .connection-dot.connected {
        background: var(--forest);
    }
    
    .connection-dot.disconnected {
        background: var(--error);
    }
    
    /* Footer style text */
    .footer-text {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        color: var(--text-muted);
        text-align: center;
        padding: 2rem 0;
        border-top: 1px solid var(--border-light);
        margin-top: 3rem;
    }
    
    /* Hide Streamlit branding and sidebar */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Hide sidebar completely */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    /* Animations */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in-up {
        animation: fadeInUp 0.6s ease both;
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


@st.cache_data(ttl=config.cache_ttl)
def get_trend_template_cached(ticker: str) -> tuple[bool, dict]:
    """Get trend template validation using existing function."""
    try:
        return validate_trend_template(ticker)
    except Exception as e:
        logger.error(f"Error getting trend template for {ticker}: {e}", exc_info=True)
        return False, {}


@st.cache_data(ttl=config.cache_ttl)
def get_institutional_sponsorship_cached(ticker: str) -> tuple[bool, float | None]:
    """Get institutional sponsorship using existing function."""
    try:
        return get_institutional_sponsorship(ticker)
    except Exception as e:
        logger.error(f"Error getting institutional sponsorship for {ticker}: {e}", exc_info=True)
        return False, None


@st.cache_data(ttl=config.cache_ttl)
def get_volatility_check_cached(ticker: str) -> tuple[bool | None, float | None]:
    """
    Check if 20-day price range is less than 5%.
    
    Returns:
        Tuple of (passes_check, price_range_percent)
        Returns (None, None) if data cannot be fetched
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")  # Get ~22 trading days
        
        if hist.empty or len(hist) < 20:
            logger.warning(f"Insufficient data for 20-day volatility check for {ticker}")
            return None, None
        
        # Get last 20 days
        last_20_days = hist.tail(20)
        
        # Calculate price range
        max_price = float(last_20_days["High"].max())
        min_price = float(last_20_days["Low"].min())
        
        if min_price == 0:
            logger.warning(f"Zero minimum price for {ticker}")
            return None, None
        
        # Calculate percentage range: (max - min) / min
        price_range_percent = (max_price - min_price) / min_price
        
        # Check if range is less than 5% (0.05)
        passes_check = price_range_percent < 0.05
        
        return passes_check, price_range_percent
        
    except Exception as e:
        logger.error(f"Error calculating volatility for {ticker}: {e}", exc_info=True)
        return None, None


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
            
            # Professional Trend Template validation (replaces simple SMA check)
            trend_pass, trend_details = get_trend_template_cached(ticker)
            
            # Volatility check: 20-day price range must be less than 5%
            volatility_pass, price_range = get_volatility_check_cached(ticker)
            
            # Institutional Sponsorship check
            inst_sponsor_pass, inst_ownership = get_institutional_sponsorship_cached(ticker)
            
            # Operating leverage calculation
            operating_leverage = calculate_operating_leverage(ticker)
            
            # Check CANSLIM criteria using config thresholds
            c_pass = earnings is not None and earnings > config.earnings_growth_threshold
            l_pass = rs is not None and rs > config.relative_strength_threshold
            volatility_check = bool(volatility_pass) if volatility_pass is not None else False
            
            # Early AI qualitative filtering (N and S criteria)
            info = get_company_info_cached(ticker)
            ai_story_pass, ai_story_reason = analyze_company_story(
                ticker, 
                {"name": info["name"], "sector": info["sector"], "industry": info["industry"]}
            )
            
            # All criteria must pass
            if c_pass and l_pass and trend_pass and volatility_check and inst_sponsor_pass and ai_story_pass:
                current_price = trend_details.get("current_price", 0) if trend_details else 0
                results.append({
                    "Ticker": ticker,
                    "Company": info["name"],
                    "Sector": info["sector"],
                    "Industry": info["industry"],
                    "Earnings Growth %": round(earnings * 100, 1),
                    "Relative Strength": round(rs, 2),
                    "Price": round(current_price, 2),
                    "Operating Leverage": round(operating_leverage, 2) if operating_leverage is not None else None,
                    "Institutional Support": f"{inst_ownership:.1f}%" if inst_ownership else "N/A",
                    "Trend Template Pass": "✓" if trend_pass else "✗",
                })
                logger.info(f"[PASS] {ticker} passed all CANSLIM criteria (Trend: {trend_pass}, Inst: {inst_ownership}%, AI: {ai_story_pass})")
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
    
    # Create DataFrame and sort by Operating Leverage (descending)
    if results:
        df = pd.DataFrame(results)
        # Sort by Operating Leverage (highest first), handling None values
        df = df.sort_values(
            "Operating Leverage", 
            ascending=False, 
            na_position='last'
        ).reset_index(drop=True)
        return df
    else:
        return pd.DataFrame()


# ============================================================================
# CHART FUNCTION
# ============================================================================
def create_chart(ticker: str, timeframe: str = "daily") -> go.Figure:
    """Create interactive candlestick chart with Old Logan Capital styling and volume."""
    try:
        from plotly.subplots import make_subplots
        
        stock = yf.Ticker(ticker)
        
        # Fetch data based on timeframe
        if timeframe.lower() == "weekly":
            df = stock.history(period="2y", interval="1wk")
            title_suffix = "Weekly Base View"
            sma_periods = {"sma_10w": 10, "sma_40w": 40}
        else:
            df = stock.history(period=config.history_period, interval="1d")
            title_suffix = "Daily View"
            sma_periods = {"sma_50": 50, "sma_150": 150, "sma_200": 200}
        
        if df.empty:
            logger.warning(f"No data available for {ticker}")
            return None
        
        # Create subplots: price on top, volume on bottom
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(f"{ticker} Price Action", "Volume")
        )
        
        # Calculate SMAs
        if timeframe.lower() == "weekly":
            df["SMA_10w"] = df["Close"].rolling(window=sma_periods["sma_10w"]).mean()
            df["SMA_40w"] = df["Close"].rolling(window=sma_periods["sma_40w"]).mean()
        else:
            df["SMA_50"] = df["Close"].rolling(window=sma_periods["sma_50"]).mean()
            sma_150_series = df["Close"].rolling(150).mean() if len(df) >= 150 else None
            sma_200_series = df["Close"].rolling(config.sma_200_period).mean() if len(df) >= config.sma_200_period else None
        
        # Candlestick with OLC colors (row 1)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
            increasing_line_color="#1A3A2E",  # Forest green for up
            decreasing_line_color="#8B3A3A",  # Muted red for down
            increasing_fillcolor="#2D5A4A",
            decreasing_fillcolor="#8B3A3A",
        ), row=1, col=1)
        
        # Add SMAs based on timeframe (row 1)
        if timeframe.lower() == "weekly":
            # 10-week SMA - Gold
            fig.add_trace(go.Scatter(
                x=df.index, y=df["SMA_10w"], mode="lines",
                name="10-Week SMA", 
                line=dict(color="#C9A962", width=2)
            ), row=1, col=1)
            
            # 40-week SMA - Dark
            fig.add_trace(go.Scatter(
                x=df.index, y=df["SMA_40w"], mode="lines",
                name="40-Week SMA", 
                line=dict(color="#1a1a1a", width=2)
            ), row=1, col=1)
        else:
            # 50-day SMA - Gold
            fig.add_trace(go.Scatter(
                x=df.index, y=df["SMA_50"], mode="lines",
                name=f"{config.sma_period}-Day SMA", 
                line=dict(color="#C9A962", width=2)
            ), row=1, col=1)
            
            # 150-day SMA - Orange
            if sma_150_series is not None:
                fig.add_trace(go.Scatter(
                    x=df.index, y=sma_150_series, mode="lines",
                    name="150-Day SMA", 
                    line=dict(color="#ffa726", width=2)
                ), row=1, col=1)
            
            # 200-day SMA - Dark
            if sma_200_series is not None:
                fig.add_trace(go.Scatter(
                    x=df.index, y=sma_200_series, mode="lines",
                    name=f"{config.sma_200_period}-Day SMA", 
                    line=dict(color="#1a1a1a", width=2)
                ), row=1, col=1)
        
        # Add Volume bars with color coding (row 2)
        if "Volume" in df.columns:
            volume_colors = []
            for i in range(len(df)):
                if df["Close"].iloc[i] > df["Open"].iloc[i]:
                    volume_colors.append("#2D5A4A")  # Green for accumulation
                else:
                    volume_colors.append("#8B3A3A")  # Red for distribution
            
            fig.add_trace(go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volume",
                marker_color=volume_colors,
                showlegend=False,
            ), row=2, col=1)
        
        # OLC-style layout
        fig.update_layout(
            title=dict(
                text=f"{ticker} — {title_suffix}",
                font=dict(family="Fraunces", size=24, color="#1a1a1a")
            ),
            paper_bgcolor="#F5F1E8",
            plot_bgcolor="#F5F1E8",
            font=dict(family="DM Sans", color="#1a1a1a"),
            legend=dict(
                orientation="h", 
                y=1.02, 
                x=0.5, 
                xanchor="center",
                font=dict(family="IBM Plex Mono", size=11),
                bgcolor="rgba(255, 255, 255, 0.5)",
            ),
            height=600,
            margin=dict(l=20, r=60, t=80, b=40),
        )
        
        # Update x-axis (shared between subplots)
        fig.update_xaxes(
            rangeslider=dict(visible=False), 
            gridcolor="rgba(26, 26, 26, 0.1)",
            linecolor="rgba(26, 26, 26, 0.2)",
            tickfont=dict(family="IBM Plex Mono", size=10),
            row=2, col=1
        )
        
        # Update y-axes
        fig.update_yaxes(
            gridcolor="rgba(26, 26, 26, 0.1)", 
            side="right",
            linecolor="rgba(26, 26, 26, 0.2)",
            tickfont=dict(family="IBM Plex Mono", size=10),
            tickformat="$,.0f",
            row=1, col=1
        )
        
        fig.update_yaxes(
            gridcolor="rgba(26, 26, 26, 0.1)",
            linecolor="rgba(26, 26, 26, 0.2)",
            tickfont=dict(family="IBM Plex Mono", size=10),
            row=2, col=1
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
            "**OpenAI API key not configured.**\n\n"
            "To enable AI analysis:\n"
            "1. Create a `.env` file in the project root\n"
            "2. Add: `OPENAI_API_KEY=sk-your-key-here`\n"
            "3. Restart the app"
        )
    
    api_key = config.OPENAI_API_KEY
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Fetch latest 10-Q with MD&A text
        mda_text = None
        filing_date = None
        try:
            with st.spinner("Fetching SEC filing data..."):
                financial_data = fetch_latest_10q(ticker)
                if financial_data and financial_data.mda_text:
                    mda_text = financial_data.mda_text
                    filing_date = financial_data.filing_date
                    logger.info(f"Retrieved MD&A text for {ticker} from {filing_date}")
        except Exception as e:
            logger.warning(f"Could not fetch MD&A text for {ticker}: {e}")
            # Continue without MD&A - not critical
        
        # Build system prompt with MD&A if available
        base_prompt = f"""You are a veteran growth stock analyst at Old Logan Capital, a strategic investment firm. Analyze {ticker} based on these CANSLIM metrics:
{chr(10).join(f'- {k}: {v}' for k, v in metrics.items())}"""
        
        if mda_text:
            base_prompt += f"""

**DEEP DIVE ANALYSIS REQUIRED**

Below is the Management's Discussion & Analysis (MD&A) section from the most recent 10-Q filing for {ticker} (filed on {filing_date}). This is actual text from the SEC filing.

**MD&A Section:**
{mda_text}

Based on this actual SEC filing MD&A section, provide a comprehensive "Deep Dive" analysis that includes:
- Key business trends and developments discussed by management
- Financial condition and results of operations insights
- Risk factors and challenges mentioned
- Management's outlook and forward-looking statements
- Strategic implications for investors

Answer questions with the wisdom and measured perspective of an experienced value investor. Be concise, insightful, and focus on risk assessment and long-term value creation potential. Use clear, professional language. Reference specific details from the MD&A when relevant."""
        else:
            base_prompt += """

Answer questions with the wisdom and measured perspective of an experienced value investor. Be concise, insightful, and focus on risk assessment and long-term value creation potential. Use clear, professional language."""
        
        system_prompt = base_prompt
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
    # Header with logo
    if logo_b64:
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1.5rem; margin-bottom: 0.5rem;">
                <img src="data:image/png;base64,{logo_b64}" alt="Logan Screener" style="height: 70px; opacity: 0.9;">
                <div>
                    <h1 style="margin: 0; line-height: 1.1;">Logan Screener</h1>
                    <span class="section-label">Strategic Growth Stock Analysis</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.title("🦬 Logan Screener")
        st.markdown('<span class="section-label">Strategic Growth Stock Analysis</span>', unsafe_allow_html=True)
    
    st.markdown("*Built to endure. Positioned to prosper.*")
    
    # Connection status (inline, subtle)
    missing_keys = config.get_missing_keys()
    if missing_keys:
        st.warning(f"⚠️ Missing configuration: {', '.join(missing_keys)}. Create a `.env` file with your API keys.")
    
    st.divider()
    
    # ========== SCREENING CONTROLS ==========
    st.markdown('<span class="section-label">Stock Screener</span>', unsafe_allow_html=True)
    
    # Layout: Mode selection and options in columns
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        scan_mode = st.radio(
            "Scan Mode",
            ["Index Scan", "Sector Scan", "Manual Entry"],
            label_visibility="collapsed"
        )
    
    # Initialize tickers list
    tickers = []
    scan_source = ""
    scan_limit = 50
    
    with col2:
        if scan_mode == "Index Scan":
            available_indices = get_available_indices()
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                selected_index = st.selectbox(
                    "Select Index",
                    available_indices,
                    label_visibility="collapsed"
                )
            with sub_col2:
                scan_limit = st.slider(
                    "Limit",
                    min_value=10,
                    max_value=200,
                    value=config.default_screen_limit,
                    step=10,
                    label_visibility="collapsed"
                )
            scan_source = selected_index
            
        elif scan_mode == "Sector Scan":
            available_sectors = get_available_sectors()
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                selected_sector = st.selectbox(
                    "Select Sector",
                    available_sectors,
                    label_visibility="collapsed"
                )
            with sub_col2:
                scan_limit = st.slider(
                    "Limit",
                    min_value=10,
                    max_value=100,
                    value=min(config.default_screen_limit, 50),
                    step=5,
                    label_visibility="collapsed"
                )
            scan_source = selected_sector
            
        else:  # Manual Entry
            default_tickers = "NVDA, PLTR, AMD, TSLA, CELH, MSFT, GOOGL, META"
            ticker_input = st.text_input(
                "Enter tickers",
                default_tickers,
                label_visibility="collapsed",
                placeholder="Enter tickers separated by commas (e.g., AAPL, MSFT, GOOGL)"
            )
            tickers = normalize_tickers(ticker_input)
            scan_limit = len(tickers)
            scan_source = "Manual"
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        run_screen_btn = st.button("🔍 Run Screen", type="primary", use_container_width=True)
    
    # CANSLIM criteria hint
    st.caption(f"**Criteria:** Earnings Growth > {config.earnings_growth_threshold * 100:.0f}% · Relative Strength > {config.relative_strength_threshold:.1f} · Professional Trend Template · Institutional Support >30% · 20-Day Volatility < 5% · AI Qualitative Filter")
    
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
            if scan_mode == "Index Scan":
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
                
                st.info(f"Loaded {len(tickers)} tickers from {scan_source}")
            
            elif scan_mode == "Sector Scan":
                status_text.text(f"Fetching {scan_source} sector stocks...")
                progress.progress(0.1)
                
                sector_stocks = get_tickers_by_sector(scan_source, limit=scan_limit)
                tickers = [t[0] for t in sector_stocks]  # Extract just tickers
                tickers = clean_fetched_tickers(tickers)
                
                st.info(f"Loaded {len(tickers)} tickers from {scan_source} sector")
            
            # Manual mode already has tickers populated
            elif scan_mode == "Manual Entry":
                st.info(f"Screening {len(tickers)} manually entered tickers")
            
            # Deduplicate
            tickers = deduplicate_tickers(tickers)
            
            if not tickers:
                st.error("No valid tickers to screen. Please check your selection.")
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
            st.error(f"Error: {str(e)}")
            progress.empty()
            status_text.empty()
    
    # Display results
    if not st.session_state["screen_results"].empty:
        st.divider()
        
        # Results header
        num_results = len(st.session_state['screen_results'])
        st.markdown(f"""
            <div style="margin-bottom: 1.5rem;">
                <span class="section-label">Screening Results</span>
                <h2 style="margin-top: 0.5rem;">{num_results} Stocks Passed All Criteria</h2>
            </div>
        """, unsafe_allow_html=True)
        
        # Market Structure - Sector Performance Heatmap
        st.markdown('<span class="section-label">Market Structure</span>', unsafe_allow_html=True)
        
        # Initialize sector filter in session state
        if "selected_sector_filter" not in st.session_state:
            st.session_state["selected_sector_filter"] = "All Sectors"
        
        try:
            sector_perf = get_sector_performance(st.session_state["screen_results"])
            
            if not sector_perf.empty:
                # Create treemap heatmap
                fig_heatmap = px.treemap(
                    sector_perf,
                    path=['Sector'],
                    values='Stock_Count',
                    color='Avg_Relative_Strength',
                    color_continuous_scale='RdYlGn',  # Red to Yellow to Green
                    title='Sector Performance Heatmap',
                    hover_data=['Stock_Count', 'Avg_Relative_Strength'],
                    labels={'Avg_Relative_Strength': 'Avg Relative Strength', 'Stock_Count': 'Stock Count'}
                )
                
                # Update layout for dark theme
                fig_heatmap.update_layout(
                    paper_bgcolor="#0f0f23",
                    plot_bgcolor="#0f0f23",
                    font=dict(color="#c9d1d9", family="DM Sans"),
                    title_font=dict(size=18, color="#c9d1d9"),
                    height=400,
                )
                
                # Update colorbar
                fig_heatmap.update_coloraxes(
                    colorbar=dict(
                        title="Avg Relative Strength",
                        titlefont=dict(color="#c9d1d9"),
                        tickfont=dict(color="#c9d1d9"),
                    )
                )
                
                st.plotly_chart(fig_heatmap, use_container_width=True)
                
                # Sector filter dropdown
                selected_sector = st.selectbox(
                    "Filter by Sector (click sector in heatmap or select below):",
                    ["All Sectors"] + sector_perf['Sector'].tolist(),
                    key="sector_filter",
                    index=0 if st.session_state["selected_sector_filter"] == "All Sectors" else 
                          sector_perf['Sector'].tolist().index(st.session_state["selected_sector_filter"]) + 1 
                          if st.session_state["selected_sector_filter"] in sector_perf['Sector'].tolist() else 0
                )
                st.session_state["selected_sector_filter"] = selected_sector
            else:
                selected_sector = "All Sectors"
                st.info("Sector performance data not available")
        except Exception as e:
            logger.error(f"Error creating sector heatmap: {e}", exc_info=True)
            selected_sector = "All Sectors"
            st.warning("Could not generate sector heatmap")
        
        # Filter results by selected sector
        if selected_sector and selected_sector != "All Sectors":
            filtered_results = st.session_state["screen_results"][
                st.session_state["screen_results"]["Sector"] == selected_sector
            ]
            st.info(f"Showing {len(filtered_results)} stocks in {selected_sector} sector")
        else:
            filtered_results = st.session_state["screen_results"]
        
        st.dataframe(
            filtered_results,
            use_container_width=True,
            hide_index=True,
        )
        
        # Stock selection
        st.divider()
        st.markdown('<span class="section-label">Deep Dive Analysis</span>', unsafe_allow_html=True)
        
        passing_tickers = st.session_state["screen_results"]["Ticker"].tolist()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            selected = st.selectbox("Select a stock to analyze:", passing_tickers)
        with col2:
            analyze_btn = st.button("Analyze", type="primary")
        
        if analyze_btn:
            st.session_state["selected_ticker"] = selected
            st.session_state["chat_messages"] = []
    
    elif run_screen_btn:
        st.warning("No stocks passed all CANSLIM criteria. Try different tickers or adjust your selection.")
    
    # Deep dive section
    if st.session_state["selected_ticker"]:
        ticker = st.session_state["selected_ticker"]
        st.divider()
        
        # Get metrics for this ticker
        row = st.session_state["screen_results"][
            st.session_state["screen_results"]["Ticker"] == ticker
        ].iloc[0]
        
        # Header
        st.markdown(f"""
            <div style="margin-bottom: 2rem;">
                <span class="section-label">Deep Dive</span>
                <h2 style="margin-top: 0.5rem;">{ticker} — {row["Company"]}</h2>
                <p style="color: #5a5a5a; margin-top: 0.25rem;">{row["Sector"]} · {row["Industry"]}</p>
            </div>
        """, unsafe_allow_html=True)
        
        metrics = {
            "Company": row["Company"],
            "Sector": row["Sector"],
            "Industry": row["Industry"],
            "Earnings Growth": f"{row['Earnings Growth %']}%",
            "Relative Strength": row["Relative Strength"],
            "Current Price": f"${row['Price']}",
            "50-Day SMA": f"${row['50-SMA']}",
        }
        
        # Metrics cards in OLC style
        st.markdown("""
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">""" + f"{row['Earnings Growth %']}%" + """</div>
                    <div class="stat-label">Earnings Growth</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">""" + f"{row['Relative Strength']}" + """</div>
                    <div class="stat-label">Relative Strength</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">$""" + f"{row['Price']}" + """</div>
                    <div class="stat-label">Current Price</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">$""" + f"{row['50-SMA']}" + """</div>
                    <div class="stat-label">50-Day SMA</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Chart with timeframe toggle
        st.markdown('<span class="section-label">Price History</span>', unsafe_allow_html=True)
        
        # Timeframe toggle
        col_chart1, col_chart2 = st.columns([1, 4])
        with col_chart1:
            timeframe = st.radio(
                "Timeframe",
                ["Daily View", "Weekly Base View"],
                horizontal=True,
                label_visibility="collapsed"
            )
            timeframe_param = "weekly" if timeframe == "Weekly Base View" else "daily"
        
        chart = create_chart(ticker, timeframe_param)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        
        st.divider()
        
        # AI Chat
        st.markdown('<span class="section-label">AI Analyst</span>', unsafe_allow_html=True)
        st.markdown(f"*Ask our AI analyst about {ticker}*")
        
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
    
    # Footer
    st.markdown("""
        <div class="footer-text">
            © 2025 Logan Screener · Built with strategic vision
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
