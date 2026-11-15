# CO2 time series lab — TD4

TD4 — Business Intelligence (ENSIM). Collect a real noisy time series, clean it,
smooth it two ways, and project it forward **honestly**: with the uncertainty the
straight line usually hides.

**Live dashboard:** https://adam-hassen-bi.github.io/td-time-series-TD4/

![dashboard](https://img.shields.io/badge/data-Open--Meteo%20CAMS-informational) ![schedule](https://img.shields.io/badge/update-weekly%20(Monday%206am%20UTC)-success)

## What it does

```
Open-Meteo Air Quality API (90 days, hourly)
        │  scripts/fetch_series.py      hourly → one row per day, days < 24 h flagged
        ▼
data/series.csv (+ 2 extension CSVs)
        │  scripts/analyze_series.py    reindex + gap detection, rolling mean (7 d),
        │                               exponential smoothing (α 0.3), linear trend
        │                               + 7-day projection with a 95 % band
        ▼
docs/data/series_analysis*.json  ──►  docs/index.html (GitHub Pages)
```

A GitHub Action (`.github/workflows/update_series.yml`, "Update analysis") runs both
scripts every Monday at 6:00 UTC and commits the new 90-day window, so the dashboard
always shows the last 90 days.

## First real run (15 Nov 2026, window 17 Aug → 14 Nov)

| series | latest day | 90-day slope | 30-day slope | R² | day-7 band |
|---|---|---|---|---|---|
| Le Mans CO2 (TD series) | 448.7 ppm | +0.207 ppm/day | +0.601 | 0.47 | ±11.5 ppm |
| Tunis CO2 | 457.1 ppm | +0.054 ppm/day | +0.219 | 0.04 | ±15.0 ppm |
| Le Mans PM2.5 | 12.0 µg/m³ | +0.086 µg/m³/day | +0.313 | 0.40 | ±5.6 µg/m³ |

0 gaps and 0 incomplete days in all three (the CAMS model backfills every hour).
CO2 in Le Mans is rising into winter and the rise is accelerating; the 7-day
projection moves 1.45 ppm while the band is ±11.5 ppm, so a week out the line cannot
tell "rising" from "flat". Discussion in [REFLECTIONS.md](REFLECTIONS.md).

## What I added to the TD's version

- **95 % prediction band** around the projection (`±1.96·s·√(1 + 1/n + (x−x̄)²/Sxx)`),
  drawn on the chart and shown day by day in "How much should you trust the line?".
- **30-day slope next to the 90-day slope**, and **R²**: if the two slopes differ a
  lot, the series is curving and the straight line is already behind.
- **Partial days flagged**: the number of real hours is kept per day; a day with
  fewer than 24 hours is drawn as a hollow dot and never used as "latest complete
  day" (a morning-only average is biased by the daily CO2 cycle).
- **Freshness badge** based on the last data day, not on the analysis timestamp, so
  a failed fetch cannot look fresh.
- **Stage 6, both extensions**: another place (Tunis, where I studied at ESPRIT) and
  another variable (PM2.5), with a series picker and a comparison table. Each is one
  entry in `scripts/series_config.py`; the analysis code doesn't change.
- **Failure handling**: if the TD's own series can't be fetched, the job stops before
  committing (last week's files stay). If an extension fails, it is skipped and
  recorded in `docs/data/fetch_status.json`.
- Charts are hand-written SVG (no chart library), light/dark mode, tooltips, works on
  mobile.

## Files

| file | role |
|---|---|
| `scripts/series_config.py` | the 3 series: place, coordinates, variable, unit, files, honesty note |
| `scripts/fetch_series.py` | API calls with retries, hourly → daily |
| `scripts/analyze_series.py` | cleaning, smoothing, projection, JSON for the dashboard |
| `.github/workflows/update_series.yml` | weekly run + commit |
| `docs/index.html` | dashboard |
| `data/` | daily CSVs (rewritten every week) |
| `docs/data/` | analysis JSON files read by the dashboard |
| `REFLECTIONS.md` | the 7 reflections |
| `serve.py` | open the dashboard locally |

## Run it locally

```bash
git clone https://github.com/adam-hassen-Bi/td-time-series-TD4.git
cd td-time-series-TD4
python3 serve.py              # opens http://localhost:8000 with the committed data
```

To refresh the data yourself:

```bash
pip3 install requests
python3 scripts/fetch_series.py
python3 scripts/analyze_series.py
python3 serve.py
```

Or on GitHub: **Actions → Update analysis → Run workflow**.

## Data source

[Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) — free,
no key. Values come from the CAMS reanalysis + forecast **model**, not from a
physical sensor at that address.
