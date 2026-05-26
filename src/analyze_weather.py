from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "houston_hourly_weather_open_meteo_2022_2023.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "figures"


def fmt_num(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def svg_text(x: float, y: float, text: str, size: int = 18, weight: str = "400", fill: str = "#0f172a", anchor: str = "start") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="Inter, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(str(text))}</text>'


def write_svg(path: Path, body: str, width: int = 1100, height: int = 700) -> None:
    path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  {body}
</svg>
""",
        encoding="utf-8",
    )


def load_data() -> pd.DataFrame:
    if not RAW_PATH.exists():
        raise FileNotFoundError("Run src/fetch_weather.py first to create the raw hourly weather CSV.")
    df = pd.read_csv(RAW_PATH)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["datetime"].dt.to_period("M").astype(str)
    df["month_name"] = df["datetime"].dt.strftime("%b %Y")
    return df


def summarize(df: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    numeric_cols = [
        "temperature_f",
        "humidity_pct",
        "dew_point_f",
        "precipitation_in",
        "pressure_msl_hpa",
        "wind_speed_mph",
        "wind_gust_mph",
    ]
    missing = df[numeric_cols].isna().sum().rename_axis("column").reset_index(name="missing_values")
    daily = (
        df.groupby("date")
        .agg(
            mean_temp_f=("temperature_f", "mean"),
            max_temp_f=("temperature_f", "max"),
            min_temp_f=("temperature_f", "min"),
            total_precip_in=("precipitation_in", "sum"),
            mean_humidity_pct=("humidity_pct", "mean"),
            max_wind_gust_mph=("wind_gust_mph", "max"),
        )
        .reset_index()
    )
    monthly = (
        df.groupby("month")
        .agg(
            avg_temp_f=("temperature_f", "mean"),
            total_precip_in=("precipitation_in", "sum"),
            avg_humidity_pct=("humidity_pct", "mean"),
            avg_wind_speed_mph=("wind_speed_mph", "mean"),
            max_wind_gust_mph=("wind_gust_mph", "max"),
        )
        .reset_index()
    )
    corr = df[numeric_cols].corr().round(3)
    hourly_temp = df.groupby("hour")["temperature_f"].mean().reset_index(name="avg_temp_f")
    rain_hours = df[df["precipitation_in"] > 0]
    max_precip_day = daily.sort_values("total_precip_in", ascending=False).iloc[0]
    hottest_month = monthly.sort_values("avg_temp_f", ascending=False).iloc[0]
    hottest_hour = hourly_temp.sort_values("avg_temp_f", ascending=False).iloc[0]

    metrics = {
        "records": int(len(df)),
        "columns": int(df.shape[1]),
        "date_min": df["date"].min().strftime("%Y-%m-%d"),
        "date_max": df["date"].max().strftime("%Y-%m-%d"),
        "days": int(df["date"].nunique()),
        "mean_temperature_f": float(df["temperature_f"].mean()),
        "max_temperature_f": float(df["temperature_f"].max()),
        "min_temperature_f": float(df["temperature_f"].min()),
        "total_precipitation_in": float(df["precipitation_in"].sum()),
        "rain_hours": int(len(rain_hours)),
        "temp_dewpoint_corr": float(corr.loc["temperature_f", "dew_point_f"]),
        "temp_humidity_corr": float(corr.loc["temperature_f", "humidity_pct"]),
        "hottest_month": str(hottest_month["month"]),
        "hottest_month_avg_temp_f": float(hottest_month["avg_temp_f"]),
        "rainiest_day": max_precip_day["date"].strftime("%Y-%m-%d"),
        "rainiest_day_precip_in": float(max_precip_day["total_precip_in"]),
        "hottest_hour": int(hottest_hour["hour"]),
        "hottest_hour_avg_temp_f": float(hottest_hour["avg_temp_f"]),
    }
    return {
        "missing": missing,
        "daily": daily,
        "monthly": monthly,
        "corr": corr.reset_index().rename(columns={"index": "variable"}),
        "hourly_temp": hourly_temp,
        "metrics": metrics,
    }


def make_kpi_summary(metrics: dict) -> None:
    cards = [
        ("Hourly records", f"{metrics['records']:,}", "#111827"),
        ("Study days", f"{metrics['days']:,}", "#0f766e"),
        ("Avg temp", f"{metrics['mean_temperature_f']:.1f}°F", "#c2410c"),
        ("Rain hours", f"{metrics['rain_hours']:,}", "#2563eb"),
    ]
    body = [
        svg_text(45, 62, "Houston Weather EDA", 32, "850"),
        svg_text(45, 96, f"Historical hourly weather near KIAH | {metrics['date_min']} to {metrics['date_max']}", 16, "400", "#64748b"),
    ]
    for i, (label, value, color) in enumerate(cards):
        x = 45 + i * 260
        body.append(f'<rect x="{x}" y="150" width="230" height="150" rx="14" fill="white" stroke="#e2e8f0"/>')
        body.append(f'<rect x="{x}" y="150" width="230" height="9" rx="4" fill="{color}"/>')
        body.append(svg_text(x + 22, 212, value, 31, "850"))
        body.append(svg_text(x + 22, 252, label, 16, "650", "#64748b"))
    write_svg(FIGURES_DIR / "kpi_summary.svg", "\n  ".join(body), 1100, 360)


def make_monthly_temp_chart(monthly: pd.DataFrame) -> None:
    width, height = 1100, 650
    left, top = 90, 115
    plot_w, plot_h = 920, 360
    max_v, min_v = monthly["avg_temp_f"].max(), monthly["avg_temp_f"].min()
    body = [
        svg_text(45, 58, "Monthly Average Temperature", 30, "850"),
        svg_text(45, 88, "Houston temperatures rise into summer and fall into winter", 16, "400", "#64748b"),
    ]
    bar_w = plot_w / len(monthly)
    for i, row in enumerate(monthly.itertuples(index=False)):
        h = ((row.avg_temp_f - min_v) / (max_v - min_v)) * 280 + 55
        x = left + i * bar_w
        y = top + plot_h - h
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 7:.1f}" height="{h:.1f}" rx="8" fill="#c2410c" opacity="0.86"/>')
        if i % 2 == 0:
            body.append(svg_text(x + bar_w / 2, top + plot_h + 35, row.month, 12, "600", "#64748b", "middle"))
    body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#94a3b8" stroke-width="2"/>')
    body.append(svg_text(left, top + plot_h + 75, f"Lowest monthly avg: {min_v:.1f}°F", 14, "700", "#334155"))
    body.append(svg_text(left + plot_w, top + plot_h + 75, f"Highest monthly avg: {max_v:.1f}°F", 14, "700", "#334155", "end"))
    write_svg(FIGURES_DIR / "monthly_temperature.svg", "\n  ".join(body), width, height)


def make_precip_chart(monthly: pd.DataFrame) -> None:
    width, height = 1100, 620
    left, top = 90, 120
    plot_w, plot_h = 920, 330
    max_v = monthly["total_precip_in"].max()
    body = [
        svg_text(45, 58, "Monthly Precipitation Totals", 30, "850"),
        svg_text(45, 88, "Rainfall is concentrated in a smaller number of wetter periods", 16, "400", "#64748b"),
    ]
    bar_w = plot_w / len(monthly)
    for i, row in enumerate(monthly.itertuples(index=False)):
        h = (row.total_precip_in / max_v) * plot_h if max_v else 0
        x = left + i * bar_w
        y = top + plot_h - h
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 7:.1f}" height="{h:.1f}" rx="8" fill="#2563eb" opacity="0.82"/>')
        if i % 2 == 0:
            body.append(svg_text(x + bar_w / 2, top + plot_h + 35, row.month, 12, "600", "#64748b", "middle"))
    body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#94a3b8" stroke-width="2"/>')
    write_svg(FIGURES_DIR / "monthly_precipitation.svg", "\n  ".join(body), width, height)


def make_correlation_heatmap(corr: pd.DataFrame) -> None:
    variables = [c for c in corr.columns if c != "variable"]
    labels = {
        "temperature_f": "Temp",
        "humidity_pct": "Humidity",
        "dew_point_f": "Dew Point",
        "precipitation_in": "Precip",
        "pressure_msl_hpa": "Pressure",
        "wind_speed_mph": "Wind",
        "wind_gust_mph": "Gust",
    }
    width, height = 960, 880
    cell = 86
    left, top = 230, 135
    body = [
        svg_text(45, 58, "Correlation Heatmap", 30, "850"),
        svg_text(45, 88, "Temperature is strongly related to dew point and negatively related to humidity", 16, "400", "#64748b"),
    ]
    data = corr.set_index("variable")
    for i, row_var in enumerate(variables):
        body.append(svg_text(left - 18, top + i * cell + 52, labels[row_var], 14, "700", "#334155", "end"))
        body.append(svg_text(left + i * cell + 43, top - 18, labels[row_var], 14, "700", "#334155", "middle"))
        for j, col_var in enumerate(variables):
            val = float(data.loc[row_var, col_var])
            if val >= 0:
                opacity = min(1, 0.18 + abs(val) * 0.78)
                color = f"rgba(194,65,12,{opacity:.2f})"
            else:
                opacity = min(1, 0.18 + abs(val) * 0.78)
                color = f"rgba(37,99,235,{opacity:.2f})"
            x = left + j * cell
            y = top + i * cell
            body.append(f'<rect x="{x}" y="{y}" width="{cell - 5}" height="{cell - 5}" rx="10" fill="{color}"/>')
            body.append(svg_text(x + (cell - 5) / 2, y + 50, f"{val:.2f}", 15, "800", "#111827", "middle"))
    write_svg(FIGURES_DIR / "correlation_heatmap.svg", "\n  ".join(body), width, height)


def make_hourly_temp_chart(hourly: pd.DataFrame) -> None:
    width, height = 1050, 600
    left, top = 85, 115
    plot_w, plot_h = 870, 330
    min_v, max_v = hourly["avg_temp_f"].min(), hourly["avg_temp_f"].max()
    points = []
    for row in hourly.itertuples(index=False):
        x = left + (row.hour / 23) * plot_w
        y = top + plot_h - ((row.avg_temp_f - min_v) / (max_v - min_v)) * plot_h
        points.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    body = [
        svg_text(45, 58, "Average Temperature By Hour", 30, "850"),
        svg_text(45, 88, "Hourly averages show the daily warming cycle", 16, "400", "#64748b"),
        f'<polyline points="{poly}" fill="none" stroke="#c2410c" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    for x, y in points:
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="white" stroke="#c2410c" stroke-width="3"/>')
    body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#94a3b8" stroke-width="2"/>')
    for h in range(0, 24, 3):
        x = left + (h / 23) * plot_w
        body.append(svg_text(x, top + plot_h + 35, h, 13, "700", "#64748b", "middle"))
    write_svg(FIGURES_DIR / "hourly_temperature_cycle.svg", "\n  ".join(body), width, height)


def export_outputs(df: pd.DataFrame, summaries: dict[str, pd.DataFrame | dict]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    summaries["daily"].to_csv(PROCESSED_DIR / "daily_weather_summary.csv", index=False)
    summaries["monthly"].to_csv(PROCESSED_DIR / "monthly_weather_summary.csv", index=False)
    summaries["corr"].to_csv(PROCESSED_DIR / "weather_correlations.csv", index=False)
    summaries["missing"].to_csv(PROCESSED_DIR / "missing_values.csv", index=False)
    summaries["hourly_temp"].to_csv(PROCESSED_DIR / "hourly_temperature_summary.csv", index=False)
    (PROCESSED_DIR / "metrics.json").write_text(json.dumps(summaries["metrics"], indent=2), encoding="utf-8")

    make_kpi_summary(summaries["metrics"])
    make_monthly_temp_chart(summaries["monthly"])
    make_precip_chart(summaries["monthly"])
    make_correlation_heatmap(summaries["corr"])
    make_hourly_temp_chart(summaries["hourly_temp"])


def main() -> None:
    df = load_data()
    summaries = summarize(df)
    export_outputs(df, summaries)
    print(json.dumps(summaries["metrics"], indent=2))


if __name__ == "__main__":
    main()

