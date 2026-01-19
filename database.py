from sqlalchemy import create_engine, String, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


def initialize_db() -> None:
    """Create all tables in the investor.db SQLite database."""
    engine = create_engine("sqlite:///investor.db", echo=False)
    Base.metadata.create_all(engine)
    print("Database initialized: investor.db")


if __name__ == "__main__":
    initialize_db()
