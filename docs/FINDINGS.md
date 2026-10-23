# Findings

Measured results from the daily pipeline. Prices are real SPY closes from yFinance; the numbers below are copied from the files
named under each finding.

## Can a free GitHub Actions schedule run a daily data pipeline reliably?

**How it was tested.** `daily_insights.py` runs on a daily cron in GitHub Actions, fetches 60 days of prices with up to three
retries on a network or rate-limit error, and commits a chart and a report for each new trading day.

| Scheduled runs since 2026-06-19 | Succeeded | As of |
|---|---|---|
| 124 | 124 | 2026-10-20 |

**Decision.** The pipeline stays on the free Actions schedule with no server. Retries (`test_fetch_retries_a_transient_failure`),
skipping days that bring no new close (`test_a_trading_day_already_recorded_is_skipped`) and dropping rows without a valid price
(`test_missing_prices_never_reach_the_report`) keep a bad fetch from producing a wrong report.

**Source.** `README.md` (run count), `tests/test_daily_insights.py`, `insights/history.md`.

**Skills shown.** GitHub Actions (cron), Python, yFinance, pandas, pytest.

## What does a rolling Z-score flag on real market data?

**How it was tested.** Each daily return is compared with its 20-day mean; a return more than 2 standard deviations away is flagged
with its Z-score. The report for 2026-06-15 lists the anomalies in its 60-day window.

| Date | Daily return | Z-score |
|---|---|---|
| 2026-06-05 | -2.58% | 3.17 |
| 2026-05-15 | -1.2% | 2.08 |

**Conclusion.** The detector separates an ordinary move from a real outlier: the -2.58% day is more than 3 standard deviations out,
and a test (`test_a_spike_is_flagged_and_a_flat_series_is_not`) checks that a spike is flagged and a flat series is not. When the
latest trading day is itself an anomaly, the job emails an alert with the close, the return, the Z-score and the report link.

**Source.** `insights/reports/2026-06-15-report.md`, `tests/test_daily_insights.py`.

**Skills shown.** pandas rolling statistics, NumPy, Matplotlib, SMTP alerting, pytest.
