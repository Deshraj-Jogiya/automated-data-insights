# Daily Market Insights & Anomaly Detection Automation Pipeline
import os
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

# Output directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE_DIR, "insights", "charts")
REPORTS_DIR = os.path.join(BASE_DIR, "insights", "reports")

def ensure_directories():
    os.makedirs(CHARTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

def fetch_index_data(ticker, period="60d"):
    """Fetch history using yfinance with fallback."""
    print(f"Fetching data for {ticker} (period: {period})...")
    try:
        data = yf.Ticker(ticker)
        df = data.history(period=period)
        if df.empty:
            raise ValueError(f"Empty dataframe returned for {ticker}")
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        # Return empty df or generate synthetic fallback data to prevent pipeline crash
        return pd.DataFrame()

def detect_anomalies(df):
    """Calculate returns and detect volatility/price anomalies (> 2 std dev)."""
    if df.empty or len(df) < 20:
        return df, []
        
    df['Daily_Return'] = df['Close'].pct_change()
    df['Return_MA_20'] = df['Daily_Return'].rolling(window=20).mean()
    df['Return_Std_20'] = df['Daily_Return'].rolling(window=20).std()
    
    # 20-day Close Moving Average
    df['Close_MA_20'] = df['Close'].rolling(window=20).mean()
    
    # Detect outliers where daily return exceeds 2 standard deviations from rolling mean
    df['Anomaly'] = 0
    anomalies = []
    
    # Start looking from index 20 onwards (where MA is defined)
    for i in range(20, len(df)):
        ret = df['Daily_Return'].iloc[i]
        ma = df['Return_MA_20'].iloc[i]
        std = df['Return_Std_20'].iloc[i]
        
        # Avoid division by zero
        if std > 0 and abs(ret - ma) > 2.0 * std:
            df.loc[df.index[i], 'Anomaly'] = 1
            anomalies.append({
                "date": df.index[i].strftime("%Y-%m-%d"),
                "close": round(float(df['Close'].iloc[i]), 2),
                "return": round(float(ret * 100), 2),
                "z_score": round(float(abs(ret - ma) / std), 2)
            })
            
    return df, anomalies

def generate_visualization(df, ticker_name, date_str):
    """Plot price chart with 20-day SMA and highlight anomalies using dark mode theme."""
    if df.empty:
        return None
        
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6), facecolor='#0b0f19')
    ax.set_facecolor('#0d1321')
    
    # Plot closing price
    ax.plot(df.index, df['Close'], label='Close Price', color='#a855f7', linewidth=2)
    
    # Plot 20-day SMA
    if 'Close_MA_20' in df.columns:
        ax.plot(df.index, df['Close_MA_20'], label='20-day SMA', color='#6366f1', linestyle='--', linewidth=1.5)
        
    # Highlight anomalies
    anomalies_df = df[df['Anomaly'] == 1]
    if not anomalies_df.empty:
        ax.scatter(anomalies_df.index, anomalies_df['Close'], color='#f43f5e', s=80, label='Anomaly Detected', zorder=5)
        
    # Styling
    ax.set_title(f"{ticker_name} Trend Analysis & Anomalies", fontsize=14, fontweight='bold', pad=15, color='#f8fafc')
    ax.set_xlabel('Date', fontsize=11, color='#94a3b8')
    ax.set_ylabel('Price (USD)', fontsize=11, color='#94a3b8')
    
    ax.grid(True, color='#1e293b', linestyle=':')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#1e293b')
    ax.spines['bottom'].set_color('#1e293b')
    
    ax.tick_params(colors='#94a3b8', labelsize=9)
    ax.legend(loc='upper left', frameon=True, facecolor='#0b0f19', edgecolor='#1e293b')
    
    plt.tight_layout()
    chart_filename = f"market-anomalies-{date_str}.png"
    chart_path = os.path.join(CHARTS_DIR, chart_filename)
    plt.savefig(chart_path, dpi=300, facecolor='#0b0f19')
    plt.close()
    
    print(f"Chart saved to {chart_path}")
    return chart_filename

