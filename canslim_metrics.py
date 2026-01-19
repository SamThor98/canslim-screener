import time
import yfinance as yf
import pandas as pd
from config import config
from logger_config import get_logger

logger = get_logger(__name__)


def _retry_yfinance_call(func, *args, max_attempts: int = 3, delay: float = 1.0, **kwargs):
    """
    Retry wrapper for yfinance API calls to handle network issues and rate limits.
    
    Args:
        func: Function to call (should be a yfinance method)
        *args: Positional arguments for the function
        max_attempts: Maximum number of retry attempts (default: 3)
        delay: Delay between retries in seconds (default: 1.0)
        **kwargs: Keyword arguments for the function
    
    Returns:
        Result from the function call
    
    Raises:
        Exception: If all retry attempts fail
    """
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = func(*args, **kwargs)
            if attempt > 1:
                logger.info(f"yfinance call succeeded on attempt {attempt}")
            return result
        except Exception as e:
            last_exception = e
            if attempt < max_attempts:
                wait_time = delay * attempt  # Exponential backoff
                logger.warning(f"yfinance call failed (attempt {attempt}/{max_attempts}): {e}. Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"yfinance call failed after {max_attempts} attempts: {e}", exc_info=True)
    
    raise last_exception


def get_price_strength(ticker: str, benchmark: str = None) -> float | None:
    """
    Calculate the Relative Strength of a stock compared to a benchmark.
    
    Fetches 1 year of closing prices for both the ticker and benchmark,
    calculates percentage change, and returns the ratio.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        benchmark: Benchmark ticker symbol (default: from config)
    
    Returns:
        Relative Strength score (e.g., 1.2 means 20% outperformance)
        Returns None if data cannot be fetched
    """
    if benchmark is None:
        benchmark = config.benchmark_ticker
    
    try:
        # Fetch historical data with retry logic
        ticker_obj = yf.Ticker(ticker)
        benchmark_obj = yf.Ticker(benchmark)
        
        ticker_data = _retry_yfinance_call(lambda: ticker_obj.history(period=config.history_period))
        benchmark_data = _retry_yfinance_call(lambda: benchmark_obj.history(period=config.history_period))
        
        # Check if we have sufficient data
        if ticker_data.empty or benchmark_data.empty:
            logger.warning(f"Insufficient data for {ticker} or {benchmark}")
            return None
        
        if len(ticker_data) < 2 or len(benchmark_data) < 2:
            logger.warning(f"Not enough historical data points for {ticker} or {benchmark}")
            return None
        
        # Get closing prices
        ticker_close = ticker_data["Close"]
        benchmark_close = benchmark_data["Close"]
        
        # Calculate percentage change from first to last close
        ticker_start = ticker_close.iloc[0]
        ticker_end = ticker_close.iloc[-1]
        ticker_pct_change = (ticker_end - ticker_start) / ticker_start
        
        benchmark_start = benchmark_close.iloc[0]
        benchmark_end = benchmark_close.iloc[-1]
        benchmark_pct_change = (benchmark_end - benchmark_start) / benchmark_start
        
        # Avoid division by zero
        if benchmark_pct_change == 0:
            logger.warning(f"Benchmark {benchmark} had zero change")
            return None
        
        # Calculate Relative Strength
        # A value > 1 means outperformance, < 1 means underperformance
        relative_strength = (1 + ticker_pct_change) / (1 + benchmark_pct_change)
        
        return float(relative_strength)
        
    except ValueError as e:
        logger.error(f"Value error calculating price strength for {ticker}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error calculating price strength for {ticker}: {e}", exc_info=True)
        return None


def get_earnings_growth(ticker: str) -> float | None:
    """
    Calculate year-over-year earnings growth for the most recent quarter.
    
    Compares the most recent quarter's Net Income to the same quarter
    one year ago.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        Percentage growth as a float (e.g., 0.25 for 25% growth)
        Returns None if data is missing or cannot be calculated
    """
    try:
        stock = yf.Ticker(ticker)
        quarterly_financials = _retry_yfinance_call(lambda: stock.quarterly_financials)
        
        # Check if we have financial data
        if quarterly_financials is None or quarterly_financials.empty:
            logger.warning(f"No quarterly financials available for {ticker}")
            return None
        
        # Check if Net Income row exists
        if "Net Income" not in quarterly_financials.index:
            logger.warning(f"Net Income not found in financials for {ticker}")
            return None
        
        net_income = quarterly_financials.loc["Net Income"]
        
        # Need at least 5 quarters to compare YoY (current + 4 quarters back)
        if len(net_income) < 5:
            logger.warning(f"Insufficient quarterly data for YoY comparison for {ticker}")
            return None
        
        # Get most recent quarter and same quarter last year
        # Columns are ordered from most recent to oldest
        current_quarter_income = net_income.iloc[0]
        year_ago_quarter_income = net_income.iloc[4]  # 4 quarters back = 1 year
        
        # Check for valid values
        if pd.isna(current_quarter_income) or pd.isna(year_ago_quarter_income):
            logger.warning(f"Missing Net Income data for {ticker}")
            return None
        
        # Avoid division by zero or negative base
        if year_ago_quarter_income == 0:
            logger.warning(f"Year-ago Net Income is zero for {ticker}")
            return None
        
        # Calculate percentage growth
        growth = (current_quarter_income - year_ago_quarter_income) / abs(year_ago_quarter_income)
        
        return float(growth)
        
    except ValueError as e:
        logger.error(f"Value error calculating earnings growth for {ticker}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error calculating earnings growth for {ticker}: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # Example usage
    ticker = "AAPL"
    
    print(f"CANSLIM Metrics for {ticker}")
    print("=" * 40)
    
    # Price Strength (Relative Strength)
    rs = get_price_strength(ticker)
    if rs is not None:
        performance = (rs - 1) * 100
        direction = "outperformed" if performance > 0 else "underperformed"
        print(f"Relative Strength: {rs:.2f} ({direction} SPY by {abs(performance):.1f}%)")
    else:
        print("Relative Strength: N/A")
    
    # Earnings Growth
    eg = get_earnings_growth(ticker)
    if eg is not None:
        print(f"YoY Earnings Growth: {eg * 100:.1f}%")
    else:
        print("YoY Earnings Growth: N/A")
