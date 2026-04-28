"""
CadenceWorks — Holiday Enrichment Layer
South African Public Holiday Calendar (2024–2027)

Enriches a UDM DataFrame with holiday context columns:
  - is_public_holiday     : bool
  - holiday_name          : str or None
  - is_day_before_holiday : bool
  - is_day_after_holiday  : bool
  - holiday_proximity     : str  ('Holiday', 'Day Before', 'Day After', 'Normal')
  - school_holiday_risk   : bool (rough proxy — Dec/Jun/Jul/Sep school breaks)

These features are used by:
  - The predictive model (risk scoring)
  - The descriptive analytics (no-show breakdowns)
  - The AI Narrator (explaining seasonal patterns)
  - The prescriptive layer (holiday-aware recommendations)
"""

import pandas as pd
from datetime import date, timedelta


# ── SA Public Holidays 2024–2027 ───────────────────────────────────────────────
# Source: South African Government (www.gov.za/about-sa/public-holidays)
# Observed days included where Monday substitution applies

SA_PUBLIC_HOLIDAYS = {
    # 2024
    "2024-01-01": "New Year's Day",
    "2024-03-21": "Human Rights Day",
    "2024-03-29": "Good Friday",
    "2024-04-01": "Family Day",
    "2024-04-27": "Freedom Day",
    "2024-04-28": "Freedom Day (observed)",  # Sunday → Monday
    "2024-05-01": "Workers' Day",
    "2024-06-16": "Youth Day",
    "2024-06-17": "Youth Day (observed)",    # Sunday → Monday
    "2024-08-09": "National Women's Day",
    "2024-09-24": "Heritage Day",
    "2024-12-16": "Day of Reconciliation",
    "2024-12-25": "Christmas Day",
    "2024-12-26": "Day of Goodwill",

    # 2025
    "2025-01-01": "New Year's Day",
    "2025-03-21": "Human Rights Day",
    "2025-04-18": "Good Friday",
    "2025-04-21": "Family Day",
    "2025-04-27": "Freedom Day",
    "2025-04-28": "Freedom Day (observed)",  # Sunday → Monday
    "2025-05-01": "Workers' Day",
    "2025-06-16": "Youth Day",
    "2025-08-09": "National Women's Day",
    "2025-08-11": "National Women's Day (observed)",  # Saturday → Monday
    "2025-09-24": "Heritage Day",
    "2025-12-16": "Day of Reconciliation",
    "2025-12-25": "Christmas Day",
    "2025-12-26": "Day of Goodwill",

    # 2026
    "2026-01-01": "New Year's Day",
    "2026-03-21": "Human Rights Day",
    "2026-03-23": "Human Rights Day (observed)",  # Saturday → Monday
    "2026-04-03": "Good Friday",
    "2026-04-06": "Family Day",
    "2026-04-27": "Freedom Day",
    "2026-05-01": "Workers' Day",
    "2026-06-16": "Youth Day",
    "2026-08-09": "National Women's Day",
    "2026-09-24": "Heritage Day",
    "2026-12-16": "Day of Reconciliation",
    "2026-12-25": "Christmas Day",
    "2026-12-26": "Day of Goodwill",

    # 2027
    "2027-01-01": "New Year's Day",
    "2027-03-21": "Human Rights Day",
    "2027-03-22": "Human Rights Day (observed)",  # Sunday → Monday
    "2027-03-26": "Good Friday",
    "2027-03-29": "Family Day",
    "2027-04-27": "Freedom Day",
    "2027-05-01": "Workers' Day",
    "2027-06-16": "Youth Day",
    "2027-08-09": "National Women's Day",
    "2027-09-24": "Heritage Day",
    "2027-12-16": "Day of Reconciliation",
    "2027-12-25": "Christmas Day",
    "2027-12-26": "Day of Goodwill",
}

# Convert to date objects for fast lookup
_HOLIDAY_MAP = {
    pd.to_datetime(k).date(): v
    for k, v in SA_PUBLIC_HOLIDAYS.items()
}

_HOLIDAY_DATES = set(_HOLIDAY_MAP.keys())

