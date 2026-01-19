"""
Configuration management using python-dotenv.
Loads environment variables from .env file in the root directory.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from root directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


class Config:
    """Application configuration loaded from environment variables."""
    
    # ==========================================================================
    # API Keys & External Services
    # ==========================================================================
    
    # OpenAI API Key for AI analyst feature
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    
    # SEC API User Agent (required for EDGAR API compliance)
    # Format: "Name email@example.com"
    SEC_API_USER_AGENT: str | None = os.getenv("SEC_API_USER_AGENT")
    
    # Benchmark ticker for relative strength calculation
    BENCHMARK_TICKER: str = os.getenv("BENCHMARK_TICKER", "SPY")
    
    # ==========================================================================
    # CANSLIM Screening Thresholds
    # ==========================================================================
    
    # Minimum earnings growth (as decimal, 0.20 = 20%)
    EARNINGS_GROWTH_THRESHOLD: float = float(os.getenv("EARNINGS_GROWTH_THRESHOLD", "0.20"))
    
    # Minimum relative strength (1.0 = matching benchmark)
    RELATIVE_STRENGTH_THRESHOLD: float = float(os.getenv("RELATIVE_STRENGTH_THRESHOLD", "1.0"))
    
    # SMA periods
    SMA_PERIOD: int = int(os.getenv("SMA_PERIOD", "50"))
    SMA_200_PERIOD: int = int(os.getenv("SMA_200_PERIOD", "200"))
    
    # ==========================================================================
    # OpenAI Settings
    # ==========================================================================
    
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "500"))
    
    # ==========================================================================
    # Application Settings
    # ==========================================================================
    
    # Cache TTL in seconds (1 hour default)
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
    
    # Rate limit delay between API calls (seconds)
    RATE_LIMIT_DELAY: float = float(os.getenv("RATE_LIMIT_DELAY", "0.3"))
    
    # History period for charts
    HISTORY_PERIOD: str = os.getenv("HISTORY_PERIOD", "1y")
    
    # Default screening limit for large index/sector scans
    DEFAULT_SCREEN_LIMIT: int = int(os.getenv("DEFAULT_SCREEN_LIMIT", "50"))
    
    # ==========================================================================
    # Index URLs (Wikipedia sources for scraping)
    # ==========================================================================
    
    INDEX_URLS: dict = {
        "S&P 500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "Nasdaq 100": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "Dow Jones": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
        "Russell 2000": "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",  # Fallback - actual Russell 2000 requires subscription
    }
    
    # ==========================================================================
    # Sector Definitions (GICS Sectors)
    # ==========================================================================
    
    SECTORS: list = [
        "Technology",
        "Healthcare", 
        "Financials",
        "Consumer Cyclical",
        "Consumer Defensive",
        "Industrials",
        "Energy",
        "Utilities",
        "Real Estate",
        "Basic Materials",
        "Communication Services",
    ]
    
    # ==========================================================================
    # Property accessors (for backward compatibility with lowercase)
    # ==========================================================================
    
    @property
    def openai_api_key(self) -> str | None:
        return self.OPENAI_API_KEY
    
    @property
    def sec_api_user_agent(self) -> str | None:
        return self.SEC_API_USER_AGENT
    
    @property
    def benchmark_ticker(self) -> str:
        return self.BENCHMARK_TICKER
    
    @property
    def earnings_growth_threshold(self) -> float:
        return self.EARNINGS_GROWTH_THRESHOLD
    
    @property
    def relative_strength_threshold(self) -> float:
        return self.RELATIVE_STRENGTH_THRESHOLD
    
    @property
    def sma_period(self) -> int:
        return self.SMA_PERIOD
    
    @property
    def sma_200_period(self) -> int:
        return self.SMA_200_PERIOD
    
    @property
    def openai_model(self) -> str:
        return self.OPENAI_MODEL
    
    @property
    def openai_temperature(self) -> float:
        return self.OPENAI_TEMPERATURE
    
    @property
    def openai_max_tokens(self) -> int:
        return self.OPENAI_MAX_TOKENS
    
    @property
    def cache_ttl(self) -> int:
        return self.CACHE_TTL
    
    @property
    def rate_limit_delay(self) -> float:
        return self.RATE_LIMIT_DELAY
    
    @property
    def history_period(self) -> str:
        return self.HISTORY_PERIOD
    
    @property
    def default_screen_limit(self) -> int:
        return self.DEFAULT_SCREEN_LIMIT
    
    @property
    def index_urls(self) -> dict:
        return self.INDEX_URLS
    
    @property
    def sectors(self) -> list:
        return self.SECTORS
    
    # ==========================================================================
    # Validation Methods
    # ==========================================================================
    
    @classmethod
    def is_openai_configured(cls) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(cls.OPENAI_API_KEY and cls.OPENAI_API_KEY.strip() 
                    and not cls.OPENAI_API_KEY.startswith("sk-your"))
    
    @classmethod
    def is_sec_configured(cls) -> bool:
        """Check if SEC API user agent is configured."""
        return bool(cls.SEC_API_USER_AGENT and cls.SEC_API_USER_AGENT.strip()
                    and "@" in cls.SEC_API_USER_AGENT)
    
    @classmethod
    def validate(cls) -> dict[str, bool]:
        """Validate all configuration settings."""
        return {
            "openai": cls.is_openai_configured(),
            "sec": cls.is_sec_configured(),
        }
    
    @classmethod
    def get_missing_keys(cls) -> list[str]:
        """Get list of missing required configuration keys."""
        missing = []
        if not cls.is_openai_configured():
            missing.append("OPENAI_API_KEY")
        if not cls.is_sec_configured():
            missing.append("SEC_API_USER_AGENT")
        return missing


# Singleton config instance
config = Config()
