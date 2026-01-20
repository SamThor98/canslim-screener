# 🦬 Logan Screener

**Built to endure. Positioned to prosper.**

A strategic growth stock screening application inspired by William O'Neil's CANSLIM methodology, featuring the elegant aesthetic of Old Logan Capital.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Features

- **CANSLIM Screening**: Filter stocks based on:
  - **(C)** Current Earnings Growth > 20%
  - **(L)** Leader/Relative Strength > 1.0 (outperforming S&P 500)
  - **(T)** Trend: Price above 50-day SMA

- **Multi-Mode Selection**:
  - **Index Scan**: Screen S&P 500, Nasdaq 100, Dow Jones, Russell 2000
  - **Sector Scan**: Filter by Technology, Healthcare, Energy, and more
  - **Manual Entry**: Enter specific tickers

- **Interactive Charts**: Candlestick charts with 50-day and 200-day SMAs using Plotly

- **AI Analyst**: Chat with an AI analyst about selected stocks, with context from CANSLIM metrics

- **SEC EDGAR Integration**: Fetch 10-Q filings using edgartools

## 🚀 Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/SamThor98/logan-screener.git
   cd logan-screener
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\Activate.ps1
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment** (create `.env` file)
   ```env
   OPENAI_API_KEY=sk-your-key-here
   SEC_API_USER_AGENT=YourName email@example.com
   BENCHMARK_TICKER=SPY
   ```

5. **Run the web app**
   ```bash
   streamlit run app.py
   ```

6. **Open in browser**: Navigate to `http://localhost:8501`

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for AI analyst | Yes (for AI features) |
| `SEC_API_USER_AGENT` | User agent for SEC EDGAR API | Yes (for 10-Q fetching) |
| `BENCHMARK_TICKER` | Benchmark for relative strength | No (defaults to SPY) |

## 📁 Project Structure

```
logan-screener/
├── app.py                 # Streamlit web application
├── main.py                # CLI version
├── config.py              # Configuration management
├── database.py            # SQLAlchemy models
├── fetcher.py             # SEC EDGAR & yfinance data fetching
├── canslim_metrics.py     # CANSLIM calculations
├── screener_logic.py      # Screening logic
├── visualizer.py          # Plotly chart generation
├── ai_analyst.py          # OpenAI chat integration
├── utils.py               # Utility functions
├── logger_config.py       # Logging configuration
├── api_validation.py      # API key validation
├── logo.png               # Old Logan Capital bison logo
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
└── README.md
```

## 🌐 Deploy to Streamlit Cloud

1. Push this repository to GitHub

2. Go to [share.streamlit.io](https://share.streamlit.io)

3. Click "New app" and connect your GitHub repository

4. Set the main file path to `app.py`

5. Add secrets in Streamlit Cloud dashboard:
   ```toml
   OPENAI_API_KEY = "your-api-key-here"
   SEC_API_USER_AGENT = "YourName email@example.com"
   ```

6. Click "Deploy"

## 🎨 Design

Logan Screener features a distinctive aesthetic inspired by Old Logan Capital:

- **Color Palette**: Cream (#F5F1E8), Forest Green (#1A3A2E), Gold (#C9A962)
- **Typography**: Fraunces (serif headings), DM Sans (body), IBM Plex Mono (data)
- **Logo**: The iconic bison symbolizing resilience and strategic vision

## 📊 CANSLIM Methodology

CANSLIM is an acronym for seven characteristics of winning stocks:

| Letter | Meaning | This App |
|--------|---------|----------|
| **C** | Current quarterly earnings | ✅ YoY growth > 20% |
| **A** | Annual earnings growth | - |
| **N** | New products/management | - |
| **S** | Supply and demand | - |
| **L** | Leader or laggard | ✅ RS > 1.0 vs S&P 500 |
| **I** | Institutional sponsorship | - |
| **M** | Market direction | ✅ Price > 50-day SMA |

## 🛠️ Technologies

- **Frontend**: Streamlit
- **Charts**: Plotly
- **Data**: yfinance, edgartools
- **Database**: SQLAlchemy + SQLite
- **AI**: OpenAI GPT-4o
- **Styling**: Custom CSS with Old Logan Capital theme

## 📄 License

MIT License - feel free to use and modify for your own projects.

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. It is not financial advice. Always do your own research before making investment decisions.

---

*© 2025 Logan Screener · Built with strategic vision*
