"""
Utility functions for CANSLIM Stock Screener.
"""
import re
from typing import List


def validate_ticker(ticker: str) -> bool:
    """
    Validate ticker symbol format.
    
    Args:
        ticker: Stock ticker symbol to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not ticker or not isinstance(ticker, str):
        return False
    
    # Ticker should be 1-5 uppercase alphanumeric characters
    pattern = r'^[A-Z0-9]{1,5}$'
    return bool(re.match(pattern, ticker.upper()))


def normalize_tickers(ticker_input: str) -> List[str]:
    """
    Parse and normalize ticker input string.
    
    Args:
        ticker_input: Comma-separated ticker string
    
    Returns:
        List of normalized (uppercase) ticker symbols
    """
    if not ticker_input:
        return []
    
    # Split by comma, strip whitespace, convert to uppercase
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    
    # Filter out invalid tickers
    valid_tickers = [t for t in tickers if validate_ticker(t)]
    
    return valid_tickers
