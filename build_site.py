import json
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://api.bart.gov/api/etd.aspx"
# Public key listed by BART on its developer page. Follow BART's API license.
BART_API_KEY = "MW9S-E7SL-26DU-VV8V"
OUTPUT_FILE = Path("public/bart_data.json")


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def pipeline_execution():
    params = {
        "cmd": "etd",
        "orig": "ALL",
        "key": BART_API_KEY,
        "json": "y",
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("BART returned a response that was not valid JSON.") from exc

    root = payload.get("root")
    if not isinstance(root, dict):
        raise RuntimeError("BART response did not contain the expected 'root' object.")

    message = root.get("message")
    if message:
        raise RuntimeError(f"BART API reported an error: {message}")

    stations_raw = as_list(root.get("station"))
    if not stations_raw:
        raise RuntimeError("BART returned no station records; refusing to publish empty data.")

    transformed_records = []
    station_directory = {}

    for station in stations_raw:
        if not isinstance(station, dict):
            continue

        station_code = station.get("abbr")
        station_name = station.get("name")
        if not station_code or not station_name:
            continue

        station_directory[station_code] = station_name

        for etd in as_list(station.get("etd")):
            if not isinstance(etd, dict):
                continue
            destination = etd.get("destination", "Unknown")

            for estimate in as_list(etd.get("estimate")):
                if not isinstance(estimate, dict):
                    continue
                transformed_records.append({
                    "origin_code": station_code,
                    "origin_name": station_name,
                    "destination": destination,
                    "minutes": str(estimate.get("minutes", "Unknown")),
                    "direction": estimate.get("direction", "Unknown"),
                    "platform": estimate.get("platform", "N/A"),
                    "length": estimate.get("length", "N/A"),
                    "color": estimate.get("hexcolor", "#64748b"),
                })

    if not station_directory:
        raise RuntimeError("No valid stations were found; refusing to publish empty data.")

    api_date = root.get("date")
    api_time = root.get("time")
    if api_date and api_time:
        extracted_at = f"{api_date} {api_time}"
    else:
        extracted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    output_payload = {
        "metadata": {
            "last_updated": extracted_at,
            "total_records": len(transformed_records),
        },
        "stations": sorted(
            [{"code": code, "name": name} for code, name in station_directory.items()],
            key=lambda station: station["name"],
        ),
        "trains": transformed_records,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    temp_file.replace(OUTPUT_FILE)

    print(
        f"[SUCCESS] Wrote {OUTPUT_FILE}: "
        f"{len(station_directory)} stations and "
        f"{len(transformed_records)} train estimates."
    )


if __name__ == "__main__":
    pipeline_execution()
