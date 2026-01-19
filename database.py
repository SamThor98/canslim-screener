from sqlalchemy import create_engine, String, Integer, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from config import config
from logger_config import get_logger
import json

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cik: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationship to QuarterlyFinancials
    quarterly_financials: Mapped[list["QuarterlyFinancial"]] = relationship(
        back_populates="stock", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Stock(ticker={self.ticker}, name={self.name})>"


class QuarterlyFinancial(Base):
    __tablename__ = "quarterly_financials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    form_type: Mapped[str] = mapped_column(String(10), nullable=False)
    filing_date: Mapped[Date] = mapped_column(Date, nullable=False)
    accession_number: Mapped[str] = mapped_column(String(25), unique=True, nullable=False)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationship to Stock
    stock: Mapped["Stock"] = relationship(back_populates="quarterly_financials")

    def __repr__(self) -> str:
        return f"<QuarterlyFinancial(stock_id={self.stock_id}, filing_date={self.filing_date})>"


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    earnings_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_above_sma: Mapped[bool | None] = mapped_column(Integer, nullable=True)  # SQLite doesn't have native bool
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    
    # Index on ticker and cached_at for faster lookups
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

    def __repr__(self) -> str:
        return f"<ScreeningResult(ticker={self.ticker}, cached_at={self.cached_at})>"


def initialize_db() -> None:
    """Create all tables in the database."""
    engine = create_engine(config.database_url, echo=False)
    Base.metadata.create_all(engine)
    logger.info(f"Database initialized: {config.database_url}")
    print(f"Database initialized: {config.database_url}")


def get_cached_screen(ticker: str, max_age_hours: int = 24) -> dict | None:
    """
    Retrieve cached screening result for a ticker if it exists and is not stale.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        max_age_hours: Maximum age of cache in hours (default: 24)
    
    Returns:
        Dictionary with cached screening data, or None if no valid cache exists
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    
    engine = create_engine(config.database_url, echo=False)
    
    try:
        with Session(engine) as session:
            # Find the most recent cache entry for this ticker
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            result = session.execute(
                select(ScreeningResult)
                .where(ScreeningResult.ticker == ticker.upper())
                .where(ScreeningResult.cached_at >= cutoff_time)
                .order_by(ScreeningResult.cached_at.desc())
            ).scalar_one_or_none()
            
            if result:
                logger.info(f"Cache HIT for {ticker} (cached at {result.cached_at})")
                return {
                    "earnings_growth": result.earnings_growth,
                    "relative_strength": result.relative_strength,
                    "current_price": result.current_price,
                    "sma_50": result.sma_50,
                    "is_above_sma": bool(result.is_above_sma) if result.is_above_sma is not None else None,
                    "company_name": result.company_name,
                    "sector": result.sector,
                    "industry": result.industry,
                }
            else:
                logger.info(f"Cache MISS for {ticker} (no valid cache found)")
                return None
                
    except Exception as e:
        logger.error(f"Error retrieving cached screen for {ticker}: {e}", exc_info=True)
        return None


def save_screen_result(ticker: str, data: dict) -> bool:
    """
    Save screening result to the database cache.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        data: Dictionary containing screening metrics:
            - earnings_growth: float | None
            - relative_strength: float | None
            - current_price: float | None
            - sma_50: float | None
            - is_above_sma: bool | None
            - company_name: str | None
            - sector: str | None
            - industry: str | None
    
    Returns:
        True if saved successfully, False otherwise
    """
    from sqlalchemy.orm import Session
    
    engine = create_engine(config.database_url, echo=False)
    
    try:
        with Session(engine) as session:
            # Create new cache entry
            result = ScreeningResult(
                ticker=ticker.upper(),
                earnings_growth=data.get("earnings_growth"),
                relative_strength=data.get("relative_strength"),
                current_price=data.get("current_price"),
                sma_50=data.get("sma_50"),
                is_above_sma=1 if data.get("is_above_sma") else 0 if data.get("is_above_sma") is False else None,
                company_name=data.get("company_name"),
                sector=data.get("sector"),
                industry=data.get("industry"),
                cached_at=datetime.now(),
            )
            
            session.add(result)
            session.commit()
            logger.info(f"Cached screening result for {ticker}")
            return True
            
    except Exception as e:
        logger.error(f"Error saving cached screen for {ticker}: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    initialize_db()
