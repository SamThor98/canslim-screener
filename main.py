import os
from fetcher import setup_sec_identity, fetch_latest_10q
from screener_logic import run_canslim_screen
from visualizer import show_interactive_chart
from ai_analyst import start_stock_chat
from database import initialize_db
from logger_config import setup_logging, get_logger
from api_validation import validate_api_keys

# Setup logging
setup_logging()
logger = get_logger(__name__)


def main():
    """Main entry point for the CANSLIM stock screening application."""
    
    print("=" * 60)
    print("  CANSLIM STOCK SCREENER & ANALYZER")
    print("=" * 60)
    
    # Validate API keys
    validate_api_keys()
    
    # Initialize database
    initialize_db()
    
    # Setup SEC identity for EDGAR API access
    setup_sec_identity()
    
    # Define high-growth tickers to screen
    tickers = ["NVDA", "PLTR", "AMD", "TSLA", "CELH"]
    
    print(f"\nScreening {len(tickers)} stocks: {', '.join(tickers)}")
    print()
    
    # Run CANSLIM screen
    results_df = run_canslim_screen(tickers)
    
    # Print results
    print("\n" + "=" * 60)
    print("SCREENING RESULTS")
    print("=" * 60)
    
    if results_df.empty:
        print("\nNo stocks passed all CANSLIM criteria.")
        print("Try adjusting the criteria or screening different stocks.")
        return
    
    print(f"\n{len(results_df)} stock(s) passed all criteria:\n")
    print(results_df.to_string(index=False))
    
    # Get list of passing tickers
    passing_tickers = results_df["Ticker"].tolist()
    
    # Interactive analysis loop
    while True:
        print("\n" + "-" * 60)
        print(f"Passing stocks: {', '.join(passing_tickers)}")
        user_choice = input("\nWhich stock do you want to analyze? (or 'quit' to exit): ").strip().upper()
        
        if user_choice.lower() == "quit" or user_choice.lower() == "exit":
            print("\nGoodbye!")
            break
        
        if user_choice not in passing_tickers:
            print(f"'{user_choice}' is not in the list of passing stocks.")
            print(f"Please choose from: {', '.join(passing_tickers)}")
            continue
        
        print(f"\n>>> Analyzing {user_choice}...")
        
        # 1. Show interactive chart
        print(f"\n[1/3] Opening interactive chart for {user_choice}...")
        show_interactive_chart(user_choice)
        
        # 2. Fetch latest 10-Q
        print(f"\n[2/3] Fetching latest 10-Q filing for {user_choice}...")
        filing_data = fetch_latest_10q(user_choice)
        
        # 3. Prepare metrics for AI analyst
        # Get the row from results_df for this ticker
        stock_row = results_df[results_df["Ticker"] == user_choice].iloc[0]
        
        # Build comprehensive financial summary
        financial_summary = {
            "Company": stock_row.get("Company", user_choice),
            "Sector": stock_row.get("Sector", "N/A"),
            "Industry": stock_row.get("Industry", "N/A"),
            "Earnings Growth (%)": stock_row.get("Earnings Growth (%)", None),
            "Relative Strength": stock_row.get("Relative Strength", None),
            "Current Price": stock_row.get("Current Price", None),
            "50-Day SMA": stock_row.get("50-Day SMA", None),
            "Price vs SMA (%)": stock_row.get("Price vs SMA (%)", None),
        }
        
        # Add 10-Q data if available
        if filing_data:
            financial_summary["10-Q Filing Date"] = str(filing_data.filing_date)
            financial_summary["10-Q Accession Number"] = filing_data.accession_number
            if filing_data.revenue:
                financial_summary["Revenue (Latest Q)"] = f"${filing_data.revenue:,.0f}"
            if filing_data.net_income:
                financial_summary["Net Income (Latest Q)"] = f"${filing_data.net_income:,.0f}"
            if filing_data.total_assets:
                financial_summary["Total Assets"] = f"${filing_data.total_assets:,.0f}"
            if filing_data.total_liabilities:
                financial_summary["Total Liabilities"] = f"${filing_data.total_liabilities:,.0f}"
        
        # 3. Start AI chat
        print(f"\n[3/3] Starting AI analyst session for {user_choice}...")
        
        # Check if OpenAI API key is set
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not set, skipping AI analyst")
            print("\nWarning: OPENAI_API_KEY not set.")
            print("Set it with: $env:OPENAI_API_KEY = 'your-api-key'")
            print("\nSkipping AI analyst. Displaying metrics instead:")
            print("-" * 40)
            for key, value in financial_summary.items():
                print(f"  {key}: {value}")
            print("-" * 40)
        else:
            start_stock_chat(user_choice, financial_summary)
        
        # Ask if user wants to analyze another stock
        continue_choice = input("\nAnalyze another stock? (y/n): ").strip().lower()
        if continue_choice != "y" and continue_choice != "yes":
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
