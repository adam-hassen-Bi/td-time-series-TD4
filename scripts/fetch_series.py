"""Collect ~90 days of real hourly air-quality data from Open-Meteo and store one
row per day.

Open-Meteo's Air Quality API is free and keyless. Its values come from the CAMS
reanalysis + forecast MODEL, not from one physical sensor, so the model backfills
every hour -- a real sensor feed would have gaps, and the pipeline is written for
that case anyway.

past_days=90 returns real history in ONE call: there was never a need to fake the
data or wait weeks for a scheduled pipeline to accumulate it.

One API call per series in series_config.py. If the TD's own series (Le Mans CO2)
cannot be fetched, the script fails and the workflow stops BEFORE committing, so
last week's files stay as they are (stale, not broken). If an extension series
fails, it is skipped and recorded in docs/data/fetch_status.json, and the others
are still updated.
"""
import csv
import json
import os
import sys
import time

import requests

from series_config import SERIES

PAST_DAYS = 90
URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_hourly(lat, lon, variable, retries=4, backoff=5):
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": variable,
        "past_days": PAST_DAYS,
        "forecast_days": 0,
        "timezone": "auto",
    }
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(URL, params=params, timeout=(15, 30))
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"  fetch attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"Open-Meteo Air Quality API unreachable after {retries} attempts") from last_error


def aggregate_to_daily(times, values):
    """Hourly -> one row per calendar day (mean of the day's real hours). A day with
    fewer than 24 real hours is flagged with its count, not silently averaged."""
    by_day = {}
    for t, v in zip(times, values):
        by_day.setdefault(t[:10], []).append(v)
    rows = []
    for day in sorted(by_day):
        real_hours = [h for h in by_day[day] if h is not None]
        rows.append({
            "date": day,
            "value": round(sum(real_hours) / len(real_hours), 2) if real_hours else "",
            "n_hours_observed": len(real_hours),
        })
    return rows


def fetch_one(s):
    print(f"\n[{s['id']}] {PAST_DAYS} days of hourly {s['variable']} ({s['unit']}) for {s['place']} "
          f"({s['lat']}, {s['lon']})...")
    data = fetch_hourly(s["lat"], s["lon"], s["variable"])
    times = data["hourly"]["time"]
    values = data["hourly"][s["variable"]]
    print(f"  received {len(times)} hourly readings ({times[0]} to {times[-1]})")
    rows = aggregate_to_daily(times, values)
    incomplete = [r for r in rows if r["n_hours_observed"] < 24]
    print(f"  aggregated to {len(rows)} days -- {len(incomplete)} with fewer than 24 real hours")
    for r in incomplete:
        print(f"    incomplete day: {r['date']} ({r['n_hours_observed']}/24 hours)")

    # The TD's file keeps the TD's column name (co2_ppm); extension files use a
    # generic one. analyze_series.py reads either.
    value_col = "co2_ppm" if s.get("primary") else "value"
    os.makedirs(os.path.dirname(s["csv"]), exist_ok=True)
    with open(s["csv"], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", value_col, "n_hours_observed"])
        w.writeheader()
        for r in rows:
            w.writerow({"date": r["date"], value_col: r["value"], "n_hours_observed": r["n_hours_observed"]})
    print(f"  wrote {s['csv']} ({len(rows)} days)")
    return {"ok": True, "days": len(rows), "incomplete_days": len(incomplete),
            "first_date": rows[0]["date"], "last_date": rows[-1]["date"]}


def main():
    status = {}
    for s in SERIES:
        try:
            status[s["id"]] = fetch_one(s)
        except Exception as e:
            print(f"  FAILED: {e}")
            if s.get("primary"):
                # stop here: the workflow's commit step never runs, last week's files stay
                raise
            status[s["id"]] = {"ok": False, "error": str(e)[:200]}
    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/fetch_status.json", "w") as f:
        json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "series": status}, f, indent=2)
    if not all(v["ok"] for v in status.values()):
        print("\nSome extension series failed -- see docs/data/fetch_status.json", file=sys.stderr)


if __name__ == "__main__":
    main()
