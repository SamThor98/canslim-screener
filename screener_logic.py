import time
import pandas as pd
import yfinance as yf

from canslim_metrics import get_earnings_growth, get_price_strength
from fetcher import fetch_company_metadata, _retry_yfinance_call
from database import get_cached_screen, save_screen_result
from config import config
from logger_config import get_logger

logger = get_logger(__name__)


def get_sma_trend(ticker: str, period: int = 50) -> tuple[bool | None, float | None, float | None]:
    """
    Check if current price is above the Simple Moving Average (SMA).
    
    Args:
        ticker: Stock ticker symbol
        period: SMA period in days (default: 50)
    
    Returns:
        Tuple of (is_above_sma, current_price, sma_value)
        Returns (None, None, None) if data cannot be fetched
    """
    try:
        # Fetch enough data to calculate SMA (need at least 'period' days)
        stock = yf.Ticker(ticker)
        hist = _retry_yfinance_call(lambda: stock.history(period="3mo"))  # ~63 trading days
        
        if hist.empty or len(hist) < period:
            logger.warning(f"Insufficient data for {period}-day SMA for {ticker}")
            return None, None, None
        
        # Calculate SMA
        close_prices = hist["Close"]
        sma = close_prices.rolling(window=period).mean().iloc[-1]
        current_price = close_prices.iloc[-1]
        
        is_above_sma = current_price > sma
        
        return is_above_sma, float(current_price), float(sma)
        
    except ValueError as e:
        logger.error(f"Value error calculating SMA trend for {ticker}: {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"Error calculating SMA trend for {ticker}: {e}", exc_info=True)
        return None, None, None


def run_canslim_screen(tickers: list[str]) -> pd.DataFrame:
    """
    Run a CANSLIM-inspired screen on a list of tickers.
    
    Checks three criteria:
    - (C) Current Earnings: YoY earnings growth > 20%
    - (L) Leader: Relative strength > 1.0 (outperforming S&P 500)
    - (Trend): Current price above 50-day SMA
    
    Args:
        tickers: List of stock ticker symbols to screen
    
    Returns:
        DataFrame of stocks passing all criteria with their metrics
    """
    results = []
    
    logger.info(f"Screening {len(tickers)} tickers...")
    print("=" * 60)
    
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Analyzing {ticker}...")
        
        try:
            # Check cache first
            cached_data = get_cached_screen(ticker, max_age_hours=24)
            
            if cached_data:
                # Use cached data
                logger.info(f"Using cached data for {ticker}")
                earnings_growth = cached_data.get("earnings_growth")
                relative_strength = cached_data.get("relative_strength")
                current_price = cached_data.get("current_price")
                sma_50 = cached_data.get("sma_50")
                is_above_sma = cached_data.get("is_above_sma")
                metadata_name = cached_data.get("company_name")
                metadata_sector = cached_data.get("sector")
                metadata_industry = cached_data.get("industry")
            else:
                # Fetch from API
                logger.info(f"Fetching fresh data for {ticker} from API")
                
                # (C) Current Earnings - check if growth > threshold
                earnings_growth = get_earnings_growth(ticker)
                time.sleep(config.rate_limit_delay)  # Rate limit delay
                
                # (L) Leader - check if relative strength > threshold
                relative_strength = get_price_strength(ticker)
                time.sleep(config.rate_limit_delay)  # Rate limit delay
                
                # (Trend) - check if price > SMA
                is_above_sma, current_price, sma_50 = get_sma_trend(ticker, period=config.sma_period)
                time.sleep(config.rate_limit_delay)  # Rate limit delay
                
                # Fetch company metadata
                metadata = fetch_company_metadata(ticker)
                metadata_name = metadata.name
                metadata_sector = metadata.sector
                metadata_industry = metadata.industry
                
                # Cache the results
                cache_data = {
                    "earnings_growth": earnings_growth,
                    "relative_strength": relative_strength,
                    "current_price": current_price,
                    "sma_50": sma_50,
                    "is_above_sma": is_above_sma,
                    "company_name": metadata_name,
                    "sector": metadata_sector,
                    "industry": metadata_industry,
                }
                save_screen_result(ticker, cache_data)
            
            # Evaluate criteria
            c_pass = earnings_growth is not None and earnings_growth > config.earnings_growth_threshold
            l_pass = relative_strength is not None and relative_strength > config.relative_strength_threshold
            trend_pass = bool(is_above_sma) if is_above_sma is not None else False
            
            # Log individual results
            c_status = f"{earnings_growth * 100:.1f}%" if earnings_growth else "N/A"
            l_status = f"{relative_strength:.2f}" if relative_strength else "N/A"
            trend_status = "Above" if is_above_sma else ("Below" if is_above_sma is False else "N/A")
            
            print(f"  (C) Earnings Growth: {c_status} {'[PASS]' if c_pass else '[FAIL]'}")
            print(f"  (L) Relative Strength: {l_status} {'[PASS]' if l_pass else '[FAIL]'}")
            print(f"  (Trend) vs {config.sma_period}-SMA: {trend_status} {'[PASS]' if trend_pass else '[FAIL]'}")
            
            # Check if all criteria pass
            if c_pass and l_pass and trend_pass:
                logger.info(f"{ticker} PASSES all criteria!")
                print(f"  >>> {ticker} PASSES all criteria!")
                
                results.append({
                    "Ticker": ticker,
                    "Company": metadata_name or ticker,
                    "Sector": metadata_sector or "N/A",
                    "Industry": metadata_industry or "N/A",
                    "Earnings Growth (%)": round(earnings_growth * 100, 1) if earnings_growth else None,
                    "Relative Strength": round(relative_strength, 2) if relative_strength else None,
                    "Current Price": round(current_price, 2) if current_price else None,
                    "50-Day SMA": round(sma_50, 2) if sma_50 else None,
                    "Price vs SMA (%)": round((current_price / sma_50 - 1) * 100, 1) if current_price and sma_50 else None,
                })
            else:
                logger.debug(f"{ticker} does not pass all criteria (C:{c_pass}, L:{l_pass}, T:{trend_pass})")
                print(f"  --- {ticker} does not pass all criteria")
                
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}", exc_info=True)
            print(f"  Error processing {ticker}: {e}")
            continue
    
    logger.info(f"Screening complete. {len(results)} stocks passed all criteria.")
    print("\n" + "=" * 60)
    print(f"Screening complete. {len(results)} stocks passed all criteria.")
    
    # Create DataFrame
    if results:
        df = pd.DataFrame(results)
        # Sort by relative strength (strongest leaders first)
        df = df.sort_values("Relative Strength", ascending=False).reset_index(drop=True)
        return df
    else:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=[
            "Ticker", "Company", "Sector", "Industry",
            "Earnings Growth (%)", "Relative Strength",
            "Current Price", "50-Day SMA", "Price vs SMA (%)"
        ])


if __name__ == "__main__":
    # Example: Screen some well-known stocks
    sample_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "CRM", "NFLX"
    ]
    
    print("CANSLIM Stock Screener")
    print("Criteria: (C) Earnings > 20% | (L) RS > 1.0 | (Trend) Price > 50-SMA")
    print()
    
    results_df = run_canslim_screen(sample_tickers)
    
    if not results_df.empty:
        print("\n" + "=" * 60)
        print("STOCKS PASSING CANSLIM SCREEN:")
        print("=" * 60)
        print(results_df.to_string(index=False))
    else:
        print("\nNo stocks passed all criteria.")
