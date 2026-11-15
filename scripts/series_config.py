"""Which series the pipeline collects and analyses.

The first entry is the TD's own series (Le Mans CO2) and keeps the TD's file names
(data/series.csv, docs/data/series_analysis.json). The two others are my Stage 6
extensions: a different place (Tunis, where I studied at ESPRIT) and a different
variable (PM2.5 in Le Mans). Adding a series = adding one entry here; nothing in
fetch_series.py or analyze_series.py names a place, a variable or a unit.
"""

SERIES = [
    {
        "id": "le-mans-co2",
        "place": "Le Mans", "lat": 48.0061, "lon": 0.1996,
        "variable": "carbon_dioxide", "label": "CO₂", "unit": "ppm",
        "csv": "data/series.csv",
        "json": "docs/data/series_analysis.json",
        "primary": True,
        "note": (
            "CO2 has a well-known yearly cycle: lower in the Northern Hemisphere's growing "
            "season, rising again through autumn and winter as vegetation stops absorbing it. "
            "A trend measured over one 90-day window must NOT be extrapolated across a season "
            "boundary. Trust this projection only a few days out."
        ),
    },
    {
        "id": "tunis-co2",
        "place": "Tunis", "lat": 36.8065, "lon": 10.1815,
        "variable": "carbon_dioxide", "label": "CO₂", "unit": "ppm",
        "csv": "data/series_tunis-co2.csv",
        "json": "docs/data/series_analysis_tunis-co2.json",
        "note": (
            "Same yearly CO2 cycle as Le Mans, but a Mediterranean climate shifts the timing "
            "of the vegetation season. A straight line through one 90-day window is only a "
            "short-range description, not a forecast."
        ),
    },
    {
        "id": "le-mans-pm2_5",
        "place": "Le Mans", "lat": 48.0061, "lon": 0.1996,
        "variable": "pm2_5", "label": "PM2.5", "unit": "µg/m³",
        "csv": "data/series_le-mans-pm2_5.csv",
        "json": "docs/data/series_analysis_le-mans-pm2_5.json",
        "note": (
            "Fine particles are driven by weather episodes (calm cold days, heating, traffic, "
            "dust events) rather than a smooth trend: day-to-day swings are larger than any "
            "90-day slope. The straight-line projection is shown for comparison only and "
            "should not be trusted even a few days out."
        ),
    },
]
