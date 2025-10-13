Tides workspace

This project contains utilities around `make_tillamook_neg_lows.py`.

Quickstart (Linux / bash):

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the original script directly:

```bash
python make_tillamook_neg_lows.py
```

4. Or run via the package entrypoint (uses the repo copy of the script):

```bash
python -m tides.cli
```

Run tests:

```bash
pytest -q
```

Notes:
- The package wrapper `tides.cli` uses runpy to execute the top-level script so you don't need to refactor the script to a module immediately.
- If you want a proper importable API, consider moving logic from the script into `src/tides/` module functions.

Web app
-------

There is a tiny web app in `src/tides_web` that provides a simple UI to query the NOAA API and show low tides.

Run locally:

```bash
python3 run_tides_web.py
# then open http://127.0.0.1:8000 in your browser
```

The app uses only the standard library (urllib, wsgiref, zoneinfo) and reads templates from `templates/`.
