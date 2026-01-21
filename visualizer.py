import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def show_interactive_chart(ticker: str, timeframe: str = "daily") -> None:
    """
    Display an interactive candlestick chart with SMA overlays and volume bars.
    
    Supports both Daily and Weekly timeframes with appropriate moving averages:
    - Daily: 50-day, 150-day, 200-day SMAs
    - Weekly: 10-week, 40-week SMAs (equivalent to 50-day and 200-day)
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        timeframe: Either "daily" or "weekly" (default: "daily")
    """
    # Download data based on timeframe
    stock = yf.Ticker(ticker)
    
    if timeframe.lower() == "weekly":
        # For weekly, fetch 2 years to get enough data points
        df = stock.history(period="2y", interval="1wk")
        sma_periods = {
            "sma_10w": 10,  # 10-week SMA (equivalent to 50-day)
            "sma_40w": 40,  # 40-week SMA (equivalent to 200-day)
        }
        title_suffix = "Weekly Base View"
    else:
        # Daily timeframe
        df = stock.history(period="1y", interval="1d")
        sma_periods = {
            "sma_50": 50,
            "sma_150": 150,
            "sma_200": 200,
        }
        title_suffix = "Daily View"
    
    if df.empty:
        print(f"No data available for {ticker}")
        return
    
    # Calculate SMAs based on timeframe
    if timeframe.lower() == "weekly":
        df["SMA_10w"] = df["Close"].rolling(window=sma_periods["sma_10w"]).mean()
        df["SMA_40w"] = df["Close"].rolling(window=sma_periods["sma_40w"]).mean()
    else:
        df["SMA_50"] = df["Close"].rolling(window=sma_periods["sma_50"]).mean()
        df["SMA_150"] = df["Close"].rolling(window=sma_periods["sma_150"]).mean()
        df["SMA_200"] = df["Close"].rolling(window=sma_periods["sma_200"]).mean()
    
    # Create subplots: price chart on top, volume on bottom
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{ticker} Price Action", "Volume")
    )
    
    # Add Candlestick chart (row 1)
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
        ),
        row=1, col=1
    )
    
    # Add SMAs based on timeframe (row 1)
    if timeframe.lower() == "weekly":
        # 10-week SMA (Blue) - equivalent to 50-day
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_10w"],
                mode="lines",
                name="10-Week SMA",
                line=dict(color="#3b9dff", width=2),
            ),
            row=1, col=1
        )
        
        # 40-week SMA (Red) - equivalent to 200-day
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_40w"],
                mode="lines",
                name="40-Week SMA",
                line=dict(color="#ff4757", width=2),
            ),
            row=1, col=1
        )
    else:
        # Daily SMAs
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_50"],
                mode="lines",
                name="50-Day SMA",
                line=dict(color="#3b9dff", width=2),
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_150"],
                mode="lines",
                name="150-Day SMA",
                line=dict(color="#ffa726", width=2),
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_200"],
                mode="lines",
                name="200-Day SMA",
                line=dict(color="#ff4757", width=2),
            ),
            row=1, col=1
        )
    
    # Add Volume bars with color coding (row 2)
    # Green for accumulation (close > open), Red for distribution (close < open)
    if "Volume" in df.columns:
        # Determine if each bar is accumulation or distribution
        volume_colors = []
        for i in range(len(df)):
            if df["Close"].iloc[i] > df["Open"].iloc[i]:
                volume_colors.append("#00d4aa")  # Green for accumulation
            else:
                volume_colors.append("#ff6b6b")  # Red for distribution
        
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volume",
                marker_color=volume_colors,
                showlegend=False,
            ),
            row=2, col=1
        )
    
    # Update layout for dark mode
    fig.update_layout(
        title=dict(
            text=f"{ticker} - {title_suffix}",
            font=dict(size=24, color="#ffffff"),
            x=0.5,
            xanchor="center",
        ),
        template="plotly_dark",
        paper_bgcolor="#0f0f23",  # Dark theme background from config
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9"),
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
    
    # Update x-axis (shared between subplots)
    fig.update_xaxes(
        title="Date",
        rangeslider=dict(visible=False),
        gridcolor="#30363d",
        showgrid=True,
        zeroline=False,
        row=2, col=1  # Only show on bottom subplot
    )
    
    # Update y-axes
    fig.update_yaxes(
        title="Price ($)",
        gridcolor="#30363d",
        showgrid=True,
        zeroline=False,
        side="right",
        row=1, col=1
    )
    
    fig.update_yaxes(
        title="Volume",
        gridcolor="#30363d",
        showgrid=True,
        zeroline=False,
        row=2, col=1
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
