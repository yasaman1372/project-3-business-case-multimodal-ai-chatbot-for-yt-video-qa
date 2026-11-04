"""Vercel entry point: Vercel serves the `app` object from this file as a Python function.

All /api/* requests are routed here by vercel.json; the real app lives in app/app.py.
"""

import sys
from pathlib import Path

# Make the project root importable (for the `app` and `ingestion` packages)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.app import app  # noqa: E402,F401
