"""CLI wrapper that executes the top-level script safely using runpy.

This avoids modifying the original `make_tillamook_neg_lows.py` while letting
you run it as a module: `python -m tides.cli`.
"""
import runpy
import sys
from pathlib import Path

def main(argv=None):
    # Locate the top-level script relative to this file
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "make_tillamook_neg_lows.py"
    if not script.exists():
        print(f"Error: {script} not found.")
        return 2

    # Prepare sys.argv for the script
    if argv is None:
        argv = sys.argv[1:]
    sys.argv[:] = [str(script)] + list(argv)

    # Execute the script in a fresh __main__ context
    return runpy.run_path(str(script), run_name="__main__")

if __name__ == "__main__":
    main()
