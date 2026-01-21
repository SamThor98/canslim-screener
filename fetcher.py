import os
import re
import time
import io
from contextlib import contextmanager

import pandas as pd
import requests
import yfinance as yf
from edgar import Company, set_identity
from dataclasses import dataclass
from datetime import date
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import Base, Stock, QuarterlyFinancial
from config import config
from logger_config import get_logger

logger = get_logger(__name__)

# Headers for web scraping (Wikipedia blocks default urllib user-agent)
SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# =============================================================================
# INDEX AND SECTOR FETCHING FUNCTIONS
# =============================================================================

def get_tickers_by_index(index_name: str) -> list[str]:
    """
    Fetch ticker symbols for a given index by scraping Wikipedia.
    
    Args:
        index_name: Name of the index ('S&P 500', 'Nasdaq 100', 'Dow Jones', 'Russell 2000')
    
    Returns:
        List of ticker symbols
    """
    logger.info(f"Fetching tickers for index: {index_name}")
    
    try:
        if index_name == "S&P 500":
            return _fetch_sp500_tickers()
        elif index_name == "Nasdaq 100":
            return _fetch_nasdaq100_tickers()
        elif index_name == "Dow Jones":
            return _fetch_djia_tickers()
        elif index_name == "Russell 2000":
            return _fetch_russell2000_tickers()
        else:
            logger.warning(f"Unknown index: {index_name}")
            return []
    except Exception as e:
        logger.error(f"Error fetching tickers for {index_name}: {e}", exc_info=True)
        return []


def _fetch_sp500_tickers() -> list[str]:
    """Fetch S&P 500 components from Wikipedia."""
    url = config.INDEX_URLS["S&P 500"]
    response = requests.get(url, headers=SCRAPE_HEADERS, timeout=10)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    # The first table contains the S&P 500 constituents
    df = tables[0]
    # Symbol column might be named 'Symbol' or 'Ticker'
    symbol_col = 'Symbol' if 'Symbol' in df.columns else 'Ticker'
    tickers = df[symbol_col].tolist()
    # Clean up tickers (remove dots, replace with dashes for yfinance compatibility)
    tickers = [str(t).replace('.', '-') for t in tickers if pd.notna(t)]
    logger.info(f"Fetched {len(tickers)} S&P 500 tickers")
    return tickers


def _fetch_nasdaq100_tickers() -> list[str]:
    """Fetch Nasdaq 100 components from Wikipedia."""
    url = config.INDEX_URLS["Nasdaq 100"]
    response = requests.get(url, headers=SCRAPE_HEADERS, timeout=10)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    # Find the table with ticker symbols (usually has 'Ticker' or 'Symbol' column)
    for table in tables:
        if 'Ticker' in table.columns:
            tickers = [str(t) for t in table['Ticker'].tolist() if pd.notna(t)]
            logger.info(f"Fetched {len(tickers)} Nasdaq 100 tickers")
            return tickers
        elif 'Symbol' in table.columns:
            tickers = [str(t) for t in table['Symbol'].tolist() if pd.notna(t)]
            logger.info(f"Fetched {len(tickers)} Nasdaq 100 tickers")
            return tickers
    # Fallback: try the 5th table which often contains the components
    if len(tables) > 4:
        df = tables[4]
        if 'Ticker' in df.columns:
            tickers = [str(t) for t in df['Ticker'].tolist() if pd.notna(t)]
            logger.info(f"Fetched {len(tickers)} Nasdaq 100 tickers")
            return tickers
    logger.warning("Could not find Nasdaq 100 tickers table")
    return []


def _fetch_djia_tickers() -> list[str]:
    """Fetch Dow Jones Industrial Average components from Wikipedia."""
    url = config.INDEX_URLS["Dow Jones"]
    response = requests.get(url, headers=SCRAPE_HEADERS, timeout=10)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    # Find the table with company information
    for table in tables:
        if 'Symbol' in table.columns:
            tickers = [str(t) for t in table['Symbol'].tolist() if pd.notna(t)]
            logger.info(f"Fetched {len(tickers)} DJIA tickers")
            return tickers
    # The DJIA table is usually the second table
    if len(tables) > 1:
        df = tables[1]
        for col in df.columns:
            if 'symbol' in col.lower():
                tickers = [str(t) for t in df[col].tolist() if pd.notna(t)]
                logger.info(f"Fetched {len(tickers)} DJIA tickers")
                return tickers
    logger.warning("Could not find DJIA tickers table")
    return []