# ── School holiday risk periods (approximate SA school calendar) ───────────────
# These are the high-risk periods where patient attendance drops because
# families travel. Not exact — practices in different provinces may vary.
_SCHOOL_HOLIDAY_PERIODS = [
    # Term 1 break (late March / early April)
    ("2025-03-22", "2025-04-01"),
    ("2026-03-21", "2026-04-07"),

    # Term 2 break (late June / early July)
    ("2025-06-28", "2025-07-13"),
    ("2026-06-27", "2026-07-12"),

    # Term 3 break (late September / early October)
    ("2025-09-27", "2025-10-05"),
    ("2026-09-26", "2026-10-04"),

    # Term 4 / December summer break (early Dec → mid Jan)
    ("2025-12-03", "2026-01-11"),
    ("2024-12-04", "2025-01-12"),
]

_SCHOOL_HOLIDAY_DATES: set = set()
for start_str, end_str in _SCHOOL_HOLIDAY_PERIODS:
    start = pd.to_datetime(start_str).date()
    end   = pd.to_datetime(end_str).date()
    d = start
    while d <= end:
        _SCHOOL_HOLIDAY_DATES.add(d)
        d += timedelta(days=1)


def is_public_holiday(d: date) -> bool:
    """Return True if the date is a SA public holiday."""
    return d in _HOLIDAY_DATES


def get_holiday_name(d: date):
    """Return the holiday name for a date, or None."""
    return _HOLIDAY_MAP.get(d)


def is_school_holiday_risk(d: date) -> bool:
    """Return True if the date falls in a school holiday period."""
    return d in _SCHOOL_HOLIDAY_DATES


def enrich(df: pd.DataFrame, date_col: str = "appointment_date") -> pd.DataFrame:
    """
    Enrich a UDM DataFrame with holiday context columns.

    Args:
        df:       UDM DataFrame (from ingestor or client_ingestor)
        date_col: Name of the date column to use

    Returns:
        DataFrame with added holiday columns (does not modify original)
    """
    df = df.copy()

    dates = pd.to_datetime(df[date_col], errors="coerce").dt.date

    df["is_public_holiday"]     = dates.map(lambda d: d in _HOLIDAY_DATES if pd.notna(d) else False)
    df["holiday_name"]          = dates.map(lambda d: _HOLIDAY_MAP.get(d) if pd.notna(d) else None)
    df["is_day_before_holiday"] = dates.map(
        lambda d: (d + timedelta(days=1)) in _HOLIDAY_DATES if pd.notna(d) else False
    )
    df["is_day_after_holiday"]  = dates.map(
        lambda d: (d - timedelta(days=1)) in _HOLIDAY_DATES if pd.notna(d) else False
    )
    df["school_holiday_risk"]   = dates.map(
        lambda d: d in _SCHOOL_HOLIDAY_DATES if pd.notna(d) else False
    )

    # Combined proximity label — useful for the AI Narrator and charts
    def _proximity(row):
        if row["is_public_holiday"]:
            return "Public Holiday"
        if row["is_day_before_holiday"]:
            return "Day Before Holiday"
        if row["is_day_after_holiday"]:
            return "Day After Holiday"
        if row["school_holiday_risk"]:
            return "School Holiday Period"
        return "Normal"

    df["holiday_proximity"] = df.apply(_proximity, axis=1)

    return df


