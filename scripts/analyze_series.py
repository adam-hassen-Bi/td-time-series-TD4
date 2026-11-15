"""Clean, smooth and project every series collected by fetch_series.py.

The functions below never name a place, a variable or a unit: they take dates and
numbers. That is why changing the location or the variable in series_config.py
needs no change here.

Additions to the TD's version, all about honesty of the projection:
- a 95 % prediction interval around the straight-line projection, from the scatter
  of the real points around the line -- the band widens the further out you go;
- the slope over the last 30 days next to the slope over the full window: if they
  differ a lot, the series is curving and a straight line is already wrong;
- R² of the line, i.e. how much of the day-to-day variation the trend explains;
- days with fewer than 24 real hours are kept but flagged.
"""
import csv
import json
import math
import time
from datetime import date, timedelta

from series_config import SERIES

WINDOW = 7
ALPHA = 0.3
PROJECT_STEPS = 7
RECENT_DAYS = 30


def load_series(path):
    with open(path) as f:
        rows = []
        for r in csv.DictReader(f):
            v = r.get("co2_ppm", r.get("value", ""))
            if v == "":
                continue  # a day with zero real hourly readings -- nothing to average
            rows.append({"date": r["date"], "value": float(v), "n_hours": int(r.get("n_hours_observed") or 24)})
    return rows


def clean_series(rows):
    """Reindex to every calendar day; missing days are reported as gaps, not filled."""
    by_date = {r["date"]: r for r in rows}
    start = date.fromisoformat(rows[0]["date"])
    end = date.fromisoformat(rows[-1]["date"])
    cleaned, gaps = [], []
    for i in range((end - start).days + 1):
        d = (start + timedelta(days=i)).isoformat()
        if d in by_date:
            cleaned.append({"day": i, "date": d, "value": by_date[d]["value"], "n_hours": by_date[d]["n_hours"]})
        else:
            gaps.append(i)
    gap_ranges = []
    if gaps:
        seg_start = prev = gaps[0]
        for g in gaps[1:]:
            if g == prev + 1:
                prev = g
            else:
                gap_ranges.append((seg_start, prev))
                seg_start = prev = g
        gap_ranges.append((seg_start, prev))
    return cleaned, gap_ranges, start


def rolling_mean(values, window=WINDOW):
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1):i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def exponential_smoothing(values, alpha=ALPHA):
    out = [values[0]]
    for v in values[1:]:
        out.append(round(alpha * v + (1 - alpha) * out[-1], 2))
    return out


def fit_line(days, values):
    n = len(days)
    mx, my = sum(days) / n, sum(values) / n
    sxx = sum((x - mx) ** 2 for x in days)
    slope = sum((x - mx) * (y - my) for x, y in zip(days, values)) / sxx if sxx else 0.0
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(days, values)]
    sse = sum(r * r for r in resid)
    sst = sum((y - my) ** 2 for y in values)
    s = math.sqrt(sse / (n - 2)) if n > 2 else 0.0
    r2 = 1 - sse / sst if sst else 0.0
    return slope, intercept, s, r2, mx, sxx, n


def linear_trend_projection(days, values, start, steps=PROJECT_STEPS):
    """Least-squares line, extended `steps` days, with a 95 % prediction interval:
    value ± 1.96 · s · sqrt(1 + 1/n + (x - x̄)² / Sxx)."""
    slope, intercept, s, r2, mx, sxx, n = fit_line(days, values)
    projection = []
    for i in range(1, steps + 1):
        x = days[-1] + i
        y = intercept + slope * x
        half = 1.96 * s * math.sqrt(1 + 1 / n + ((x - mx) ** 2 / sxx if sxx else 0))
        projection.append({"day": x, "date": (start + timedelta(days=x)).isoformat(),
                           "value": round(y, 2), "low": round(y - half, 2), "high": round(y + half, 2)})
    return projection, slope, intercept, s, r2


