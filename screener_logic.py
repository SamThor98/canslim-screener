import time
import pandas as pd
import yfinance as yf

from canslim_metrics import get_earnings_growth, get_price_strength
from fetcher import fetch_company_metadata


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
        hist = stock.history(period="3mo")  # ~63 trading days
        
        if hist.empty or len(hist) < period:
            print(f"Insufficient data for {period}-day SMA for {ticker}")
            return None, None, None
        
        # Calculate SMA
        close_prices = hist["Close"]
        sma = close_prices.rolling(window=period).mean().iloc[-1]
        current_price = close_prices.iloc[-1]
        
        is_above_sma = current_price > sma
        
        return is_above_sma, float(current_price), float(sma)
        
    except Exception as e:
        print(f"Error calculating SMA trend for {ticker}: {e}")
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
    
    print(f"Screening {len(tickers)} tickers...")
    print("=" * 60)
    
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Analyzing {ticker}...")
        
        try:
            # (C) Current Earnings - check if growth > 20%
            earnings_growth = get_earnings_growth(ticker)
            time.sleep(0.5)  # Rate limit delay
            
            c_pass = earnings_growth is not None and earnings_growth > 0.20
            
            # (L) Leader - check if relative strength > 1.0
            relative_strength = get_price_strength(ticker)
            time.sleep(0.5)  # Rate limit delay
            
            l_pass = relative_strength is not None and relative_strength > 1.0
            
            # (Trend) - check if price > 50-day SMA
            is_above_sma, current_price, sma_50 = get_sma_trend(ticker)
            time.sleep(0.5)  # Rate limit delay
            
            trend_pass = bool(is_above_sma) if is_above_sma is not None else False
            
            # Log individual results
            c_status = f"{earnings_growth * 100:.1f}%" if earnings_growth else "N/A"
            l_status = f"{relative_strength:.2f}" if relative_strength else "N/A"
            trend_status = "Above" if is_above_sma else ("Below" if is_above_sma is False else "N/A")
            
            print(f"  (C) Earnings Growth: {c_status} {'[PASS]' if c_pass else '[FAIL]'}")
            print(f"  (L) Relative Strength: {l_status} {'[PASS]' if l_pass else '[FAIL]'}")
            print(f"  (Trend) vs 50-SMA: {trend_status} {'[PASS]' if trend_pass else '[FAIL]'}")
            
            # Check if all criteria pass
            if c_pass and l_pass and trend_pass:
                print(f"  >>> {ticker} PASSES all criteria!")
                
                # Fetch company metadata for additional context
                metadata = fetch_company_metadata(ticker)
                time.sleep(0.5)  # Rate limit delay
                
                results.append({
                    "Ticker": ticker,
                    "Company": metadata.name,
                    "Sector": metadata.sector,
                    "Industry": metadata.industry,
                    "Earnings Growth (%)": round(earnings_growth * 100, 1),
                    "Relative Strength": round(relative_strength, 2),
                    "Current Price": round(current_price, 2),
                    "50-Day SMA": round(sma_50, 2),
                    "Price vs SMA (%)": round((current_price / sma_50 - 1) * 100, 1),
                })
            else:
                print(f"  --- {ticker} does not pass all criteria")
                
        except Exception as e:
            print(f"  Error processing {ticker}: {e}")
            continue
    
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
