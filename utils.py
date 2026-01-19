"""
Utility functions for CANSLIM Stock Screener.
"""
import re
from typing import List

from logger_config import get_logger

logger = get_logger(__name__)


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
    
    # Ticker should be 1-6 uppercase alphanumeric characters (some tickers have dashes)
    # Allow dashes for tickers like BRK-B
    pattern = r'^[A-Z0-9\-]{1,6}$'
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


def validate_ticker_list(tickers: List[str]) -> tuple[List[str], List[str]]:
    """
    Validate a list of tickers and separate valid from invalid.
    
    Args:
        tickers: List of ticker symbols to validate
    
    Returns:
        Tuple of (valid_tickers, invalid_tickers)
    """
    valid = []
    invalid = []
    
    for ticker in tickers:
        if validate_ticker(ticker):
            valid.append(ticker.upper())
        else:
            invalid.append(ticker)
    
    if invalid:
        logger.warning(f"Invalid tickers filtered out: {invalid}")
    
    return valid, invalid


def clean_fetched_tickers(tickers: List[str]) -> List[str]:
    """
    Clean and validate tickers fetched from external sources (Wikipedia, etc).
    
    Args:
        tickers: Raw list of tickers from scraping
    
    Returns:
        Cleaned list of valid ticker symbols
    """
    cleaned = []
    
    for ticker in tickers:
        if not ticker or not isinstance(ticker, str):
            continue
        
        # Clean the ticker
        t = ticker.strip().upper()
        
        # Replace dots with dashes (e.g., BRK.B -> BRK-B)
        t = t.replace('.', '-')
        
        # Remove any non-alphanumeric characters except dashes
        t = re.sub(r'[^A-Z0-9\-]', '', t)
        
        # Validate
        if validate_ticker(t):
            cleaned.append(t)
    
    logger.info(f"Cleaned {len(tickers)} tickers to {len(cleaned)} valid symbols")
    return cleaned


def deduplicate_tickers(tickers: List[str]) -> List[str]:
    """
    Remove duplicate tickers while preserving order.
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Deduplicated list
    """
    seen = set()
    result = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result
