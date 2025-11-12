"""
Configuration for JR East Real-time Train Tracking System
"""
import os

# ODPT API
ODPT_API_KEY = os.getenv("ODPT_API_KEY", "")

# Polling settings
POLL_INTERVAL_SEC = 3
HEARTBEAT_INTERVAL_SEC = 1

# Matching settings
STATION_MATCH_DISTANCE_M = [300, 500]
MAX_DELAY_SEC = 600
TRIP_CACHE_TTL_SEC = 900

# Target railways
INITIAL_RAILWAYS = [
    "odpt.Railway:JR-East.ChuoRapid",
    "odpt.Railway:JR-East.Chuo",
    "odpt.Railway:JR-East.Yamanote"
]

# Data paths (relative to backend directory)
GTFS_DATA_PATH = "../train_json"
SHAPEFILE_STATION_PATH = "../N02-05_GML/N02-05_v1.0/N02-05-g_Station.shp"
SHAPEFILE_RAIL_PATH = "../N02-05_GML/N02-05_v1.0/N02-05-g_RailroadSection.shp"
OVERRIDES_STATION_PATH = "./data/config/overrides.stations.json"

# Server settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
