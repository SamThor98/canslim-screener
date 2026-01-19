import os
from openai import OpenAI


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
            
            # Send to GPT-4o
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            
            # Extract and display response
            assistant_message = response.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_message})
            
            print(f"\nAnalyst: {assistant_message}")
            
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue


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