def write_markdown_report(anomalies, last_close, daily_change, ticker_name, chart_filename, date_str):
    report_path = os.path.join(REPORTS_DIR, f"{date_str}-report.md")
    
    # Draft a LinkedIn post
    anomaly_alert = ""
    if anomalies:
        recent_anomaly = anomalies[-1]
        anomaly_alert = f"🚨 ANOMALY ALERT: A significant price deviation was detected on {recent_anomaly['date']} with a return of {recent_anomaly['return']}% (Z-score: {recent_anomaly['z_score']})."
    else:
        anomaly_alert = "📈 TREND STABILITY: Price movements remained within normal statistical boundaries."
        
    linkedin_post = f"""
### 💡 Daily Data Science Insights: Market Volatility Audit

{anomaly_alert}

**Key Metrics for {ticker_name}:**
- 📅 Date: {date_str}
- 💵 Close Price: ${last_close:,.2f}
- 📊 Daily Return: {daily_change:+.2f}%
- 🔍 Anomalies in last 45 days: {len(anomalies)}

This report was generated automatically by my data engineering and analytics pipeline hosted on GitHub Actions. It runs statistical anomaly detection models (Z-score thresholds) to audit market stability daily.

Check out the full interactive charts and source code on my Git profile!

#DataScience #MachineLearning #Finance #ETL #Automation #GitHubActions
    """.strip()

    report_content = f"""
# 📋 Daily Market Anomaly & Trend Report

**Target Asset:** {ticker_name}
**Execution Date:** {date_str}

---

## 📊 Performance Summary
* **Last Closing Price:** ${last_close:,.2f}
* **Daily Percent Change:** {daily_change:+.2f}%
* **Statistical Anomalies Detected:** {len(anomalies)}

---

## 🔍 Visual Analysis
Here is the trend visualization highlighting calculated moving averages and detected statistical outliers (Z-Score > 2.0):

![Market Anomalies Grid](../charts/{chart_filename})

---

## 🚨 Anomaly Event Log
| Date | Closing Price | Daily Return (%) | Outlier Z-Score |
|---|---|---|---|
"""
    if not anomalies:
        report_content += "| *N/A* | *No anomalies detected* | *N/A* | *N/A* |\n"
    else:
        for a in reversed(anomalies):
            report_content += f"| {a['date']} | ${a['close']:,.2f} | {a['return']:+}% | {a['z_score']} |\n"

    report_content += f"""
---

## 📝 Generated LinkedIn Draft
Copy and paste this drafted update for your professional portfolio feed:

```markdown
{linkedin_post}
```

---
*Generated by automated daily workflow pipeline at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content.strip() + "\n")
        
    print(f"Report saved to {report_path}")
    update_central_readme(ticker_name, date_str, last_close, daily_change, len(anomalies))

def update_central_readme(ticker_name, date_str, last_close, daily_change, anomaly_count):
    readme_path = os.path.join(BASE_DIR, "README.md")
    
    # Default header if file does not exist
    if not os.path.exists(readme_path):
        header = """
# 📈 Automated Daily Data Insights

Welcome! This repository is a fully automated daily data analysis showcase. Every single day, a GitHub Actions cron job wakes up, fetches market data, runs statistical anomaly detection, exports high-quality visualizations, and drafts a daily report.

## 🗂️ Execution History Index
| Date | Asset Class | Closing Price | Daily Return | Anomalies | Report Link |
|---|---|---|---|---|---|
"""
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(header.strip() + "\n")
            
    # Append the new row to the table
    row = f"| {date_str} | {ticker_name} | ${last_close:,.2f} | {daily_change:+.2f}% | {anomaly_count} | [View Report](./insights/reports/{date_str}-report.md) |\n"
    with open(readme_path, "a", encoding="utf-8") as f:
        f.write(row)
    print("Appended run details to central README.md index.")

def run():
    print("Starting daily market insights pipeline...")
    ensure_directories()
    
    # Target S&P 500 Index ETF (SPY) for standard daily trend
    ticker = "SPY"
    ticker_display = "S&P 500 ETF (SPY)"
    
    df = fetch_index_data(ticker, period="60d")
    
    if df.empty or len(df) < 2:
        print("Error: Could not retrieve sufficient data. Terminating pipeline.")
        return
        
    df, anomalies = detect_anomalies(df)
    
    # Get last day metrics
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    last_close = float(last_row['Close'])
    prev_close = float(prev_row['Close'])
    daily_change = ((last_close - prev_close) / prev_close) * 100.0
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Generate charts
    chart_filename = generate_visualization(df, ticker_display, today_str)
    
    # Write markdown reports
    if chart_filename:
        write_markdown_report(anomalies, last_close, daily_change, ticker_display, chart_filename, today_str)
        print("Daily automation job ran successfully!")
    else:
        print("Error: Could not render chart.")

if __name__ == '__main__':
    run()
