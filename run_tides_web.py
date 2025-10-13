#!/usr/bin/env python3
"""Run the small tides web app for local testing."""
from src.tides_web.app import application
from wsgiref.simple_server import make_server

if __name__ == '__main__':
    print("Serving on http://127.0.0.1:8000")
    with make_server('127.0.0.1', 8000, application) as httpd:
        httpd.serve_forever()
