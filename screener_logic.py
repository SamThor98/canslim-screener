import time
import pandas as pd
import yfinance as yf

from canslim_metrics import get_earnings_growth, get_price_strength, calculate_operating_leverage, get_institutional_sponsorship
from fetcher import fetch_company_metadata, _retry_yfinance_call
from database import get_cached_screen, save_screen_result
from ai_analyst import analyze_company_story
from config import config
from logger_config import get_logger

logger = get_logger(__name__)


def get_volatility_check(ticker: str) -> tuple[bool | None, float | None]:
    """
    Check if 20-day price range is less than 5%.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Tuple of (passes_check, price_range_percent)
        Returns (None, None) if data cannot be fetched
    """
    try:
        stock = yf.Ticker(ticker)
        hist = _retry_yfinance_call(lambda: stock.history(period="1mo"))  # Get ~22 trading days
        
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


def validate_trend_template(ticker: str) -> tuple[bool, dict]:
    """
    Validate Professional Trend Template for CANSLIM screening.
    
    Requirements:
    1. Price > SMA 150 AND Price > SMA 200
    2. SMA 150 > SMA 200
    3. SMA 200 is trending up (current vs 20 days ago)
    4. Price is within 25% of 52-week high
    5. Price is at least 30% above 52-week low
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Tuple of (passes_all_checks, details_dict)
        details_dict contains: current_price, sma_150, sma_200, 
        price_vs_52w_high_pct, price_vs_52w_low_pct, sma_200_trend
    """
    try:
        stock = yf.Ticker(ticker)
        # Need at least 250 trading days (~1 year) for 200-day SMA and 52-week data
        hist = _retry_yfinance_call(lambda: stock.history(period="1y"))
        
        if hist.empty or len(hist) < 250:
            logger.warning(f"Insufficient data for trend template validation for {ticker}")
            return False, {}
        
        # Calculate SMAs
        close_prices = hist["Close"]
        sma_150 = close_prices.rolling(window=150).mean()
        sma_200 = close_prices.rolling(window=200).mean()
        
        # Get current values
        current_price = float(close_prices.iloc[-1])
        current_sma_150 = float(sma_150.iloc[-1])
        current_sma_200 = float(sma_200.iloc[-1])
        
        # Check 1: Price > SMA 150 AND Price > SMA 200
        price_above_150 = current_price > current_sma_150
        price_above_200 = current_price > current_sma_200
        check1 = price_above_150 and price_above_200
        
        # Check 2: SMA 150 > SMA 200
        check2 = current_sma_150 > current_sma_200
        
        # Check 3: SMA 200 trending up (current vs 20 days ago)
        if len(sma_200) >= 20:
            sma_200_current = current_sma_200
            sma_200_20_days_ago = float(sma_200.iloc[-20])
            sma_200_trending_up = sma_200_current > sma_200_20_days_ago
            sma_200_trend_pct = ((sma_200_current - sma_200_20_days_ago) / sma_200_20_days_ago) * 100
        else:
            sma_200_trending_up = False
            sma_200_trend_pct = 0.0
        check3 = sma_200_trending_up
        
        # Get 52-week high and low
        high_52w = float(hist["High"].tail(252).max())  # ~1 year of trading days
        low_52w = float(hist["Low"].tail(252).min())
        
        # Check 4: Price within 25% of 52-week high
        price_vs_52w_high_pct = ((current_price - high_52w) / high_52w) * 100
        check4 = price_vs_52w_high_pct >= -25.0  # Within 25% means no more than 25% below
        
        # Check 5: Price at least 30% above 52-week low
        price_vs_52w_low_pct = ((current_price - low_52w) / low_52w) * 100
        check5 = price_vs_52w_low_pct >= 30.0
        
        # All checks must pass
        passes_all = check1 and check2 and check3 and check4 and check5
        
        details = {
            "current_price": current_price,
            "sma_150": current_sma_150,
            "sma_200": current_sma_200,
            "price_vs_52w_high_pct": round(price_vs_52w_high_pct, 2),
            "price_vs_52w_low_pct": round(price_vs_52w_low_pct, 2),
            "sma_200_trend_pct": round(sma_200_trend_pct, 2),
            "check1_price_above_smas": check1,
            "check2_sma_150_above_200": check2,
            "check3_sma_200_trending_up": check3,
            "check4_within_25pct_high": check4,
            "check5_30pct_above_low": check5,
        }
        
        if passes_all:
            logger.info(f"{ticker} PASSES trend template validation")
        else:
            logger.debug(f"{ticker} FAILS trend template: {[k for k, v in details.items() if k.startswith('check') and not v]}")
        
        return passes_all, details
        
    except Exception as e:
        logger.error(f"Error validating trend template for {ticker}: {e}", exc_info=True)
        return False, {}


