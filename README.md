Tides Web App
=============

This repository provides a minimal web interface for exploring negative low tides via the NOAA tides and currents API. The app runs entirely on the Python standard library and renders HTML templates from the `templates/` directory.

Getting Started
---------------

1. (Optional) Create a virtual environment and activate it:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install any project dependencies (mainly for local tooling):
   ```bash
   pip install -r requirements.txt
   ```
3. Start the web app:
   ```bash
   python3 run_tides_web.py
   ```
4. Open the browser at [http://127.0.0.1:8000](http://127.0.0.1:8000) and use the interface to select a station, choose a date range, and review the calendar results.

Notes
-----

- The server binds to `127.0.0.1:8000` and will attempt to free the port automatically if another local process is using it.
- Station metadata is fetched from NOAA at runtime; if the network is unavailable the app falls back to a bundled snapshot embedded in the page.
