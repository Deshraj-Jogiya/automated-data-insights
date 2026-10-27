import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import daily_insights as di  # noqa: E402


def _prices(values, start="2026-09-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.DataFrame({"Close": values}, index=idx)


def test_missing_prices_never_reach_the_report():
    df = _prices([100.0, np.nan, 101.0, np.inf])
    assert list(di.clean_prices(df)["Close"]) == [100.0, 101.0]


def test_a_spike_is_flagged_and_a_flat_series_is_not():
    calm = [100 + (i % 3) * 0.1 for i in range(40)]
    _, none = di.detect_anomalies(_prices(calm))
    _, found = di.detect_anomalies(_prices(calm[:-1] + [130.0]))
    assert none == [] and found and found[-1]["z_score"] > 2


def test_a_trading_day_already_recorded_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "HISTORY_PATH", str(tmp_path / "history.md"))
    assert di.recorded_dates() == set()
    di.append_history("SPY", "2026-10-16", 763.23, -1.11, 1)
    di.append_history("SPY", "2026-10-19", 766.48, 0.42, 1)
    assert di.recorded_dates() == {"2026-10-16", "2026-10-19"}


class _FakeSMTP:
    sent = []

    def __init__(self, host, port):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)


ANOMALY = {"date": "2026-10-19", "close": 640.5, "return": -3.2, "z_score": 2.7}


def test_alert_is_skipped_without_smtp_settings(monkeypatch):
    for k in ("ALERT_SMTP_USER", "ALERT_SMTP_PASSWORD", "ALERT_EMAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    _FakeSMTP.sent.clear()
    assert di.send_anomaly_alert(ANOMALY, "SPY", "2026-10-19", smtp_factory=_FakeSMTP) is False
    assert _FakeSMTP.sent == []


def test_alert_email_names_the_move_and_links_the_report(monkeypatch):
    monkeypatch.setenv("ALERT_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("ALERT_SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("ALERT_EMAIL_TO", "me@example.com")
    _FakeSMTP.sent.clear()
    assert di.send_anomaly_alert(ANOMALY, "SPY", "2026-10-19", smtp_factory=_FakeSMTP) is True
    msg = _FakeSMTP.sent[0]
    assert msg["Subject"] == "Market anomaly: SPY down 3.2% on 2026-10-19"
    assert msg["To"] == "me@example.com"
    body = msg.get_content()
    assert "2.7 standard deviations" in body and "insights/reports/2026-10-19-report.md" in body


def test_fetch_retries_a_transient_failure(monkeypatch):
    calls = {"n": 0}

    class FlakyTicker:
        def __init__(self, ticker):
            pass

        def history(self, period):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("temporary")
            return _prices([100.0, 101.0])

    monkeypatch.setattr(di.yf, "Ticker", FlakyTicker)
    df = di.fetch_index_data("SPY", sleep=lambda s: None)
    assert calls["n"] == 3 and len(df) == 2


def test_a_weekend_or_zero_volume_bar_is_not_a_trading_day():
    idx = pd.to_datetime(["2026-10-15", "2026-10-16", "2026-10-17", "2026-10-19"])  # Thu, Fri, Sat, Mon
    df = pd.DataFrame({"Close": [771.8, 763.23, 763.25, 766.48], "Volume": [10, 12, 0, 9]}, index=idx)
    kept = di.clean_prices(df)
    assert [d.strftime("%Y-%m-%d") for d in kept.index] == ["2026-10-15", "2026-10-16", "2026-10-19"]
    holiday = pd.DataFrame({"Close": [100.0, 100.0]}, index=pd.to_datetime(["2026-11-25", "2026-11-26"])).assign(Volume=[5, 0])
    assert len(di.clean_prices(holiday)) == 1  # Thanksgiving bar with no volume is dropped
