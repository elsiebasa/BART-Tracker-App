import json
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://api.bart.gov/api/etd.aspx"
STATION_URL = "https://api.bart.gov/api/stn.aspx"
BART_API_KEY = "MW9S-E7SL-26DU-VV8V"

# Written into public/ so the workflow can publish it.
OUTPUT_FILE = Path("public/bart_data.json")
SESSION = requests.Session()


def as_list(value):
    """Convert an API object or list into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def get_bart_data(url, params):
    """Fetch data from BART and handle API warnings."""
    response = SESSION.get(url, params=params, timeout=30)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("BART returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected BART API response.")

    root = payload.get("root")
    if not isinstance(root, dict):
        raise RuntimeError("BART response did not contain a root object.")

    message = root.get("message")
    if message:
        message_text = json.dumps(message, default=str).lower()

        # No estimates at one station should not stop the pipeline.
        if (
            params.get("cmd") == "etd"
            and "no data matched your criteria" in message_text
        ):
            print(f"[WARN] No estimates for {params.get('orig')}. Continuing.")
            return root

        raise RuntimeError(f"BART API reported an error: {message}")

    return root


def pipeline_execution():
    common_params = {"key": BART_API_KEY, "json": "y"}

    # STEP 1: Retrieve the complete station directory.
    station_root = get_bart_data(STATION_URL, {"cmd": "stns", **common_params})

    stations_container = station_root.get("stations")
    if not isinstance(stations_container, dict):
        stations_container = {}

    stations_raw = as_list(stations_container.get("station"))
    if not stations_raw:
        raise RuntimeError("BART returned no stations.")

    station_directory = {}
    transformed_records = []
    failed_stations = []

    # STEP 2 + 3: Keep every station, then fetch its departure estimates.
    for station in stations_raw:
        if not isinstance(station, dict):
            continue

        station_code = station.get("abbr")
        station_name = station.get("name")
        if not station_code or not station_name:
            continue

        station_code = str(station_code)
        station_name = str(station_name)
        station_directory[station_code] = station_name

        # One bad station should not abort the whole run.
        try:
            root = get_bart_data(
                API_URL,
                {"cmd": "etd", "orig": station_code, **common_params},
            )
        except (requests.RequestException, RuntimeError) as exc:
            print(f"[WARN] Skipping {station_code}: {exc}")
            failed_stations.append(station_code)
            continue

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
                        "minutes": str(estimate.get("minutes") or "Unknown"),
                        "direction": estimate.get("direction", "Unknown"),
                        "platform": estimate.get("platform", "N/A"),
                        "length": estimate.get("length", "N/A"),
                        "color": estimate.get("hexcolor", "#64748b"),
                    })

    if not station_directory:
        raise RuntimeError("No valid stations were found.")

    # If every request failed, don't publish an empty file over good data.
    if len(failed_stations) == len(station_directory):
        raise RuntimeError("Every station request failed. Not writing output.")

    # STEP 4: Build the JSON payload.
    output_payload = {
        "metadata": {
            "last_updated": datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
            "total_records": len(transformed_records),
        },
        "stations": sorted(
            [{"code": c, "name": n} for c, n in station_directory.items()],
            key=lambda s: s["name"].casefold(),
        ),
        "trains": transformed_records,
    }

    # STEP 5: Write to public/bart_data.json (folder is created if missing).
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