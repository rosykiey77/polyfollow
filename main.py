"""
Main entry point for Polymarket Bandar Tracker API.

This module initializes and starts the FastAPI application.
"""

from bandar_tracker import app


if __name__ == "__main__":
    print("Starting Polymarket Bandar Tracker API...")
    app.run("0.0.0.0:8000", reload=True)
