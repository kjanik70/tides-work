#!/usr/bin/env python3
"""
Fetch NOAA tide predictions for NORTH JETTY (station 9437585) between
2025-10-11 and 2026-10-11, find low tides < 0.0 ft that occur between
08:00 and 19:00 local time, and write an ICS file with 30-minute events.

Produces: tillamook_negative_lows_20251011-20261011.ics
"""

import datetime
import sys
import time
import json
import urllib.request
import urllib.parse
from zoneinfo import ZoneInfo

# This script uses only the Python standard library (urllib, json, zoneinfo).

STATION = "9437585"  # NORTH JETTY, TILLAMOOK BAY
BEGIN = "20251011"
END   = "20261011"
# NOAA datagetter: product=predictions, interval=hilo (high/low)
BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

params = {
    "product": "predictions",
    "begin_date": BEGIN,
    "end_date": END,
    "station": STATION,
    "time_zone": "lst_ldt",   # local standard/daylight time
    "units": "english",
    "datum": "MLLW",
    "interval": "hilo",       # high/low entries only
    "format": "json"
}

def fetch_predictions():
    # Build URL with encoded query parameters
    q = urllib.parse.urlencode(params)
    url = BASE_URL + "?" + q
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = resp.read()
        # NOAA returns UTF-8 JSON
        return json.loads(body.decode("utf-8"))

def is_between_local_hours(dt_local, start_h=8, end_h=19):
    """Return True if dt_local hour is within [start_h, end_h] inclusive."""
    h = dt_local.hour
    return (h >= start_h) and (h <= end_h)

def make_ics(events, out_path):
    # events: list of dicts with keys: dt (aware datetime), height (float)
    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("PRODID:-//ChatGPT//Tillamook Negative Low Tides//EN")
    lines.append("VERSION:2.0")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    # VTIMEZONE (simple block for America/Los_Angeles)
    lines.extend([
        "BEGIN:VTIMEZONE",
        "TZID:America/Los_Angeles",
        "X-LIC-LOCATION:America/Los_Angeles",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:-0700",
        "TZOFFSETTO:-0800",
        "TZNAME:PST",
        "DTSTART:19701101T020000",
        "END:STANDARD",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:-0800",
        "TZOFFSETTO:-0700",
        "TZNAME:PDT",
        "DTSTART:19700308T020000",
        "END:DAYLIGHT",
        "END:VTIMEZONE",
    ])
    now_utc = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for i, ev in enumerate(events, start=1):
        dt_local = ev["dt"]  # aware datetime in local tz
        dt_end = dt_local + datetime.timedelta(minutes=30)
        uid = f"tillamook-neg-low-{i}@generated"
        summary = f"Low tide {ev['height']:.2f} ft — Barview / North Jetty (Tillamook Bay)"
        description = f"Predicted low tide of {ev['height']:.2f} ft (NOAA predictions). Station 9437585."
        # format datetimes as YYYYMMDDTHHMMSS
        dtstart = dt_local.strftime("%Y%m%dT%H%M%S")
        dtend   = dt_end.strftime("%Y%m%dT%H%M%S")
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTAMP:{now_utc}")
        lines.append(f"DTSTART;TZID=America/Los_Angeles:{dtstart}")
        lines.append(f"DTEND;TZID=America/Los_Angeles:{dtend}")
        lines.append(f"SUMMARY:{summary}")
        lines.append(f"DESCRIPTION:{description}")
        lines.append("LOCATION:Barview / North Jetty, Tillamook Bay, OR")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Wrote", out_path)

def main():
    print("Requesting NOAA predictions for station", STATION)
    data = fetch_predictions()
    if "predictions" not in data:
        print("Unexpected response shape:", data)
        sys.exit(1)
    predictions = data["predictions"]
    # predictions are timezone-aware strings per time_zone=lst_ldt (e.g., "2025-11-03 16:45")
    events = []
    # We'll treat times as local; convert to tz-aware datetimes in America/Los_Angeles
    tz_local = ZoneInfo("America/Los_Angeles")
    for p in predictions:
        t_str = p["t"]    # e.g., "2025-11-03 16:45"
        val   = float(p["v"])  # height in feet (english units)
        typ   = p.get("type", "").lower()  # 'H' or 'L'
        if typ != "l":
            continue
        # parse time (NOAA returns 'YYYY-MM-DD HH:MM') and attach tz
        try:
            dt_naive = datetime.datetime.strptime(t_str, "%Y-%m-%d %H:%M")
        except ValueError:
            # Fallback to generic parser-like attempt for unexpected formats
            # (keep original behavior tolerant)
            dt_naive = datetime.datetime.fromisoformat(t_str)
        dt_local = dt_naive.replace(tzinfo=tz_local)
        # filter hours and negative height
        if val < 0.0 and is_between_local_hours(dt_local, 8, 19):
            events.append({"dt": dt_local, "height": val, "time_str": t_str})
    if not events:
        print("No matching negative low tides found in the range.")
    else:
        out_path = "tillamook_negative_lows_20251011-20261011.ics"
        make_ics(events, out_path)
        print(f"{len(events)} events written. Import {out_path} into Google Calendar.")
        for e in events:
            print(e["dt"].strftime("%Y-%m-%d %H:%M %Z"), f"{e['height']:.2f} ft")

if __name__ == "__main__":
    main()