def get_sma_trend(ticker: str, period: int = 50) -> tuple[bool | None, float | None, float | None]:
    """
    Check if current price is above the Simple Moving Average (SMA).
    Legacy function for backward compatibility.
    
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
                
                # Professional Trend Template validation (replaces simple SMA check)
                trend_pass, trend_details = validate_trend_template(ticker)
                time.sleep(config.rate_limit_delay)  # Rate limit delay
                
                # Volatility check: 20-day price range must be less than 5%
                volatility_pass, price_range = get_volatility_check(ticker)
                time.sleep(config.rate_limit_delay)  # Rate limit delay
                
                # Institutional Sponsorship check
                inst_sponsor_pass, inst_ownership = get_institutional_sponsorship(ticker)
                time.sleep(config.rate_limit_delay)  # Rate limit delay
                
                # Operating leverage calculation
                operating_leverage = calculate_operating_leverage(ticker)
                
                # Fetch company metadata
                metadata = fetch_company_metadata(ticker)
                metadata_name = metadata.name
                metadata_sector = metadata.sector
                metadata_industry = metadata.industry
                
                # Early AI qualitative filtering (N and S criteria)
                ai_story_pass, ai_story_reason = analyze_company_story(
                    ticker,
                    {"name": metadata_name, "sector": metadata_sector, "industry": metadata_industry}
                )
                
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
            volatility_check = bool(volatility_pass) if volatility_pass is not None else False
            # trend_pass is already boolean from validate_trend_template
            inst_sponsor_check = inst_sponsor_pass  # Already boolean from get_institutional_sponsorship
            ai_story_check = ai_story_pass  # Already boolean from analyze_company_story
            
            # Log individual results
            c_status = f"{earnings_growth * 100:.1f}%" if earnings_growth else "N/A"
            l_status = f"{relative_strength:.2f}" if relative_strength else "N/A"
            trend_status = "PASS" if trend_pass else "FAIL"
            volatility_status = f"{price_range * 100:.2f}%" if price_range is not None else "N/A"
            inst_status = f"{inst_ownership:.1f}%" if inst_ownership else "N/A"
            ai_status = "PASS" if ai_story_check else "FAIL"
            
            print(f"  (C) Earnings Growth: {c_status} {'[PASS]' if c_pass else '[FAIL]'}")
            print(f"  (L) Relative Strength: {l_status} {'[PASS]' if l_pass else '[FAIL]'}")
            print(f"  (Trend Template): {trend_status} {'[PASS]' if trend_pass else '[FAIL]'}")
            print(f"  (I) Institutional Support: {inst_status} {'[PASS]' if inst_sponsor_check else '[FAIL]'}")
            print(f"  (Volatility) 20-Day Range: {volatility_status} {'[PASS]' if volatility_check else '[FAIL]'}")
            print(f"  (N/S) AI Story Analysis: {ai_status} {'[PASS]' if ai_story_check else '[FAIL]'}")
            
            # Check if all criteria pass
            if c_pass and l_pass and trend_pass and volatility_check and inst_sponsor_check and ai_story_check:
                logger.info(f"{ticker} PASSES all criteria!")
                print(f"  >>> {ticker} PASSES all criteria!")
                
                current_price = trend_details.get("current_price", 0) if trend_details else 0
                results.append({
                    "Ticker": ticker,
                    "Company": metadata_name or ticker,
                    "Sector": metadata_sector or "N/A",
                    "Industry": metadata_industry or "N/A",
                    "Earnings Growth (%)": round(earnings_growth * 100, 1) if earnings_growth else None,
                    "Relative Strength": round(relative_strength, 2) if relative_strength else None,
                    "Current Price": round(current_price, 2) if current_price else None,
                    "Operating Leverage": round(operating_leverage, 2) if operating_leverage is not None else None,
                    "Institutional Support": f"{inst_ownership:.1f}%" if inst_ownership else "N/A",
                    "Trend Template Pass": "✓" if trend_pass else "✗",
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
        # Sort by Operating Leverage (highest first), handling None values
        df = df.sort_values(
            "Operating Leverage", 
            ascending=False, 
            na_position='last'
        ).reset_index(drop=True)
        return df
    else:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=[
            "Ticker", "Company", "Sector", "Industry",
            "Earnings Growth (%)", "Relative Strength",
            "Current Price", "Operating Leverage",
            "Institutional Support", "Trend Template Pass"
        ])


if __name__ == "__main__":
    # Example: Screen some well-known stocks
    sample_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "CRM", "NFLX"
    ]
    
    print("CANSLIM Stock Screener")
    print("Criteria: (C) Earnings > 20% | (L) RS > 1.0 | (Trend Template) Professional | (I) Institutional >30% | (Volatility) 20-Day Range < 5% | (N/S) AI Qualitative")
    print()
    
    results_df = run_canslim_screen(sample_tickers)
    
    if not results_df.empty:
        print("\n" + "=" * 60)
        print("STOCKS PASSING CANSLIM SCREEN:")
        print("=" * 60)
        print(results_df.to_string(index=False))
    else:
        print("\nNo stocks passed all criteria.")
