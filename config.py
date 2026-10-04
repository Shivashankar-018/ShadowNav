"""ShadowNav settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

APP_NAME = "ShadowNav"
APP_TAGLINE = "Hyper-local heat-aware walking routes"

# Flask debug is for local student development only. Set SHADOWNAV_DEBUG=false
# in .env before using a non-debug configuration.
DEBUG = os.getenv("SHADOWNAV_DEBUG", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PUBLIC_DEMO = os.getenv("SHADOWNAV_PUBLIC_DEMO", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
HOST = "127.0.0.1"
PORT = 5000

# Default map view (Bengaluru city centre). Change these later for your city.
# These are map coordinates only. They are NOT temperature readings.
MAP_LAT = 12.9716
MAP_LON = 77.5946
MAP_ZOOM = 14

WEATHER_TIMEOUT_SECONDS = int(os.getenv("WEATHER_TIMEOUT_SECONDS", "10"))
WEATHER_CACHE_SECONDS = int(os.getenv("WEATHER_CACHE_SECONDS", "300"))

# Prototype heat grid (degrees of latitude/longitude around the map centre).
GRID_HALF_SIZE_DEG = 0.02
GRID_CELLS = 8
UHI_MAX_OFFSET_C = 2.0
UHI_RADIUS_KM = 2.0
