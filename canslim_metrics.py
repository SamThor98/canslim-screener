import yfinance as yf
import pandas as pd


def get_price_strength(ticker: str, benchmark: str = "SPY") -> float | None:
    """
    Calculate the Relative Strength of a stock compared to a benchmark.
    
    Fetches 1 year of closing prices for both the ticker and benchmark,
    calculates percentage change, and returns the ratio.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        benchmark: Benchmark ticker symbol (default: 'SPY')
    
    Returns:
        Relative Strength score (e.g., 1.2 means 20% outperformance)
        Returns None if data cannot be fetched
    """
    try:
        # Fetch 1 year of historical data
        ticker_data = yf.Ticker(ticker).history(period="1y")
        benchmark_data = yf.Ticker(benchmark).history(period="1y")
        
        # Check if we have sufficient data
        if ticker_data.empty or benchmark_data.empty:
            print(f"Insufficient data for {ticker} or {benchmark}")
            return None
        
        if len(ticker_data) < 2 or len(benchmark_data) < 2:
            print(f"Not enough historical data points")
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
            print(f"Benchmark {benchmark} had zero change")
            return None
        
        # Calculate Relative Strength
        # A value > 1 means outperformance, < 1 means underperformance
        relative_strength = (1 + ticker_pct_change) / (1 + benchmark_pct_change)
        
        return float(relative_strength)
        
    except Exception as e:
        print(f"Error calculating price strength for {ticker}: {e}")
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
        quarterly_financials = stock.quarterly_financials
        
        # Check if we have financial data
        if quarterly_financials is None or quarterly_financials.empty:
            print(f"No quarterly financials available for {ticker}")
            return None
        
        # Check if Net Income row exists
        if "Net Income" not in quarterly_financials.index:
            print(f"Net Income not found in financials for {ticker}")
            return None
        
        net_income = quarterly_financials.loc["Net Income"]
        
        # Need at least 5 quarters to compare YoY (current + 4 quarters back)
        if len(net_income) < 5:
            print(f"Insufficient quarterly data for YoY comparison for {ticker}")
            return None
        
        # Get most recent quarter and same quarter last year
        # Columns are ordered from most recent to oldest
        current_quarter_income = net_income.iloc[0]
        year_ago_quarter_income = net_income.iloc[4]  # 4 quarters back = 1 year
        
        # Check for valid values
        if pd.isna(current_quarter_income) or pd.isna(year_ago_quarter_income):
            print(f"Missing Net Income data for {ticker}")
            return None
        
        # Avoid division by zero or negative base
        if year_ago_quarter_income == 0:
            print(f"Year-ago Net Income is zero for {ticker}")
            return None
        
        # Calculate percentage growth
        growth = (current_quarter_income - year_ago_quarter_income) / abs(year_ago_quarter_income)
        
        return float(growth)
        
    except Exception as e:
        print(f"Error calculating earnings growth for {ticker}: {e}")
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
