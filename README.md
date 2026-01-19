# 📈 CANSLIM Stock Screener

A web-based stock screening application inspired by William O'Neil's CANSLIM methodology. Screen stocks for growth characteristics and analyze them with AI-powered insights.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Features

- **CANSLIM Screening**: Filter stocks based on:
  - **(C)** Current Earnings Growth > 20%
  - **(L)** Leader/Relative Strength > 1.0 (outperforming S&P 500)
  - **(T)** Trend: Price above 50-day SMA

- **Interactive Charts**: Candlestick charts with 50-day and 200-day SMAs using Plotly

- **AI Analyst**: Chat with GPT-4o about selected stocks, with context from CANSLIM metrics

- **SEC EDGAR Integration**: Fetch 10-Q filings using edgartools

## 🚀 Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/canslim-screener.git
   cd canslim-screener
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

4. **Run the web app**
   ```bash
   streamlit run app.py
   ```

5. **Open in browser**: Navigate to `http://localhost:8501`

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for AI analyst | Optional (can enter in UI) |
| `SEC_EMAIL` | Email for SEC EDGAR API compliance | For CLI tools only |

## 📁 Project Structure

```
canslim-screener/
├── app.py                 # Streamlit web application
├── main.py                # CLI version
├── database.py            # SQLAlchemy models
├── fetcher.py             # SEC EDGAR & yfinance data fetching
├── canslim_metrics.py     # CANSLIM calculations
├── screener_logic.py      # Screening logic
├── visualizer.py          # Plotly chart generation
├── ai_analyst.py          # OpenAI chat integration
├── requirements.txt       # Python dependencies
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
   ```

6. Click "Deploy"

## 🖥️ CLI Usage

For command-line usage:

```bash
# Set environment variables
export SEC_EMAIL="your-email@example.com"
export OPENAI_API_KEY="your-api-key"

# Run CLI version
python main.py
```

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

## 📄 License

MIT License - feel free to use and modify for your own projects.

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. It is not financial advice. Always do your own research before making investment decisions.
