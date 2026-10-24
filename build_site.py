import json
from datetime import datetime, timezone
from pathlib import Path
import requests
API_URL = "https://api.bart.gov/api/etd.aspx"
STATION_URL = "https://api.bart.gov/api/stn.aspx"
BART_API_KEY = "MW9S-E7SL-26DU-VV8V"
OUTPUT_FILE = Path("public/bart_data.json")
SESSION = requests.Session()
def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []
def get_bart_data(url, params):
    response = SESSION.get(url, params=params, timeout=30)
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "BART returned a response that was not valid JSON."
        ) from exc
    root = payload.get("root")
    if not isinstance(root, dict):
        raise RuntimeError(
            "BART response did not contain the expected root object."
        )
    message = root.get("message")
    if message:
        raise RuntimeError(f"BART API reported an error: {message}")
    return root
def pipeline_execution():
    common_params = {
        "key": BART_API_KEY,
        "json": "y",
    }
    # Retrieve the supported BART station list first.
    station_root = get_bart_data(
        STATION_URL,
        {"cmd": "stns", **common_params},
    )
    stations_raw = as_list(station_root.get("stations", {}).get("station"))
    if not stations_raw:
        raise RuntimeError("BART returned no stations.")
    station_directory = {}
    transformed_records = []
    # Request departure estimates one station at a time.
    for station in stations_raw:
        if not isinstance(station, dict):
            continue
        station_code = station.get("abbr")
        station_name = station.get("name")
        if not station_code or not station_name:
            continue
        station_directory[station_code] = station_name
        root = get_bart_data(
            API_URL,
            {
                "cmd": "etd",
                "orig": station_code,
                **common_params,
            },
        )
        for station_result in as_list(root.get("station")):
            if not isinstance(station_result, dict):
                continue
            for etd in as_list(station_result.get("etd")):
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
                        "minutes": str(
                            estimate.get("minutes", "Unknown")
                        ),
                        "direction": estimate.get("direction", "Unknown"),
                        "platform": estimate.get("platform", "N/A"),
                        "length": estimate.get("length", "N/A"),
                        "color": estimate.get("hexcolor", "#64748b"),
                    })
    if not station_directory:
        raise RuntimeError("No valid BART stations were found.")
    if not transformed_records:
        raise RuntimeError(
            "No departure estimates were returned. "
            "Refusing to publish an empty departure board."
        )
    output_payload = {
        "metadata": {
            "last_updated": datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
            "total_records": len(transformed_records),
        },
        "stations": sorted(
            [
                {"code": code, "name": name}
                for code, name in station_directory.items()
            ],
            key=lambda station: station["name"],
        ),
        "trains": transformed_records,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(output_payload, indent=2),
        encoding="utf-8",
    )
    temp_file.replace(OUTPUT_FILE)
    print(
        f"[SUCCESS] Wrote {OUTPUT_FILE}: "
        f"{len(station_directory)} stations and "
        f"{len(transformed_records)} train estimates."
    )
if __name__ == "__main__":
    pipeline_execution()