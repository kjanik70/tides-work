def test_package_importable():
    import sys
    from pathlib import Path
    # Add project root to sys.path so tests can import src package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import tides
    assert hasattr(tides, "cli")
