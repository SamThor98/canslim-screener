import os
import yfinance as yf
from openai import OpenAI
from config import config
from logger_config import get_logger

logger = get_logger(__name__)


def start_stock_chat(ticker: str, financial_summary: dict) -> None:
    """
    Start an interactive chat session with an AI stock analyst.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        financial_summary: Dictionary of CANSLIM metrics for the stock
    """
    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Set it with: $env:OPENAI_API_KEY = 'your-api-key'")
        return
    
    client = OpenAI(api_key=api_key)
    
    # Build system prompt
    system_prompt = f"""You are a veteran growth stock trader. I will provide financial metrics for {ticker}. Answer questions briefly, focusing on risk and technical strength.

Current CANSLIM Metrics for {ticker}:
{_format_metrics(financial_summary)}

Use these metrics to inform your analysis. Be concise and actionable."""

    # Initialize conversation history
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    print("=" * 60)
    print(f"AI Stock Analyst - Analyzing {ticker}")
    print("=" * 60)
    print(f"Loaded metrics: {list(financial_summary.keys())}")
    print("Type your questions about this stock. Type 'exit' to quit.")
    print("=" * 60)
    
    # Chat loop
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "exit":
                print("\nEnding analysis session. Goodbye!")
                break
            
            # Add user message to history
            messages.append({"role": "user", "content": user_input})
            
            # Send to OpenAI
            response = client.chat.completions.create(
                model=config.openai_model,
                messages=messages,
                temperature=config.openai_temperature,
                max_tokens=config.openai_max_tokens,
            )
            
            # Extract and display response
            assistant_message = response.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_message})
            
            print(f"\nAnalyst: {assistant_message}")
            
        except KeyboardInterrupt:
            logger.info("Chat session interrupted by user")
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in chat session: {e}", exc_info=True)
            print(f"\nError: {e}")
            continue


def analyze_company_story(ticker: str, ticker_metadata: dict, news_headlines: list[str] = None) -> tuple[bool, str]:
    """
    Early AI qualitative filtering for CANSLIM "N" (New) and "S" (Supply/Demand) criteria.
    
    Analyzes if the company has:
    - New Product/Management (The "N" in CANSLIM)
    - Belongs to a Leading Industry (The "S" in CANSLIM - supply/demand dynamics)
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        ticker_metadata: Dictionary with company metadata (name, sector, industry)
        news_headlines: Optional list of recent news headlines (will fetch if not provided)
    
    Returns:
        Tuple of (passes_check, analysis_summary)
        passes_check: True if company shows signs of new products/management or leading industry
        analysis_summary: Brief explanation of the AI's assessment
    """
    if not config.is_openai_configured():
        logger.warning("OpenAI not configured, skipping AI company story analysis")
        return True, "AI analysis unavailable - defaulting to pass"
    
    try:
        # Fetch news if not provided
        if news_headlines is None:
            try:
                stock = yf.Ticker(ticker)
                news = stock.news
                if news and len(news) > 0:
                    # Get top 5 most recent headlines
                    news_headlines = [item.get('title', '') for item in news[:5] if item.get('title')]
                else:
                    news_headlines = []
            except Exception as e:
                logger.debug(f"Could not fetch news for {ticker}: {e}")
                news_headlines = []
        
        # Build context for AI
        company_name = ticker_metadata.get('name', ticker)
        sector = ticker_metadata.get('sector', 'Unknown')
        industry = ticker_metadata.get('industry', 'Unknown')
        
        news_context = "\n".join([f"- {headline}" for headline in news_headlines[:5]]) if news_headlines else "No recent news available."
        
        # Create AI prompt
        system_prompt = """You are a CANSLIM growth stock analyst. Analyze if a company meets the "N" (New) and "S" (Supply/Demand) criteria:

"N" (New): Company has new products, services, management, or significant positive changes.
"S" (Supply/Demand): Company operates in a leading, high-demand industry with favorable supply/demand dynamics.

Respond with ONLY a JSON object in this exact format:
{
    "passes": true/false,
    "reason": "Brief explanation (1-2 sentences)"
}

Be strict: Only pass if there's clear evidence of new products/management OR if the industry is clearly leading/high-growth."""
        
        user_prompt = f"""Analyze this company for CANSLIM "N" and "S" criteria:

Company: {company_name} ({ticker})
Sector: {sector}
Industry: {industry}

Recent News Headlines:
{news_context}

Does this company show signs of:
1. New products, services, or management changes? (The "N")
2. Operating in a leading, high-growth industry? (The "S")

Respond with JSON only."""
        
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent analysis
            max_tokens=200,
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON from response (handle cases where AI adds extra text)
        json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            passes = result.get('passes', False)
            reason = result.get('reason', 'No reason provided')
        else:
            # Fallback: try to parse the whole response
            try:
                result = json.loads(response_text)
                passes = result.get('passes', False)
                reason = result.get('reason', 'No reason provided')
            except:
                # If parsing fails, default to pass but log warning
                logger.warning(f"Could not parse AI response for {ticker}: {response_text}")
                passes = True
                reason = "AI analysis parsing failed - defaulting to pass"
        
        logger.info(f"AI company story analysis for {ticker}: {'PASS' if passes else 'FAIL'} - {reason}")
        return passes, reason
        
    except Exception as e:
        logger.error(f"Error in AI company story analysis for {ticker}: {e}", exc_info=True)
        # Default to pass on error to avoid blocking stocks
        return True, f"AI analysis error - defaulting to pass: {str(e)}"


def _format_metrics(metrics: dict) -> str:
    """Format metrics dictionary for the system prompt."""
    if not metrics:
        return "No metrics available."
    
    lines = []
    for key, value in metrics.items():
        if isinstance(value, float):
            if "%" in key or "Growth" in key:
                lines.append(f"- {key}: {value:.1f}%")
            else:
                lines.append(f"- {key}: {value:.2f}")
        else:
            lines.append(f"- {key}: {value}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage with sample metrics
    sample_metrics = {
        "Earnings Growth (%)": 25.3,
        "Relative Strength": 1.15,
        "Current Price": 185.50,
        "50-Day SMA": 178.20,
        "200-Day SMA": 165.40,
        "Price vs SMA (%)": 4.1,
        "Sector": "Technology",
        "Industry": "Consumer Electronics",
    }
    
    ticker = "AAPL"
    start_stock_chat(ticker, sample_metrics)
