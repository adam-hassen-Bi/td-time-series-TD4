# Reflections — TD4

Numbers below come from the first real run of the workflow (15 Nov 2026), window
2026-08-17 → 2026-11-14, 90 days, 2,160 hourly readings per series.

## 1. Checking the "no real history" assumption (Stage 0)

One concrete action: open the Open-Meteo Air Quality docs and send one test request
with `past_days=90` (or just paste the URL in a browser) and count the rows that
come back. That takes two minutes and would have killed the synthetic-data plan
before any code was written. More generally, "the data doesn't exist yet" is a claim
about an API, so the check is one call to that API, not a design decision.

## 2. Prediction before running: rising, falling or flat? (Stage 1)

*Written before running the script:* I expect CO2 in Le Mans to be **rising**. The
window runs from mid-August to mid-November: in August vegetation in the Northern
Hemisphere is still absorbing a lot of CO2 (the yearly minimum is around
August–September), and from October leaves fall, photosynthesis drops, and heating
starts, so CO2 should climb into the autumn. I expect a small slope, a few tenths
of ppm per day at most, with a lot of daily noise from the weather.

*Checked in Stage 3:* rising, as predicted. The 90-day slope is **+0.207 ppm/day**
(about +18 ppm over the window), monthly means go 435.3 (Aug) → 441.0 (Sep) → 443.9
(Oct) → 454.1 ppm (first half of Nov). What I did not predict: the rise is not
steady. Over the last 30 days the slope is **+0.601 ppm/day**, three times the
90-day slope, so the increase is speeding up in November.

## 3. Zero gaps: can `clean_series()`'s gap detection be deleted? (Stage 2)

My run reports **0 gaps and 0 incomplete days** for all three series. That does not
make the gap detection useless. It shows that this source was clean on 15 November,
not that it always will be: CAMS is a model that backfills every hour, but the API
could still return a short window during an outage, and if I swap the source for a
real sensor (a CO2 monitor on a building that loses power or Wi-Fi), gaps become
normal. Without the reindexing, a missing week would just disappear, the dates would
be shifted, and the rolling mean and the slope would be computed over the wrong time
axis without any warning. The check costs a few lines and does nothing when the data
is clean, so I kept it. I also tested it on a made-up series with 4 days removed and
a day with 8/24 hours, and both were flagged.

## 4. Rolling mean vs exponential smoothing (Stage 3)

Last 5 values (Le Mans CO2):

| | 10 Nov | 11 Nov | 12 Nov | 13 Nov | 14 Nov |
|---|---|---|---|---|---|
| raw | 451.62 | 460.29 | 455.79 | 446.00 | 448.67 |
| rolling mean (7 d) | 457.22 | 458.75 | 458.22 | 454.71 | 452.58 |
| exp. smoothing (α 0.3) | 454.58 | 456.29 | 456.14 | 453.10 | 451.77 |

Something I did not expect: on 13 November the rolling mean drops *more* than the
exponential smoothing (−3.5 vs −3.0). That is not because of the new value, it is
because the peak of 6 November (470.6 ppm) leaves the 7-day window that day. The
rolling mean moves when an old value drops out, which has nothing to do with what
happens today. The exponential smoothing had already been forgetting that peak little
by little, which is why it was lower all week. I would use
**exponential smoothing** for monitoring, when a recent change matters, for example
an alert on air quality where a pollution episode should show up the day after,
not a week later. I would use the **rolling mean** when I want a stable "typical
level of the last week" for a weekly report: every one of the 7 days counts the
same, a single spike leaves the window after exactly 7 days, and it is easy to
explain to someone who is not technical.

## 5. What happens if the API call fails 4 times? (Stage 4)

