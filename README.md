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