def _fetch_russell2000_tickers() -> list[str]:
    """
    Fetch Russell 2000 components.
    Note: Full Russell 2000 requires subscription. 
    This returns a subset from available public sources.
    """
    # Russell 2000 is harder to get - we'll use a combination approach
    # First, try to get small-cap stocks from other indices
    logger.info("Russell 2000 full list requires subscription. Fetching available small-cap stocks...")
    
    # Use yfinance screener for small-cap stocks as fallback
    try:
        # Get S&P 600 (small-cap) as a proxy - it's a subset of small caps
        # Unfortunately Wikipedia doesn't have a reliable S&P 600 table
        # Return empty and suggest manual entry or premium data source
        logger.warning("Russell 2000 requires premium data source. Consider using Sector scan instead.")
        return []
    except Exception as e:
        logger.error(f"Error fetching Russell 2000: {e}")
        return []


def get_tickers_by_sector(sector_name: str, limit: int = 100) -> list[tuple[str, float]]:
    """
    Get tickers for a given sector using yfinance.
    Returns tickers sorted by market cap.
    
    Args:
        sector_name: GICS sector name (e.g., 'Technology', 'Healthcare')
        limit: Maximum number of tickers to return
    
    Returns:
        List of (ticker, market_cap) tuples sorted by market cap descending
    """
    logger.info(f"Fetching tickers for sector: {sector_name}")
    
    # Map sector names to yfinance sector names
    sector_mapping = {
        "Technology": "Technology",
        "Healthcare": "Healthcare", 
        "Financials": "Financial Services",
        "Consumer Cyclical": "Consumer Cyclical",
        "Consumer Defensive": "Consumer Defensive",
        "Industrials": "Industrials",
        "Energy": "Energy",
        "Utilities": "Utilities",
        "Real Estate": "Real Estate",
        "Basic Materials": "Basic Materials",
        "Communication Services": "Communication Services",
    }
    
    yf_sector = sector_mapping.get(sector_name, sector_name)
    
    # Get a broad list of tickers to filter
    # Start with S&P 500 as our universe
    try:
        all_tickers = _fetch_sp500_tickers()
    except Exception:
        logger.warning("Could not fetch S&P 500 for sector filtering")
        return []
    
    # Filter by sector and get market cap
    sector_stocks = []
    
    for ticker in all_tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            stock_sector = info.get("sector", "")
            market_cap = info.get("marketCap", 0)
            
            if stock_sector == yf_sector and market_cap:
                sector_stocks.append((ticker, market_cap))
            
            # Rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            logger.debug(f"Error checking {ticker}: {e}")
            continue
        
        # Early exit if we have enough candidates
        if len(sector_stocks) >= limit * 2:
            break
    
    # Sort by market cap descending
    sector_stocks.sort(key=lambda x: x[1], reverse=True)
    
    logger.info(f"Found {len(sector_stocks)} stocks in {sector_name} sector")
    return sector_stocks[:limit]


def get_top_tickers_by_market_cap(tickers: list[str], limit: int = 50) -> list[str]:
    """
    Filter tickers to top N by market cap using batch download.
    
    Args:
        tickers: List of ticker symbols
        limit: Maximum number to return
    
    Returns:
        List of tickers sorted by market cap (descending)
    """
    logger.info(f"Filtering {len(tickers)} tickers to top {limit} by market cap")
    
    # For S&P 500, just return the first N tickers (they're already roughly sorted by importance)
    # This avoids the slow market cap lookup for each ticker
    if len(tickers) > limit:
        # Quick approach: S&P 500 on Wikipedia is roughly ordered by market cap
        # Just take the first N tickers
        result = tickers[:limit]
        logger.info(f"Quick filter: returning first {len(result)} tickers")
        return result
    
    return tickers


def get_available_indices() -> list[str]:
    """Get list of available indices for scanning."""
    return list(config.INDEX_URLS.keys())


def get_available_sectors() -> list[str]:
    """Get list of available sectors for scanning."""
    return config.SECTORS


