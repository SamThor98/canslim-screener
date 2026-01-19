"""
API key validation utilities.
"""
import os
from logger_config import get_logger

logger = get_logger(__name__)


def validate_api_keys() -> None:
    """
    Check for required API keys and log warnings if missing.
    Does not raise exceptions - just logs warnings.
    """
    missing_keys = []
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        missing_keys.append("OPENAI_API_KEY")
        logger.warning("Configuration Missing: OPENAI_API_KEY not set. AI analyst features will be unavailable.")
    
    # Check SEC API credentials
    if not os.getenv("SEC_EMAIL") and not os.getenv("SEC_API_USER_AGENT"):
        missing_keys.append("SEC_EMAIL or SEC_API_USER_AGENT")
        logger.warning("Configuration Missing: SEC_EMAIL or SEC_API_USER_AGENT not set. SEC EDGAR features may be unavailable.")
    
    if missing_keys:
        logger.warning(f"Missing API keys: {', '.join(missing_keys)}. Some features may be unavailable.")
    else:
        logger.info("All API keys configured")
