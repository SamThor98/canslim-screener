import os
from contextlib import contextmanager

import yfinance as yf
from edgar import Company, set_identity
from dataclasses import dataclass
from datetime import date
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import Base, Stock, QuarterlyFinancial


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


def setup_sec_identity() -> None:
    """
    Set up SEC identity for EDGAR API access.
    The SEC requires a user-agent with contact information.
    """
    email = os.environ.get("SEC_EMAIL")
    if not email:
        print("=" * 60)
        print("SEC EDGAR API requires identification.")
        print("Please set your email for SEC compliance.")
        print("=" * 60)
        email = input("Enter your email address: ").strip()
        if not email:
            raise ValueError("Email is required for SEC EDGAR API access.")
    
    set_identity(email)
    print(f"SEC identity set: {email}")


def fetch_company_metadata(ticker: str) -> CompanyMetadata:
    """
    Fetch company metadata using yfinance.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        CompanyMetadata with ticker, name, CIK, sector, and industry
    """
    stock = yf.Ticker(ticker)
    info = stock.info
    
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
            print(f"Warning: Could not extract all financials: {e}")
        
        return QuarterlyFinancialData(
            form_type="10-Q",
            filing_date=latest_10q.filing_date,
            accession_number=latest_10q.accession_number,
            revenue=revenue,
            net_income=net_income,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
        )
        
    except Exception as e:
        print(f"Error fetching 10-Q for {ticker}: {e}")
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
DATABASE_URL = "sqlite:///investor.db"
engine = create_engine(DATABASE_URL, echo=False)


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
