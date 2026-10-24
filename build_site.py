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
    """Normalize the BART API's sometimes-single, sometimes-list fields."""
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
        # Serializing the whole message handles dicts, lists, and strings.
        # BART's warning may be wrapped differently across responses.
        message_text = json.dumps(message, default=str).lower()

        if "no data matched your criteria" in message_text:
            print(
                "[WARN] BART returned no data for "
                f"cmd={params.get('cmd')}, orig={params.get('orig', 'N/A')}; "
                "continuing."
            )
            # An empty ETD response is expected for some stations.
            # Return the root so the station remains in the directory.
            return root

        raise RuntimeError(f"BART API reported an error: {message}")

    return root


def pipeline_execution():
    common_params = {
        "key": BART_API_KEY,
        "json": "y",
    }

    # Fetch the complete station directory first. Stations are retained even
    # when BART has no live departure estimates for them.
    station_root = get_bart_data(
        STATION_URL,
        {"cmd": "stns", **common_params},
    )
    stations_container = station_root.get("stations")
    if not isinstance(stations_container, dict):
        stations_container = {}
    stations_raw = as_list(stations_container.get("station"))
    if not stations_raw:
        raise RuntimeError(
            "BART returned no stations. Check the station-list API response."
        )

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