Looking at the code: `fetch_series.py` re-raises the error for the primary series
(Le Mans CO2), so the Python process exits with an error code. In the workflow, the
steps run one after the other, so the failing `python scripts/fetch_series.py`
step stops the job: `analyze_series.py` and the commit step never run. Nothing is
written to the repo, so `data/series.csv` and `docs/data/series_analysis.json` stay
exactly as they were after last week's run. The dashboard does **not** break, it
shows **stale** numbers, and GitHub sends a failure email.

The risk is that stale looks like fresh. Two things I added for that: the dashboard
badge turns orange ("Data ends N days ago — weekly run may have failed") when the
last data day is more than 9 days old, and I base it on the last date in the data,
not on `generated_at`. Reason: if only an *extension* series fails (Tunis or PM2.5),
its error is written to `docs/data/fetch_status.json` and the others are updated,
but `analyze_series.py` re-runs on its old CSV and gives it a new `generated_at`. A
badge based on `generated_at` would say "updated this week" on old data.

## 6. How many days would I trust this projection? (Stage 5)

My numbers: the line projects 452.5 → 453.8 ppm over 7 days, so it moves by only
**1.45 ppm**, while the 95 % band at day 7 is **±11.5 ppm** (residual SD 5.7 ppm).
On 21 of the 89 days, CO2 moved by more than one residual SD from one day to the
next. So even at day 1, the line cannot tell "rising" from "flat": the weather noise
is 8 times bigger than a week of trend.

I would trust it for about **7 days**, and only as "the level will probably stay
in the 442–465 ppm range", not as a precise value. Not much more, because the
30-day slope (+0.60) is already 3× the 90-day slope (+0.21): the series is curving
up as winter comes, and the straight line is already behind (the last real values
are below the line, but the November average is above it). After 2–3 weeks the
real values could leave the band on the high side. Not much less either, because
the direction (rising until spring) is physically expected, so the line is not
wrong about the sign; the band is wide but it is honest. Across the season change
(around April–May, when vegetation starts absorbing again) the straight line would
be completely wrong, and no 90-day window from autumn can see that coming.

## 7. Why did changing one line not break anything? (Stage 6)

I did both extensions: **Tunis CO2** (where I studied at ESPRIT, different
latitude and climate) and **Le Mans PM2.5** (different variable). In
`analyze_series.py`, `clean_series`, `rolling_mean`, `exponential_smoothing`,
`fit_line` and `linear_trend_projection` take only a list of dates and a list of
numbers. They never mention a place, coordinates, a variable name or a unit. The
place, variable, unit and file names are all in `series_config.py`, and the
dashboard reads the unit and label from the JSON. So the code that does the maths
does not know what it is measuring, and adding a series is one entry in the config.

What the comparison shows:

| series | 90-day slope | 30-day slope | R² | day-7 band |
|---|---|---|---|---|
| Le Mans CO2 | +0.207 ppm/day | +0.601 | 0.47 | ±11.5 ppm |
| Tunis CO2 | +0.054 ppm/day | +0.219 | 0.04 | ±15.0 ppm |
| Le Mans PM2.5 | +0.086 µg/m³/day | +0.313 | 0.40 | ±5.6 µg/m³ |

- **Tunis** is almost flat over 90 days (R² 0.04: the line explains nothing), with a
  dip in September (monthly mean 447.7) before rising again in November (456.4).
  The Mediterranean vegetation cycle is different (dry summer, growth in autumn and
  winter), so the same "autumn = rising" logic does not apply directly. Same code,
  very different pattern.
- **PM2.5** in Le Mans almost triples, from 4.3 µg/m³ in August to 12.6 in November
  (heating, colder and calmer air). But it comes in episodes (peak 19.7 on
  6 November), so the band (±5.6) is huge compared to the level (~11). The low side
  of the band stays positive this time, but with a wider band it could go below 0,
  which is impossible for a concentration: a sign that a straight line with a
  symmetric band is the wrong model for this variable.

6 November is also the maximum of Le Mans CO2 (470.6 ppm) and of
PM2.5 (19.7 µg/m³), which suggests a weather episode (stagnant air) that affects
both, not a change in the trend.