def holiday_noshow_analysis(df: pd.DataFrame) -> dict:
    """
    Analyse no-show rates by holiday proximity.
    Requires enriched DataFrame (run enrich() first).

    Returns a dict with:
      - noshow_by_proximity: no-show rate per holiday_proximity band
      - worst_period: the proximity band with the highest no-show rate
      - holiday_impact_score: how much worse holidays are vs normal days
      - affected_appointments: count of appointments in holiday periods
      - revenue_at_risk: estimated revenue at risk on holiday-adjacent days
    """
    required = {"status", "holiday_proximity", "fee"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"Missing columns for holiday analysis: {missing}")

    result = {}

    # No-show rate by proximity band
    bands = {}
    for band, grp in df.groupby("holiday_proximity"):
        total    = len(grp)
        noshows  = (grp["status"] == "No-Show").sum()
        rate     = round(noshows / total * 100, 1) if total > 0 else 0
        bands[band] = {
            "total":       int(total),
            "no_shows":    int(noshows),
            "noshow_rate": rate,
            "revenue_lost": float(grp[grp["status"] == "No-Show"]["fee"].sum()),
        }
    result["noshow_by_proximity"] = bands

    # Baseline: normal days
    normal_rate = bands.get("Normal", {}).get("noshow_rate", 0)

    # Worst performing period
    worst_band  = max(bands, key=lambda b: bands[b]["noshow_rate"])
    worst_rate  = bands[worst_band]["noshow_rate"]
    result["worst_period"] = worst_band
    result["worst_rate"]   = worst_rate

    # Impact score: how much worse is the worst period vs normal
    result["holiday_impact_score"] = round(worst_rate - normal_rate, 1)

    # Affected appointments (anything not Normal)
    affected = df[df["holiday_proximity"] != "Normal"]
    result["affected_appointments"] = len(affected)
    result["revenue_at_risk"] = float(
        affected[affected["status"] != "Completed"]["fee"].sum()
    )

    # Monthly holiday summary (useful for the Narrator)
    df["month"] = pd.to_datetime(df["appointment_date"], errors="coerce").dt.to_period("M")
    monthly_holidays = (
        df[df["is_public_holiday"]]
        .groupby("month")
        .agg(holiday_appointments=("status", "count"),
             holiday_noshows=("status", lambda x: (x == "No-Show").sum()))
        .reset_index()
    )
    monthly_holidays["month"] = monthly_holidays["month"].astype(str)
    result["monthly_holiday_impact"] = monthly_holidays.to_dict(orient="records")

    return result


def get_upcoming_holidays(days_ahead: int = 30) -> list:
    """
    Return a list of public holidays in the next N days.
    Useful for the Reminder Agent to flag high-risk upcoming periods.
    """
    today = date.today()
    end   = today + timedelta(days=days_ahead)
    upcoming = []
    d = today
    while d <= end:
        if d in _HOLIDAY_DATES:
            days_until = (d - today).days
            upcoming.append({
                "date":       str(d),
                "name":       _HOLIDAY_MAP[d],
                "days_until": days_until,
                "risk_note":  (
                    "High no-show risk — consider reminder burst 48hrs before"
                    if days_until <= 7
                    else "Monitor no-show rate as date approaches"
                ),
            })
        d += timedelta(days=1)
    return upcoming


# ── CLI test ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from engine.client_ingestor import ingest_two_file

    if len(sys.argv) < 3:
        print("Usage: python -m engine.holiday_enrichment <type_file> <status_file>")
        sys.exit(1)

    hist, future, meta = ingest_two_file(sys.argv[1], sys.argv[2])

    print("\nEnriching with holiday data...")
    enriched = enrich(hist)

    print("\n=== HOLIDAY PROXIMITY BREAKDOWN ===")
    print(enriched["holiday_proximity"].value_counts().to_string())

    print("\n=== NO-SHOW ANALYSIS BY HOLIDAY PROXIMITY ===")
    analysis = holiday_noshow_analysis(enriched)
    for band, stats in analysis["noshow_by_proximity"].items():
        print(f"\n  {band}:")
        print(f"    Appointments : {stats['total']:,}")
        print(f"    No-shows     : {stats['no_shows']:,}")
        print(f"    No-show rate : {stats['noshow_rate']}%")
        print(f"    Revenue lost : R{stats['revenue_lost']:,.0f}")

    print(f"\n  Worst period   : {analysis['worst_period']} ({analysis['worst_rate']}%)")
    print(f"  Holiday impact : +{analysis['holiday_impact_score']}% vs normal days")

    print("\n=== UPCOMING SA PUBLIC HOLIDAYS (next 60 days) ===")
    for h in get_upcoming_holidays(60):
        print(f"  {h['date']}  {h['name']}  ({h['days_until']} days away)")
        print(f"    → {h['risk_note']}")
