import yfinance as yf
import plotly.graph_objects as go


def show_interactive_chart(ticker: str) -> None:
    """
    Display an interactive candlestick chart with SMA overlays.
    
    Downloads 1 year of OHLC data and displays:
    - Candlestick chart for price action
    - 50-day SMA (blue line)
    - 200-day SMA (red line)
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
    """
    # Download 1 year of OHLC data
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")
    
    if df.empty:
        print(f"No data available for {ticker}")
        return
    
    # Calculate SMAs
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    df["SMA_200"] = df["Close"].rolling(window=200).mean()
    
    # Create figure
    fig = go.Figure()
    
    # Add Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_line_color="#00d4aa",  # Teal green for up
            decreasing_line_color="#ff6b6b",  # Coral red for down
            increasing_fillcolor="#00d4aa",
            decreasing_fillcolor="#ff6b6b",
        )
    )
    
    # Add 50-day SMA (Blue)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA_50"],
            mode="lines",
            name="50-Day SMA",
            line=dict(color="#3b9dff", width=2),
        )
    )
    
    # Add 200-day SMA (Red)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA_200"],
            mode="lines",
            name="200-Day SMA",
            line=dict(color="#ff4757", width=2),
        )
    )
    
    # Update layout for dark mode
    fig.update_layout(
        title=dict(
            text=f"{ticker} - 1 Year Chart with SMAs",
            font=dict(size=24, color="#ffffff"),
            x=0.5,
            xanchor="center",
        ),
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9"),
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=False),
            gridcolor="#30363d",
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            title="Price ($)",
            gridcolor="#30363d",
            showgrid=True,
            zeroline=False,
            side="right",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(22, 27, 34, 0.8)",
            bordercolor="#30363d",
            borderwidth=1,
        ),
        hovermode="x unified",
        margin=dict(l=50, r=50, t=100, b=50),
    )
    
    # Add range selector buttons
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(label="All", step="all"),
            ]),
            bgcolor="#21262d",
            activecolor="#388bfd",
            bordercolor="#30363d",
            font=dict(color="#c9d1d9"),
        )
    )
    
    # Show the chart in default browser
    print(f"Opening interactive chart for {ticker}...")
    fig.show()


if __name__ == "__main__":
    # Example usage
    ticker = "AAPL"
    show_interactive_chart(ticker)
