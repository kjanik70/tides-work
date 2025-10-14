"""A tiny WSGI web application to search NOAA tide predictions and show negative low tides.

Uses only the Python standard library so you can run it without installing extra packages.
"""
from urllib import request, parse
import json
import datetime
from zoneinfo import ZoneInfo
import html
from pathlib import Path
import calendar
from collections import defaultdict

MDAPI_STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
DATAGETTER_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def fetch_stations():
    """Fetch stations list from NOAA MDAPI. Returns a list of station dicts.
    This can be large; the caller may want to cache it.
    """
    with request.urlopen(MDAPI_STATIONS_URL, timeout=30) as resp:
        data = json.load(resp)
    return data.get("stations", [])


def fetch_predictions(station, begin_date, end_date):
    params = {
        "product": "predictions",
        "begin_date": begin_date,
        "end_date": end_date,
        "station": station,
        "time_zone": "lst_ldt",
        "units": "english",
        "datum": "MLLW",
        "interval": "hilo",
        "format": "json",
    }
    q = parse.urlencode(params)
    url = DATAGETTER_URL + "?" + q
    with request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def filter_low_tides(predictions, start_hour, end_hour, min_level):
    """Return list of events (dt, height) that are low tides below min_level and within hours.

    predictions: list of dicts as returned by NOAA datagetter 'predictions'
    start_hour/end_hour: ints 0-23
    min_level: float (e.g., 0.0)
    """
    tz_local = ZoneInfo("America/Los_Angeles")
    events = []
    for p in predictions:
        typ = p.get("type", "").lower()
        if typ != "l":
            continue
        try:
            val = float(p.get("v", "nan"))
        except Exception:
            continue
        t_str = p.get("t")
        if not t_str:
            continue
        try:
            dt_naive = datetime.datetime.strptime(t_str, "%Y-%m-%d %H:%M")
        except ValueError:
            # fallback for unexpected formats
            try:
                dt_naive = datetime.datetime.fromisoformat(t_str)
            except Exception:
                continue
        dt_local = dt_naive.replace(tzinfo=tz_local)
        h = dt_local.hour
        if val < min_level and (h >= start_hour and h <= end_hour):
            events.append({"dt": dt_local, "height": val, "t_str": t_str})
    return events


TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def render_template(name, **context):
    path = TEMPLATES_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        tmpl = f.read()
    # simple {{ var }} replacement for a few known fields
    # Provide a minimal templating: replace {{key}} with html-escaped str(value)
    # but allow raw insertion for known HTML fragments (options, table rows, errors)
    raw_keys = {
        "stations_markup",
        "table_rows",
        "stations_error",
        "stations_json",
        "calendar_markup",
    }
    out = tmpl
    for k, v in context.items():
        placeholder = "{{" + k + "}}"
        if k in raw_keys:
            out = out.replace(placeholder, str(v))
        else:
            out = out.replace(placeholder, html.escape(str(v)))
    return out


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if path == "/":
        # Show form; fetch stations (could be cached in memory)
        try:
            stations = fetch_stations()
        except Exception as e:
            stations = []
            stations_error = str(e)
        else:
            stations_error = ""

        # Provide stations markup and embed stations JSON for client-side interactions
        stations_markup = build_stations_options(stations)
        stations_json = json.dumps(stations)
        stations_count = len(stations)
        # small preview to use as a safe fallback in the browser if the full JSON is problematic
        stations_preview = json.dumps(stations[:200])
        body = render_template(
            "index.html",
            stations_markup=stations_markup,
            stations_error=stations_error,
            stations_json=stations_json,
            stations_count=stations_count,
            stations_preview=stations_preview,
        )
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [body.encode("utf-8")]

    if path == "/results" and method in ("POST", "GET"):
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except Exception:
            size = 0
        body_bytes = environ['wsgi.input'].read(size) if size else b""
        params = parse.parse_qs(body_bytes.decode('utf-8')) if size else parse.parse_qs(environ.get('QUERY_STRING', ''))

        station = params.get('station', [None])[0]
        begin = params.get('begin_date', [None])[0]
        end = params.get('end_date', [None])[0]
        start_time = params.get('start_time', ['08:00'])[0]
        end_time = params.get('end_time', ['19:00'])[0]
        min_level = float(params.get('min_level', ["0"])[0])

        if not station or not begin or not end:
            start_response('400 Bad Request', [('Content-Type', 'text/plain')])
            return [b'Missing station, begin_date or end_date']

        # Convert start_time/end_time to hours
        sh = int(start_time.split(':')[0])
        eh = int(end_time.split(':')[0])

        try:
            begin_date = datetime.date.fromisoformat(begin)
            end_date = datetime.date.fromisoformat(end)
        except ValueError:
            start_response('400 Bad Request', [('Content-Type', 'text/plain')])
            return [b'Invalid begin_date or end_date; expected YYYY-MM-DD']

        if end_date < begin_date:
            start_response('400 Bad Request', [('Content-Type', 'text/plain')])
            return [b'end_date must be on or after begin_date']

        try:
            data = fetch_predictions(station, begin, end)
            predictions = data.get('predictions', [])
            events = filter_low_tides(predictions, sh, eh, min_level)
        except Exception as e:
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [f'Error fetching predictions: {e}'.encode('utf-8')]

        calendar_markup = build_calendar_markup(events, begin_date, end_date)

        body = render_template('results.html', calendar_markup=calendar_markup, station=station, begin=begin, end=end)
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
        return [body.encode('utf-8')]

    # Serve stations as a separate JSON endpoint to avoid embedding a very large
    # JSON blob into the HTML page (avoid quoting/escaping issues in templates).
    if path == '/stations.json' and method == 'GET':
        try:
            stations = fetch_stations()
            body = json.dumps({'stations': stations})
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8')])
            return [body.encode('utf-8')]
        except Exception as e:
            start_response('500 Internal Server Error', [('Content-Type', 'application/json; charset=utf-8')])
            return [json.dumps({'error': str(e)}).encode('utf-8')]

    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'Not found']


