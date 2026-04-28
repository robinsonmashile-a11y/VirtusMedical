"""
CadenceWorks - Weather Enrichment
Fetches historical Cape Town weather from Open-Meteo (free, no API key).
Adds rain/wind/temp columns to the booking DataFrame.
"""
import json
from pathlib import Path
from typing import Optional
import pandas as pd

CAPE_TOWN = {"latitude": -33.9249, "longitude": 18.4241}
RAIN_BANDS = {"Dry": (0,1), "Light Rain": (1,5), "Moderate Rain": (5,10), "Heavy Rain": (10,9999)}

def _rain_cat(mm):
    for cat, (lo, hi) in RAIN_BANDS.items():
        if lo <= mm < hi:
            return cat
    return "Heavy Rain"

def _risk_score(df):
    rain = (df["precipitation_mm"].clip(0, 30) / 30).fillna(0)
    wind = (df["wind_speed_max_kmh"].clip(0, 80) / 80).fillna(0)
    cold = ((15 - df["temp_max_c"]).clip(0, 15) / 15).fillna(0)
    return (rain * 0.50 + wind * 0.25 + cold * 0.25).round(3)

def fetch_weather(start_date: str, end_date: str,
                  latitude: float = CAPE_TOWN["latitude"],
                  longitude: float = CAPE_TOWN["longitude"]) -> pd.DataFrame:
    import requests
    cache = Path(f"/tmp/cw_wx_{start_date}_{end_date}.json")
    if cache.exists():
        raw = json.loads(cache.read_text())
    else:
        resp = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            timeout=30,
            params={
                "latitude": latitude, "longitude": longitude,
                "start_date": start_date, "end_date": end_date,
                "daily": ["temperature_2m_max", "temperature_2m_min",
                          "precipitation_sum", "wind_speed_10m_max"],
                "timezone": "Africa/Johannesburg",
                "wind_speed_unit": "kmh",
            }
        )
        resp.raise_for_status()
        raw = resp.json()
        cache.write_text(json.dumps(raw))

    d = raw.get("daily", {})
    df = pd.DataFrame({
        "date":               pd.to_datetime(d.get("time", [])),
        "temp_max_c":         pd.to_numeric(d.get("temperature_2m_max", []), errors="coerce"),
        "temp_min_c":         pd.to_numeric(d.get("temperature_2m_min", []), errors="coerce"),
        "precipitation_mm":   pd.to_numeric(d.get("precipitation_sum",   []), errors="coerce").fillna(0),
        "wind_speed_max_kmh": pd.to_numeric(d.get("wind_speed_10m_max",  []), errors="coerce").fillna(0),
    })
    df["is_rainy_day"]        = df["precipitation_mm"] > 1.0
    df["is_heavy_rain"]       = df["precipitation_mm"] > 10.0
    df["is_windy_day"]        = df["wind_speed_max_kmh"] > 40.0
    df["is_cold_day"]         = df["temp_max_c"] < 15.0
    df["rain_category"]       = df["precipitation_mm"].apply(_rain_cat)
    df["weather_risk_score"]  = _risk_score(df)
    return df

def enrich(df: pd.DataFrame, date_col: str = "appointment_date",
           latitude: float = CAPE_TOWN["latitude"],
           longitude: float = CAPE_TOWN["longitude"]) -> pd.DataFrame:
    df = df.copy()
    dates = pd.to_datetime(df[date_col], errors="coerce")
    valid = dates.dropna()
    if valid.empty:
        return df
    try:
        wx = fetch_weather(
            valid.min().strftime("%Y-%m-%d"),
            valid.max().strftime("%Y-%m-%d"),
            latitude, longitude,
        )
    except Exception as e:
        print(f"  [weather] fetch failed: {e}")
        return df
    df["_dk"] = dates.dt.normalize()
    wx["_dk"] = wx["date"].dt.normalize()
    cols = ["_dk", "temp_max_c", "temp_min_c", "precipitation_mm", "rain_category",
            "wind_speed_max_kmh", "is_rainy_day", "is_heavy_rain",
            "is_windy_day", "is_cold_day", "weather_risk_score"]
    return df.merge(wx[cols], on="_dk", how="left").drop(columns=["_dk"])

