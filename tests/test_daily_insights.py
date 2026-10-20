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
