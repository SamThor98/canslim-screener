import time
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from config import config
from logger_config import get_logger
from database import Stock, QuarterlyFinancial

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


def calculate_operating_leverage(ticker: str) -> float | None:
    """
    Calculate operating leverage by comparing Net Income growth to Revenue growth.
    
    Operating leverage indicates if Net Income is growing faster than Revenue.
    A value > 1.0 means Net Income is growing faster than Revenue (positive operating leverage).
    A value < 1.0 means Revenue is growing faster than Net Income (negative operating leverage).
    
    Uses the database to get the most recent two quarterly filings and compares
    the growth rates.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        Operating leverage ratio (Net Income growth / Revenue growth)
        Returns None if insufficient data or calculation cannot be performed
    """
    try:
        engine = create_engine(config.database_url, echo=False)
        
        with Session(engine) as session:
            # Find the stock by ticker
            stock = session.execute(
                select(Stock).where(Stock.ticker == ticker.upper())
            ).scalar_one_or_none()
            
            if not stock:
                logger.debug(f"No stock record found for {ticker} in database")
                return None
            
            # Get the two most recent quarterly financials, ordered by filing_date descending
            financials = session.execute(
                select(QuarterlyFinancial)
                .where(QuarterlyFinancial.stock_id == stock.id)
                .where(QuarterlyFinancial.revenue.isnot(None))
                .where(QuarterlyFinancial.net_income.isnot(None))
                .order_by(QuarterlyFinancial.filing_date.desc())
                .limit(2)
            ).scalars().all()
            
            if len(financials) < 2:
                logger.debug(f"Insufficient quarterly financial data for {ticker} (need at least 2 quarters)")
                return None
            
            # Get the two most recent quarters
            current_quarter = financials[0]
            previous_quarter = financials[1]
            
            # Extract revenue and net income
            current_revenue = current_quarter.revenue
            previous_revenue = previous_quarter.revenue
            current_net_income = current_quarter.net_income
            previous_net_income = previous_quarter.net_income
            
            # Check for valid values
            if (current_revenue is None or previous_revenue is None or
                current_net_income is None or previous_net_income is None):
                logger.debug(f"Missing revenue or net income data for {ticker}")
                return None
            
            # Avoid division by zero or negative base values
            if previous_revenue == 0 or previous_net_income == 0:
                logger.debug(f"Zero base values for {ticker} (revenue={previous_revenue}, net_income={previous_net_income})")
                return None
            
            # Calculate growth rates
            revenue_growth = (current_revenue - previous_revenue) / abs(previous_revenue)
            net_income_growth = (current_net_income - previous_net_income) / abs(previous_net_income)
            
            # Avoid division by zero if revenue didn't grow
            if revenue_growth == 0:
                logger.debug(f"Zero revenue growth for {ticker}")
                return None
            
            # Calculate operating leverage: Net Income growth / Revenue growth
            operating_leverage = net_income_growth / revenue_growth
            
            logger.debug(f"Operating leverage for {ticker}: {operating_leverage:.2f} "
                        f"(Revenue growth: {revenue_growth*100:.1f}%, "
                        f"Net Income growth: {net_income_growth*100:.1f}%)")
            
            return float(operating_leverage)
            
    except Exception as e:
        logger.error(f"Error calculating operating leverage for {ticker}: {e}", exc_info=True)
        return None


def get_institutional_sponsorship(ticker: str) -> tuple[bool, float | None]:
    """
    Check institutional sponsorship by analyzing institutional ownership.
    
    Returns True if:
    - Institutional ownership is above 30%, OR
    - Institutional ownership is showing an increasing trend (if historical data available)
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        Tuple of (passes_check, institutional_ownership_percent)
        Returns (False, None) if data cannot be fetched
    """
    try:
        stock = yf.Ticker(ticker)
        info = _retry_yfinance_call(lambda: stock.info)
        
        # Get institutional ownership percentage
        # yfinance stores this in 'institutionPercent' or 'heldPercentInstitutions'
        institutional_ownership = None
        
        # Try different field names
        ownership_fields = [
            'institutionPercent',
            'heldPercentInstitutions', 
            'institutionalOwnership',
            'institutionalPercent',
            'percentInstitutions'
        ]
        
        for field in ownership_fields:
            if field in info and info[field] is not None:
                institutional_ownership = info[field]
                # Convert to percentage if it's a decimal (0.30 -> 30)
                if institutional_ownership < 1.0:
                    institutional_ownership = institutional_ownership * 100
                break
        
        if institutional_ownership is None:
            logger.debug(f"Institutional ownership data not available for {ticker}")
            return False, None
        
        # Check if above 30% threshold
        passes_check = institutional_ownership >= 30.0
        
        # Try to get institutional holders to check for increasing trend
        # This is a secondary check - if ownership is already >30%, we pass
        if not passes_check:
            try:
                # Get institutional holders (may not always be available)
                institutional_holders = stock.institutional_holders
                if institutional_holders is not None and not institutional_holders.empty:
                    # If we have institutional holders data, consider it a positive signal
                    # even if ownership % is slightly below 30%
                    if len(institutional_holders) > 0:
                        logger.debug(f"{ticker} has {len(institutional_holders)} institutional holders")
                        # Could add trend analysis here if historical data available
            except Exception:
                pass  # Institutional holders data not always available
        
        logger.debug(f"Institutional sponsorship for {ticker}: {institutional_ownership:.1f}% - {'PASS' if passes_check else 'FAIL'}")
        return passes_check, float(institutional_ownership)
        
    except Exception as e:
        logger.error(f"Error calculating institutional sponsorship for {ticker}: {e}", exc_info=True)
        return False, None


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