def analyse(df: pd.DataFrame) -> dict:
    """Return no-show rates by rain band, wind, and weather quartile."""
    if "rain_category" not in df.columns or "status" not in df.columns:
        return {}

    out = {}

    # By rain band
    bands = {}
    for band in ["Dry", "Light Rain", "Moderate Rain", "Heavy Rain"]:
        g = df[df["rain_category"] == band]
        if not len(g):
            continue
        ns = (g["status"] == "No-Show").sum()
        bands[band] = {
            "total":        int(len(g)),
            "no_shows":     int(ns),
            "noshow_rate":  round(ns / len(g) * 100, 1),
            "revenue_lost": float(g[g["status"] == "No-Show"]["fee"].sum())
                            if "fee" in df.columns else 0,
        }
    out["noshow_by_rain"] = bands

    dry = bands.get("Dry", {}).get("noshow_rate", 0)
    wet = bands.get("Heavy Rain", bands.get("Moderate Rain", {})).get("noshow_rate", 0)
    out["rain_uplift"]           = round(wet - dry, 1)
    out["weather_is_significant"] = abs(out["rain_uplift"]) >= 2.0

    # By wind
    if "is_windy_day" in df.columns:
        w  = df[df["is_windy_day"] == True]
        nw = df[df["is_windy_day"] == False]
        if len(w) and len(nw):
            out["windy_day_noshow_rate"] = round((w["status"] == "No-Show").mean() * 100, 1)
            out["calm_day_noshow_rate"]  = round((nw["status"] == "No-Show").mean() * 100, 1)
            out["wind_uplift"] = round(out["windy_day_noshow_rate"] - out["calm_day_noshow_rate"], 1)

    # By weather risk quartile
    if "weather_risk_score" in df.columns:
        df2 = df.copy()
        try:
            df2["wq"] = pd.qcut(
                df2["weather_risk_score"].fillna(0), q=4,
                labels=["Q1 (Best)", "Q2", "Q3", "Q4 (Worst)"],
                duplicates="drop"
            )
            out["noshow_by_weather_quartile"] = {
                str(q): {
                    "total":       int(len(g)),
                    "noshow_rate": round((g["status"] == "No-Show").mean() * 100, 1),
                }
                for q, g in df2.groupby("wq", observed=True)
            }
        except Exception:
            pass

    out["recommendation"] = (
        f"Rain increases no-show rate by {out['rain_uplift']}% — factor into reminder timing."
        if out["weather_is_significant"]
        else "Weather signal small (<2%) — continue monitoring."
    )
    return out

def get_forecast(days_ahead: int = 7,
                 latitude: float = CAPE_TOWN["latitude"],
                 longitude: float = CAPE_TOWN["longitude"]) -> list:
    """7-day forecast with reminder boost flags."""
    import requests
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            timeout=15,
            params={
                "latitude": latitude, "longitude": longitude,
                "forecast_days": days_ahead,
                "daily": ["temperature_2m_max", "precipitation_sum", "wind_speed_10m_max"],
                "timezone": "Africa/Johannesburg",
                "wind_speed_unit": "kmh",
            }
        )
        resp.raise_for_status()
        d = resp.json().get("daily", {})
        out = []
        for i, dt in enumerate(d.get("time", [])):
            prec = float((d.get("precipitation_sum")    or [0]*99)[i] or 0)
            wind = float((d.get("wind_speed_10m_max")   or [0]*99)[i] or 0)
            tmax = float((d.get("temperature_2m_max")   or [20]*99)[i] or 20)
            risk = round(
                min(prec/30, 1)*0.5 + min(wind/80, 1)*0.25 + max(0,(15-tmax)/15)*0.25, 3
            )
            out.append({
                "date":               dt,
                "precipitation_mm":   prec,
                "wind_speed_max_kmh": wind,
                "temp_max_c":         tmax,
                "rain_category":      _rain_cat(prec),
                "weather_risk_score": risk,
                "reminder_boost":     risk > 0.35,
                "action": "Send extra reminder" if risk > 0.35 else "Normal schedule",
            })
        return out
    except Exception as e:
        print(f"  [weather] forecast failed: {e}")
        return []