def build_stations_options(stations):
    # Build HTML <option> elements: show id - name (state)
    out = []
    for s in stations:
        sid = s.get('id') or s.get('stationId') or s.get('station')
        name = s.get('name') or s.get('stationName') or ''
        state = s.get('state') or ''
        if not sid:
            continue
        label = f"{sid} — {name} {('('+state+')') if state else ''}"
        out.append(f"<option value=\"{html.escape(sid)}\">{html.escape(label)}</option>")
    return '\n'.join(out)


def build_calendar_markup(events, begin_date, end_date):
    """Return HTML representing monthly calendars highlighting matching events."""
    events_by_date = defaultdict(list)
    for ev in events:
        dt = ev.get("dt")
        if not dt:
            continue
        events_by_date[dt.date()].append(ev)

    current = begin_date.replace(day=1)
    last_month = end_date.replace(day=1)
    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    month_sections = []
    day_headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    while current <= last_month:
        year, month = current.year, current.month
        weeks = cal.monthdatescalendar(year, month)
        week_rows = []
        for week in weeks:
            cells = []
            for day in week:
                classes = ["day"]
                if day.month != month:
                    classes.append("other-month")
                cell_body = []
                if begin_date <= day <= end_date and day in events_by_date:
                    classes.append("has-event")
                    entries = []
                    for ev in events_by_date[day]:
                        ev_dt = ev.get("dt")
                        ev_height = ev.get("height")
                        if not isinstance(ev_height, (int, float)) or not ev_dt:
                            continue
                        time_label = ev_dt.strftime("%I:%M %p").lstrip("0")
                        entries.append(f"{time_label}  {ev_height:.2f} ft")
                    if entries:
                        cell_body.append(f"<div class=\"events\">{'<br>'.join(entries)}</div>")
                cells.append(
                    f"<td class=\"{' '.join(classes)}\">"
                    f"<div class=\"date-label\">{day.day}</div>"
                    f"{''.join(cell_body)}"
                    "</td>"
                )
            week_rows.append("<tr>" + "".join(cells) + "</tr>")
        month_sections.append(
            f"<section class=\"month\">"
            f"<h2>{calendar.month_name[month]} {year}</h2>"
            f"<table class=\"calendar\">"
            f"<thead><tr>{''.join(f'<th>{name}</th>' for name in day_headers)}</tr></thead>"
            f"<tbody>{''.join(week_rows)}</tbody>"
            "</table>"
            "</section>"
        )
        if month == 12:
            current = datetime.date(year + 1, 1, 1)
        else:
            current = datetime.date(year, month + 1, 1)

    if not month_sections:
        return "<p>No matching events found.</p>"
    return "\n".join(month_sections)
