# Daily Market Insights & Anomaly Detection Automation Pipeline
import os
import re
import smtplib
from email.message import EmailMessage
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Output directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE_DIR, "insights", "charts")
REPORTS_DIR = os.path.join(BASE_DIR, "insights", "reports")

def ensure_directories():
    os.makedirs(CHARTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

def fetch_index_data(ticker, period="60d", attempts=3, wait_seconds=20, sleep=None):
    """Fetch price history from yfinance, retrying a few times so a passing network or rate-limit error doesn't cost a day."""
    import time
    sleep = sleep or time.sleep
    for attempt in range(1, attempts + 1):
        print(f"Fetching data for {ticker} (period: {period}), attempt {attempt}/{attempts}...")
        try:
            df = yf.Ticker(ticker).history(period=period)
            if df.empty:
                raise ValueError(f"Empty dataframe returned for {ticker}")
            return df
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            if attempt < attempts:
                sleep(wait_seconds * attempt)
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
    
    if anomalies:
        latest = anomalies[-1]
        summary = (f"Latest anomaly: {latest['date']}, daily return {latest['return']}% "
                   f"(Z-score {latest['z_score']}).")
    else:
        summary = "No daily return moved more than 2 standard deviations from its 20-day mean."

    report_content = f"""
# Daily Market Anomaly Report

**Target Asset:** {ticker_name}
**Trading Date:** {date_str}

{summary}

---

## Summary
* **Last Closing Price:** ${last_close:,.2f}
* **Daily Percent Change:** {daily_change:+.2f}%
* **Anomalies in the 60-day window:** {len(anomalies)}

---

## Chart
Here is the trend visualization highlighting calculated moving averages and detected statistical outliers (Z-Score > 2.0):

![Market Anomalies Grid](../charts/{chart_filename})

---

## Anomalies in the last 60 days
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
*Generated by automated daily workflow pipeline at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content.strip() + "\n")
        
    print(f"Report saved to {report_path}")
    append_history(ticker_name, date_str, last_close, daily_change, len(anomalies))

HISTORY_PATH = os.path.join(BASE_DIR, "insights", "history.md")
HISTORY_HEADER = """# Run history

One row per trading day the pipeline analysed. Weekends and market holidays are skipped: they bring no new close.

| Trading date | Asset | Close | Daily return | Anomalies (60 days) | Report |
|---|---|---|---|---|---|
"""


def recorded_dates():
    """Trading dates already in the run history."""
    if not os.path.exists(HISTORY_PATH):
        return set()
    with open(HISTORY_PATH, encoding="utf-8") as f:
        return {line.split("|")[1].strip() for line in f if re.match(r"\| \d{4}-\d{2}-\d{2} \|", line)}


def append_history(ticker_name, date_str, last_close, daily_change, anomaly_count):
    if not os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            f.write(HISTORY_HEADER)
    row = (f"| {date_str} | {ticker_name} | ${last_close:,.2f} | {daily_change:+.2f}% | {anomaly_count} | "
           f"[report](./reports/{date_str}-report.md) |\n")
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(row)
    print(f"Recorded {date_str} in {HISTORY_PATH}")


def clean_prices(df):
    """Drop rows without a close price, so a gap in the feed can never reach the report as $nan."""
    if df.empty:
        return df
    return df[df["Close"].notna() & np.isfinite(df["Close"])]


REPO_URL = "https://github.com/Deshraj-Jogiya/automated-data-insights"


def send_anomaly_alert(anomaly, ticker_name, date_str, smtp_factory=smtplib.SMTP_SSL, test=False):
    """Email an alert when the latest trading day is itself an anomaly.

    Reads ALERT_SMTP_USER, ALERT_SMTP_PASSWORD and ALERT_EMAIL_TO from the environment (GitHub Actions secrets). Returns True when an
    email was sent and False when the settings are missing, so a fork without them still runs the rest of the pipeline.
    """
    user, password, to = (os.environ.get(k) for k in ("ALERT_SMTP_USER", "ALERT_SMTP_PASSWORD", "ALERT_EMAIL_TO"))
    if not (user and password and to):
        print("Email alert skipped: ALERT_SMTP_USER, ALERT_SMTP_PASSWORD and ALERT_EMAIL_TO are not all set.")
        return False
    direction = "up" if anomaly["return"] > 0 else "down"
    msg = EmailMessage()
    msg["Subject"] = ("[Test] " if test else "") + f"Market anomaly: {ticker_name} {direction} {abs(anomaly['return'])}% on {date_str}"
    msg["From"] = user
    msg["To"] = to
    msg.set_content(
        f"{ticker_name} closed at ${anomaly['close']:,.2f} on {date_str}, a daily return of {anomaly['return']:+}%.\n"
        f"That is {anomaly['z_score']} standard deviations from its 20-day average return (alert threshold: 2).\n\n"
        f"Report: {REPO_URL}/blob/main/insights/reports/{date_str}-report.md\n"
    )
    with smtp_factory(os.environ.get("ALERT_SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("ALERT_SMTP_PORT", "465"))) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Email alert sent to {to}.")
    return True


def latest_day_sample(df, last_close, daily_change):
    """The latest day's close, return and Z-score in the same shape as an anomaly record."""
    z = 0.0
    if "Return_Std_20" in df and df["Return_Std_20"].iloc[-1] > 0:
        z = abs(df["Daily_Return"].iloc[-1] - df["Return_MA_20"].iloc[-1]) / df["Return_Std_20"].iloc[-1]
    return {"close": round(last_close, 2), "return": round(daily_change, 2), "z_score": round(float(z), 2)}


def run():
    print("Starting daily market insights pipeline...")
    ensure_directories()
    
    # Target S&P 500 Index ETF (SPY) for standard daily trend
    ticker = "SPY"
    ticker_display = "S&P 500 ETF (SPY)"
    
    df = clean_prices(fetch_index_data(ticker, period="60d"))

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
    
    # Name everything after the last trading day in the data, not the calendar day the job ran: a weekend or holiday run
    # brings no new close and is skipped instead of repeating Friday's numbers under a new date.
    today_str = df.index[-1].strftime("%Y-%m-%d")
    latest_is_anomaly = bool(anomalies) and anomalies[-1]["date"] == today_str
    if os.environ.get("ALERT_TEST") == "1" and not latest_is_anomaly:
        # Manual check of the email settings: send the latest day's numbers, marked as a test
        send_anomaly_alert(latest_day_sample(df, last_close, daily_change), ticker_display, today_str, test=True)
    if today_str in recorded_dates():
        print(f"No new trading day since {today_str}; nothing to report.")
        return

    # Generate charts
    chart_filename = generate_visualization(df, ticker_display, today_str)

    # Write markdown reports
    if chart_filename:
        write_markdown_report(anomalies, last_close, daily_change, ticker_display, chart_filename, today_str)
        if latest_is_anomaly:
            send_anomaly_alert(anomalies[-1], ticker_display, today_str)
        print("Daily automation job ran successfully!")
    else:
        print("Error: Could not render chart.")

if __name__ == '__main__':
    run()
