#!/usr/bin/env python3
"""
log_odds.py

Fetches current weather and river gauge data, computes catfish-odds score,
and appends to a JSON log file.
Supports ZIP code lookup for weather station location.
If automatic USGS gauge mapping by ZIP is not implemented, defaults to a Philadelphia gauge.
"""

import os
import requests
import datetime
import json
import math
import sys
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Configuration ===
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', './data/odds_log.json')
ZIP_CODE = os.getenv('ZIP_CODE', '19130')
USER_AGENT = os.getenv('USER_AGENT', 'CatfishOddsLogger/1.0 (youremail@example.com)')

# Default USGS gauge site for Philadelphia (Schuylkill River)
USGS_URL = "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=01473730&parameterCd=00065"

KEEP_HOURS = 30 * 24
STABILITY_THRESHOLD = 2.0
STABILITY_DAYS = 4

def geocode_zip(zip_code):
    """Return (lat, lon) for given ZIP code using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {'postalcode': zip_code, 'country': 'USA', 'format': 'json', 'limit': 1}
    headers = {'User-Agent': USER_AGENT}
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise RuntimeError(f"No geocode results for ZIP {zip_code}")
    return float(data[0]['lat']), float(data[0]['lon'])

def fetch_json(url, headers=None, params=None, timeout=15):
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def get_weather_station(lat, lon):
    """Get the nearest weather.gov station for coordinates."""
    headers = {"User-Agent": USER_AGENT}
    pts_url = f"https://api.weather.gov/points/{lat},{lon}"
    data = fetch_json(pts_url, headers=headers)
    stations_url = data["properties"]["observationStations"]
    stations_data = fetch_json(stations_url, headers=headers)
    return stations_data["features"][0]["properties"]["stationIdentifier"]

def fetch_latest_obs(station_id):
    headers = {"User-Agent": USER_AGENT}
    url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    data = fetch_json(url, headers=headers)
    props = data["properties"]
    p_now = props["barometricPressure"]["value"] / 100.0
    T_now = props["temperature"]["value"] * 9/5 + 32
    return p_now, T_now

def fetch_prev_pressure(station_id):
    headers = {"User-Agent": USER_AGENT}
    url = f"https://api.weather.gov/stations/{station_id}/observations"
    data = fetch_json(url, headers=headers, params={'limit':48})
    past = data["features"][1]["properties"]["barometricPressure"]["value"] / 100.0
    return past

def fetch_gauge():
    """Fetch the USGS gauge height (river level)."""
    data = fetch_json(USGS_URL)
    val = data["value"]["timeSeries"][0]["values"][0]["value"][0]["value"]
    return float(val)

def compute_barometric_stability_local(entries):
    if not entries:
        return 0.0
    pressures_by_date = defaultdict(list)
    for e in entries:
        t = e.get("time")
        p = e.get("p_now")
        try:
            dt = datetime.datetime.fromisoformat(t.replace("Z","+00:00"))
        except:
            continue
        date_str = dt.date().isoformat()
        pressures_by_date[date_str].append(p)
    now = datetime.datetime.now(datetime.timezone.utc).date()
    past_dates = [(now - datetime.timedelta(days=i)).isoformat() for i in range(1, STABILITY_DAYS+1)]
    avgs = []
    for d in reversed(past_dates):
        vals = pressures_by_date.get(d)
        avgs.append(sum(vals)/len(vals) if vals else None)
    stable = 0
    for i in range(1, len(avgs)):
        if avgs[i] is not None and avgs[i-1] is not None and abs(avgs[i]-avgs[i-1])<=STABILITY_THRESHOLD:
            stable += 1
    return stable/STABILITY_DAYS

def compute_score(p_now, p_prev, T_now, L_now, D):
    P = max(0,1-abs(p_now-p_prev)/10)
    L = max(0,1-abs(L_now-7)/5)
    T = max(0,1-abs(T_now-75)/15)
    S = 0.30*D + 0.25*P + 0.20*L + 0.25*T
    return round(S*100,1)

def load_existing_data(path):
    try:
        if os.path.exists(path):
            with open(path,'r') as f:
                data = json.load(f)
                return data if isinstance(data,list) else []
    except:
        pass
    return []

def save_data(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp,'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def main():
    # 1. Geocode ZIP
    try:
        lat, lon = geocode_zip(ZIP_CODE)
    except Exception as e:
        print(f"[ERROR] Geocode failed: {e}", file=sys.stderr)
        return

    # 2. Determine weather station
    try:
        station = get_weather_station(lat, lon)
        p_now, T_now = fetch_latest_obs(station)
        p_prev = fetch_prev_pressure(station)
        L_now = fetch_gauge()
    except Exception as e:
        print(f"[ERROR] Data fetch failed: {e}", file=sys.stderr)
        return

    # 3. Log management
    data = load_existing_data(LOG_FILE_PATH)
    D = compute_barometric_stability_local(data)
    pct = compute_score(p_now, p_prev, T_now, L_now, D)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    entry = {"time": now, "p_now": p_now, "T_now": T_now, "L_now": L_now, "score": pct}
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=KEEP_HOURS)
    data = [e for e in data if datetime.datetime.fromisoformat(e["time"].replace("Z","+00:00")) >= cutoff]
    if data and datetime.datetime.fromisoformat(data[-1]["time"].replace("Z","+00:00")).hour == datetime.datetime.now(datetime.timezone.utc).hour:
        data[-1] = entry
    else:
        data.append(entry)
    save_data(LOG_FILE_PATH, data)
    print(f"[{now}] Logged odds: {pct}%")

if __name__ == "__main__":
    main()