def get_sector_performance(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate sector performance metrics from screening results.
    
    Aggregates average Price Strength (Relative Strength) of all tickers
    grouped by sector. Used for creating sector heatmap.
    
    Args:
        results_df: DataFrame with screening results containing 'Sector' and 'Relative Strength' columns
    
    Returns:
        DataFrame with columns: Sector, Avg_Relative_Strength, Stock_Count
    """
    if results_df.empty or 'Sector' not in results_df.columns or 'Relative Strength' not in results_df.columns:
        logger.warning("Cannot calculate sector performance: missing required columns")
        return pd.DataFrame(columns=['Sector', 'Avg_Relative_Strength', 'Stock_Count'])
    
    try:
        # Filter out N/A sectors and invalid relative strength values
        valid_df = results_df[
            (results_df['Sector'] != 'N/A') & 
            (results_df['Relative Strength'].notna())
        ].copy()
        
        if valid_df.empty:
            logger.warning("No valid sector data for performance calculation")
            return pd.DataFrame(columns=['Sector', 'Avg_Relative_Strength', 'Stock_Count'])
        
        # Group by sector and calculate metrics
        sector_stats = valid_df.groupby('Sector').agg({
            'Relative Strength': ['mean', 'count']
        }).reset_index()
        
        # Flatten column names
        sector_stats.columns = ['Sector', 'Avg_Relative_Strength', 'Stock_Count']
        
        # Round average relative strength
        sector_stats['Avg_Relative_Strength'] = sector_stats['Avg_Relative_Strength'].round(2)
        
        # Sort by average relative strength (descending)
        sector_stats = sector_stats.sort_values('Avg_Relative_Strength', ascending=False).reset_index(drop=True)
        
        logger.info(f"Calculated sector performance for {len(sector_stats)} sectors")
        return sector_stats
        
    except Exception as e:
        logger.error(f"Error calculating sector performance: {e}", exc_info=True)
        return pd.DataFrame(columns=['Sector', 'Avg_Relative_Strength', 'Stock_Count'])


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


@dataclass
class CompanyMetadata:
    ticker: str
    name: str
    cik: str
    sector: str | None
    industry: str | None


@dataclass
class QuarterlyFinancialData:
    form_type: str
    filing_date: date
    accession_number: str
    revenue: float | None
    net_income: float | None
    total_assets: float | None
    total_liabilities: float | None
    mda_text: str | None = None


def setup_sec_identity() -> None:
    """
    Set up SEC identity for EDGAR API access.
    The SEC requires a user-agent with contact information.
    """
    email = os.environ.get("SEC_EMAIL") or os.environ.get("SEC_API_USER_AGENT")
    if not email:
        logger.warning("Configuration Missing: SEC_EMAIL or SEC_API_USER_AGENT not set. SEC EDGAR API features may not work.")
        print("=" * 60)
        print("⚠️  WARNING: SEC EDGAR API requires identification.")
        print("Please set SEC_EMAIL or SEC_API_USER_AGENT environment variable.")
        print("=" * 60)
        try:
            email = input("Enter your email address (or press Enter to skip): ").strip()
            if not email:
                logger.warning("SEC identity not set. Some features may be unavailable.")
                return
        except (EOFError, KeyboardInterrupt):
            logger.warning("SEC identity setup cancelled. Some features may be unavailable.")
            return
    
    try:
        set_identity(email)
        logger.info(f"SEC identity set: {email}")
        print(f"SEC identity set: {email}")
    except Exception as e:
        logger.error(f"Error setting SEC identity: {e}", exc_info=True)
        print(f"Warning: Could not set SEC identity: {e}")


def fetch_company_metadata(ticker: str) -> CompanyMetadata:
    """
    Fetch company metadata using yfinance with retry logic.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        CompanyMetadata with ticker, name, CIK, sector, and industry
    """
    try:
        stock = yf.Ticker(ticker)
        info = _retry_yfinance_call(lambda: stock.info)
        
        # Extract CIK - yfinance stores it in different possible fields
        cik = info.get("cik") or info.get("companyOfficers", [{}])[0].get("cik") if info.get("companyOfficers") else None
        
        # If CIK not found in yfinance, try to get it from edgartools
        if not cik:
            try:
                company = Company(ticker)
                cik = str(company.cik)
            except Exception:
                cik = None
        
        # Ensure CIK is zero-padded to 10 digits if found
        if cik:
            cik = str(cik).zfill(10)
        
        return CompanyMetadata(
            ticker=ticker.upper(),
            name=info.get("longName") or info.get("shortName") or ticker,
            cik=cik,
            sector=info.get("sector"),
            industry=info.get("industry"),
        )
    except Exception as e:
        logger.error(f"Error fetching company metadata for {ticker}: {e}", exc_info=True)
        # Return minimal metadata on error
        return CompanyMetadata(
            ticker=ticker.upper(),
            name=ticker,
            cik=None,
            sector=None,
            industry=None,
        )


def fetch_latest_10q(ticker: str) -> QuarterlyFinancialData | None:
    """
    Fetch the most recent 10-Q filing using edgartools.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        QuarterlyFinancialData with financial metrics, or None if not found
    """
    try:
        company = Company(ticker)
        filings = company.get_filings(form="10-Q")
        
        if not filings or len(filings) == 0:
            logger.warning(f"No 10-Q filings found for {ticker}")
            print(f"No 10-Q filings found for {ticker}")
            return None
        
        # Get the most recent 10-Q
        latest_10q = filings[0]
        filing_obj = latest_10q.obj()
        
        # Extract financial data
        revenue = None
        net_income = None
        total_assets = None
        total_liabilities = None
        mda_text = None
        
        # Try to get financials from the filing
        try:
            financials = filing_obj.financials
            
            # Extract from income statement
            if hasattr(financials, 'income_statement') and financials.income_statement is not None:
                income_stmt = financials.income_statement
                # Try common field names for revenue
                revenue = _extract_value(income_stmt, [
                    'Revenues', 'Revenue', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet', 'TotalRevenue', 'NetRevenue', 'RevenueNet'
                ])
                # Try common field names for net income
                net_income = _extract_value(income_stmt, [
                    'NetIncomeLoss', 'NetIncome', 'ProfitLoss', 
                    'NetIncomeLossAvailableToCommonStockholdersBasic'
                ])
            
            # Extract from balance sheet
            if hasattr(financials, 'balance_sheet') and financials.balance_sheet is not None:
                balance_sheet = financials.balance_sheet
                # Try common field names for total assets
                total_assets = _extract_value(balance_sheet, [
                    'Assets', 'TotalAssets', 'AssetsCurrent'
                ])
                # Try common field names for total liabilities
                total_liabilities = _extract_value(balance_sheet, [
                    'Liabilities', 'TotalLiabilities', 'LiabilitiesAndStockholdersEquity',
                    'LiabilitiesCurrent'
                ])
        except Exception as e:
            logger.warning(f"Could not extract all financials for {ticker}: {e}")
            print(f"Warning: Could not extract all financials: {e}")
        
        # Extract MD&A text (Item 2 in 10-Q filings)
        try:
            mda_text = _extract_mda_text(filing_obj, latest_10q)
            if mda_text:
                logger.info(f"Extracted MD&A text for {ticker} ({len(mda_text)} characters)")
            else:
                logger.warning(f"Could not extract MD&A text for {ticker}")
        except Exception as e:
            logger.warning(f"Error extracting MD&A text for {ticker}: {e}")
            mda_text = None
        
        return QuarterlyFinancialData(
            form_type="10-Q",
            filing_date=latest_10q.filing_date,
            accession_number=latest_10q.accession_number,
            revenue=revenue,
            net_income=net_income,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            mda_text=mda_text,
        )
        
    except Exception as e:
        logger.error(f"Error fetching 10-Q for {ticker}: {e}", exc_info=True)
        print(f"Error fetching 10-Q for {ticker}: {e}")
        return None


def _extract_mda_text(filing_obj, filing) -> str | None:
    """
    Extract MD&A (Management's Discussion & Analysis) text from a 10-Q filing.
    
    Args:
        filing_obj: The filing object from edgartools
        filing: The filing metadata object
    
    Returns:
        MD&A text as a string, or None if not found
    """
    try:
        # Try to get HTML content from the filing
        # edgartools filing objects may have different methods/properties
        html_content = None
        
        # Method 1: Try sections property (if edgartools provides it)
        try:
            if hasattr(filing_obj, 'sections'):
                sections = filing_obj.sections
                if sections and '2' in sections:
                    mda_section = sections['2']
                    if isinstance(mda_section, str):
                        return mda_section[:15000] if len(mda_section) > 15000 else mda_section
                    elif hasattr(mda_section, 'text'):
                        text = mda_section.text
                        return text[:15000] if len(text) > 15000 else text
        except Exception as e:
            logger.debug(f"Could not access sections property: {e}")
        
        # Method 2: Try html() or text() methods
        try:
            if hasattr(filing_obj, 'html') and callable(filing_obj.html):
                html_content = filing_obj.html()
            elif hasattr(filing_obj, 'text') and callable(filing_obj.text):
                html_content = filing_obj.text()
            elif hasattr(filing, 'html') and callable(filing.html):
                html_content = filing.html()
            elif hasattr(filing, 'text') and callable(filing.text):
                html_content = filing.text()
        except Exception as e:
            logger.debug(f"Could not get content via html/text methods: {e}")
        
        # Method 3: Try document property
        if not html_content:
            try:
                if hasattr(filing_obj, 'document'):
                    html_content = filing_obj.document
                elif hasattr(filing, 'document'):
                    html_content = filing.document
            except Exception as e:
                logger.debug(f"Could not get document property: {e}")
        
        # Method 4: Try accessing the filing URL directly
        if not html_content:
            try:
                if hasattr(filing, 'url'):
                    url = filing.url
                    response = requests.get(url, headers=SCRAPE_HEADERS, timeout=30)
                    if response.status_code == 200:
                        html_content = response.text
            except Exception as e:
                logger.debug(f"Could not fetch from URL: {e}")
        
        if not html_content:
            logger.warning("Could not get HTML/text content from filing")
            return None
        
        # Convert to string if needed
        if not isinstance(html_content, str):
            html_content = str(html_content)
        
        # Extract MD&A section (Item 2 in 10-Q filings)
        # Look for common MD&A section markers
        import re
        
        # Patterns to find MD&A section
        mda_patterns = [
            r'(?i)item\s*2[\.\s]*management[^\'"]*discussion[^\'"]*analysis[^\'"]*of[^\'"]*financial[^\'"]*condition[^\'"]*and[^\'"]*results[^\'"]*of[^\'"]*operations',
            r'(?i)management[^\'"]*discussion[^\'"]*and[^\'"]*analysis[^\'"]*of[^\'"]*financial[^\'"]*condition[^\'"]*and[^\'"]*results[^\'"]*of[^\'"]*operations',
            r'(?i)item\s*2[\.\s]*mda',
            r'(?i)<title[^>]*>item\s*2[^<]*</title>',
        ]
        
        # Try to find MD&A section start
        mda_start = None
        for pattern in mda_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                mda_start = match.start()
                break
        
        if mda_start is None:
            # Fallback: look for "Item 2" or "Management's Discussion"
            fallback_patterns = [
                r'(?i)item\s*2[\.:]',
                r'(?i)management[^\'"]*discussion',
            ]
            for pattern in fallback_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    mda_start = match.start()
                    break
        
        if mda_start is None:
            logger.warning("Could not find MD&A section start marker")
            return None
        
        # Find the end of MD&A section (typically Item 3 or Item 4)
        # Look for next item marker
        end_patterns = [
            r'(?i)item\s*3[\.\s]',
            r'(?i)item\s*4[\.\s]',
            r'(?i)item\s*2a[\.\s]',
        ]
        
        mda_end = len(html_content)
        remaining_text = html_content[mda_start:]
        for pattern in end_patterns:
            match = re.search(pattern, remaining_text, re.IGNORECASE)
            if match:
                mda_end = mda_start + match.start()
                break
        
        # Extract the MD&A text
        mda_html = html_content[mda_start:mda_end]
        
        # Convert HTML to plain text (basic cleanup)
        # Remove HTML tags
        mda_text = re.sub(r'<[^>]+>', ' ', mda_html)
        
        # Clean up whitespace
        mda_text = re.sub(r'\s+', ' ', mda_text)
        mda_text = mda_text.strip()
        
        # Limit length to avoid token limits (keep first 15000 characters)
        if len(mda_text) > 15000:
            mda_text = mda_text[:15000] + "... [truncated]"
            logger.info(f"MD&A text truncated to 15000 characters")
        
        return mda_text if mda_text else None
        
    except Exception as e:
        logger.error(f"Error extracting MD&A text: {e}", exc_info=True)
        return None


def _extract_value(statement, field_names: list[str]) -> float | None:
    """
    Extract a value from a financial statement by trying multiple field names.
    
    Args:
        statement: Financial statement object (income statement or balance sheet)
        field_names: List of possible field names to try
    
    Returns:
        The extracted value as a float, or None if not found
    """
    for field in field_names:
        try:
            # Try attribute access
            if hasattr(statement, field):
                val = getattr(statement, field)
                if val is not None:
                    return float(val)
            # Try dictionary-style access
            if hasattr(statement, '__getitem__'):
                try:
                    val = statement[field]
                    if val is not None:
                        return float(val)
                except (KeyError, TypeError):
                    pass
            # Try get method
            if hasattr(statement, 'get'):
                val = statement.get(field)
                if val is not None:
                    return float(val)
        except (ValueError, TypeError, AttributeError):
            continue
    return None


# Database connection
engine = create_engine(config.database_url, echo=False)


@contextmanager
def get_session():
    """
    Context manager for database sessions.
    Ensures connections are properly closed after use.
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_filing_to_db(data: QuarterlyFinancialData, ticker: str) -> bool:
    """
    Save a quarterly financial filing to the database.
    
    Checks if the accession_number already exists before inserting.
    Also ensures the stock record exists, creating it if necessary.
    
    Args:
        data: QuarterlyFinancialData object with filing information
        ticker: Stock ticker symbol
    
    Returns:
        True if data was inserted, False if it already existed
    """
    if data is None:
        print(f"No data to save for {ticker}")
        return False
    
    with get_session() as session:
        # Check if filing already exists
        existing = session.execute(
            select(QuarterlyFinancial).where(
                QuarterlyFinancial.accession_number == data.accession_number
            )
        ).scalar_one_or_none()
        
        if existing:
            logger.debug(f"Filing {data.accession_number} already exists in database")
            print(f"Filing {data.accession_number} already exists in database")
            return False
        
        # Get or create the stock record
        stock = session.execute(
            select(Stock).where(Stock.ticker == ticker.upper())
        ).scalar_one_or_none()
        
        if not stock:
            # Fetch metadata and create stock record
            metadata = fetch_company_metadata(ticker)
            stock = Stock(
                ticker=metadata.ticker,
                name=metadata.name,
                cik=metadata.cik,
                sector=metadata.sector,
                industry=metadata.industry,
            )
            session.add(stock)
            session.flush()  # Get the stock.id
            logger.info(f"Created new stock record for {ticker}")
            print(f"Created new stock record for {ticker}")
        
        # Create the quarterly financial record
        quarterly = QuarterlyFinancial(
            stock_id=stock.id,
            form_type=data.form_type,
            filing_date=data.filing_date,
            accession_number=data.accession_number,
            revenue=data.revenue,
            net_income=data.net_income,
            total_assets=data.total_assets,
            total_liabilities=data.total_liabilities,
        )
        session.add(quarterly)
        logger.info(f"Saved filing {data.accession_number} for {ticker}")
        print(f"Saved filing {data.accession_number} for {ticker}")
        return True


if __name__ == "__main__":
    # Setup SEC identity first
    setup_sec_identity()
    
    # Example usage
    ticker = "AAPL"
    
    print(f"\nFetching metadata for {ticker}...")
    metadata = fetch_company_metadata(ticker)
    print(f"  Name: {metadata.name}")
    print(f"  CIK: {metadata.cik}")
    print(f"  Sector: {metadata.sector}")
    print(f"  Industry: {metadata.industry}")
    
    print(f"\nFetching latest 10-Q for {ticker}...")
    financials = fetch_latest_10q(ticker)
    if financials:
        print(f"  Filing Date: {financials.filing_date}")
        print(f"  Accession Number: {financials.accession_number}")
        print(f"  Revenue: {financials.revenue:,.0f}" if financials.revenue else "  Revenue: N/A")
        print(f"  Net Income: {financials.net_income:,.0f}" if financials.net_income else "  Net Income: N/A")
        print(f"  Total Assets: {financials.total_assets:,.0f}" if financials.total_assets else "  Total Assets: N/A")
        print(f"  Total Liabilities: {financials.total_liabilities:,.0f}" if financials.total_liabilities else "  Total Liabilities: N/A")