def analyze(cfg):
    raw = load_series(cfg["csv"])
    cleaned, gap_ranges, start = clean_series(raw)
    print(f"\n[{cfg['id']}] {len(raw)} daily values ({raw[0]['date']} to {raw[-1]['date']})")
    for a, b in gap_ranges:
        print(f"  Gap: {(start + timedelta(days=a)).isoformat()} to {(start + timedelta(days=b)).isoformat()} "
              f"({b - a + 1} missing day(s)) -- flagged, not filled")
    if not gap_ranges:
        print("  No gaps -- the model backfills every hour; gap detection stays for sources that do not.")

    days = [c["day"] for c in cleaned]
    values = [c["value"] for c in cleaned]
    ma = rolling_mean(values)
    ex = exponential_smoothing(values)
    projection, slope, intercept, s, r2 = linear_trend_projection(days, values, start)
    recent_slope = fit_line(days[-RECENT_DAYS:], values[-RECENT_DAYS:])[0] if len(days) >= RECENT_DAYS else slope
    incomplete = [c["date"] for c in cleaned if c["n_hours"] < 24]

    print(f"  Last 5 raw:          {values[-5:]}")
    print(f"  Last 5 rolling mean: {ma[-5:]}")
    print(f"  Last 5 exp-smoothed: {ex[-5:]}")
    print(f"  Trend: {slope:+.3f} {cfg['unit']}/day over {len(days)} days (R² {r2:.2f}); "
          f"last {RECENT_DAYS} days: {recent_slope:+.3f} {cfg['unit']}/day")
    print(f"  Projection: {[p['value'] for p in projection]}  (day 7 band ±{projection[-1]['high'] - projection[-1]['value']:.2f})")

    honest_note = (f"Projection covers {PROJECT_STEPS} days ahead from {len(cleaned)} days of real history "
                   f"({len(gap_ranges)} known gap(s) in the source data). " + cfg["note"])
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "id": cfg["id"], "place": cfg["place"], "variable": cfg["variable"], "label": cfg["label"],
        "unit": cfg["unit"], "lat": cfg["lat"], "lon": cfg["lon"],
        "raw": [{"day": c["day"], "date": c["date"], "value": c["value"], "n_hours": c["n_hours"]} for c in cleaned],
        "gaps": [{"start_day": a, "end_day": b, "start_date": (start + timedelta(days=a)).isoformat(),
                  "end_date": (start + timedelta(days=b)).isoformat()} for a, b in gap_ranges],
        "incomplete_days": incomplete,
        "rolling_mean": [{"day": d, "value": v} for d, v in zip(days, ma)],
        "exp_smoothed": [{"day": d, "value": v} for d, v in zip(days, ex)],
        "projection": projection,
        "trend_slope_per_day": round(slope, 4),
        "trend_intercept": round(intercept, 3),
        "trend_r2": round(r2, 3),
        "residual_sd": round(s, 3),
        "recent_slope_per_day": round(recent_slope, 4),
        "recent_days": RECENT_DAYS,
        "params": {"window": WINDOW, "alpha": ALPHA, "project_steps": PROJECT_STEPS},
        "honest_note": honest_note,
    }
    with open(cfg["json"], "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {cfg['json']}")
    return out


def main():
    index = []
    for cfg in SERIES:
        try:
            o = analyze(cfg)
        except FileNotFoundError:
            print(f"\n[{cfg['id']}] no data file yet -- skipped")
            continue
        index.append({k: o[k] for k in ("id", "place", "label", "unit", "trend_slope_per_day",
                                        "recent_slope_per_day", "trend_r2", "generated_at")} |
                     {"file": cfg["json"].replace("docs/", ""), "last_value": o["raw"][-1]["value"],
                      "last_date": o["raw"][-1]["date"], "first_date": o["raw"][0]["date"]})
    with open("docs/data/series_index.json", "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "series": index}, f,
                  indent=2, ensure_ascii=False)
    print("\nWrote docs/data/series_index.json")


if __name__ == "__main__":
    main()
