from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_PATH = RAW_DIR / "houston_hourly_weather_open_meteo_2022_2023.csv"
METADATA_PATH = RAW_DIR / "source_metadata.json"


def fetch_open_meteo() -> pd.DataFrame:
    params = {
        "latitude": 29.9844,
        "longitude": -95.3414,
        "start_date": "2022-01-01",
        "end_date": "2023-01-31",
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "dew_point_2m",
                "precipitation",
                "pressure_msl",
                "wind_speed_10m",
                "wind_gusts_10m",
                "weather_code",
            ]
        ),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/Chicago",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))

    hourly = payload["hourly"]
    df = pd.DataFrame(hourly)
    df = df.rename(
        columns={
            "time": "datetime",
            "temperature_2m": "temperature_f",
            "relative_humidity_2m": "humidity_pct",
            "dew_point_2m": "dew_point_f",
            "precipitation": "precipitation_in",
            "pressure_msl": "pressure_msl_hpa",
            "wind_speed_10m": "wind_speed_mph",
            "wind_gusts_10m": "wind_gust_mph",
        }
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date.astype(str)
    df["hour"] = df["datetime"].dt.hour

    metadata = {
        "source": "Open-Meteo Historical Weather API",
        "source_url": url,
        "latitude": params["latitude"],
        "longitude": params["longitude"],
        "study_start": params["start_date"],
        "study_end": params["end_date"],
        "timezone": params["timezone"],
        "note": "Reproducible portfolio weather EDA project using Open-Meteo historical hourly data.",
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_PATH, index=False)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return df


if __name__ == "__main__":
    data = fetch_open_meteo()
    print(data.shape)
    print(RAW_PATH)
