"""
JR East Real-time Train Tracking System - Main Application (Debug Version)
FastAPI server with SSE streaming
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

# Import our modules
from config import (
    ODPT_API_KEY, ODPT_BASE_URL, INITIAL_RAILWAYS, GTFS_DATA_PATH,
    SHAPEFILE_STATION_PATH, SHAPEFILE_RAIL_PATH,
    OVERRIDES_STATION_PATH, POLL_INTERVAL_SEC
)
from gtfs_loader import GTFSLoader
from shapefile_loader import ShapefileLoader
from station_mapper import StationMapper
from trip_matcher import TripMatcher, get_current_time_sec, get_service_day_start_epoch
from interpolator import Interpolator
from odpt_client import ODPTClient


app = FastAPI(title="JR East Real-time Train Tracker")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_methods=["*"],
    allow_headers=["*"]
)

# Global state
gtfs_loader = None
shapefile_loader = None
station_mapper = None
trip_matcher = None
interpolator = None
odpt_client = None
rail_paths = {}
live_snapshot = {
    "seq": 0,
    "vehicles": [],
    "timestamp": 0,
    "service_day_start_epoch": 0,
    "current_time_sec": 0
}


@app.on_event("startup")
async def startup():
    global gtfs_loader, shapefile_loader, station_mapper, trip_matcher, interpolator, odpt_client, rail_paths

    print("\n" + "="*60)
    print("JR East Real-time Train Tracking System (DEBUG MODE)")
    print("="*60 + "\n")

    # Check API key
    if not ODPT_API_KEY:
        print("[Startup] WARNING: ODPT_API_KEY not set!")
        print("[Startup] Set environment variable: export ODPT_API_KEY='your_key'")

    # Load GTFS data
    print("[Startup] Loading GTFS data...")
    gtfs_path = Path(__file__).parent / GTFS_DATA_PATH
    gtfs_loader = GTFSLoader(str(gtfs_path))

    # Load Shapefile data
    print("\n[Startup] Loading Shapefile data...")
    station_shp = Path(__file__).parent / SHAPEFILE_STATION_PATH
    rail_shp = Path(__file__).parent / SHAPEFILE_RAIL_PATH

    shapefile_loader = ShapefileLoader(
        str(station_shp),
        str(rail_shp)
    )
    shapefile_stations = shapefile_loader.load_stations()
    rail_paths = shapefile_loader.load_rail_sections()

    # Initialize ODPT client
    print("\n[Startup] Initializing ODPT client...")
    print(f"[Startup] Using ODPT base URL: {ODPT_BASE_URL}")
    odpt_client = ODPTClient(api_key=ODPT_API_KEY, railways=INITIAL_RAILWAYS, base_url=ODPT_BASE_URL)

    # Fetch ODPT stations
    print("[Startup] Fetching ODPT stations...")
    odpt_stations = {}
    for railway in INITIAL_RAILWAYS:
        try:
            stations = await odpt_client.get_stations(railway)
            odpt_stations.update(stations)
            print(f"[Startup] Fetched {len(stations)} stations for {railway}")
        except Exception as e:
            print(f"[Startup] Error fetching stations for {railway}: {e}")

    # Create station mapping
    print("\n[Startup] Creating station mapping...")
    overrides_path = Path(__file__).parent / OVERRIDES_STATION_PATH
    station_mapper = StationMapper(
        gtfs_loader,
        odpt_stations,
        overrides_path=str(overrides_path) if overrides_path.exists() else None
    )

    # Enhance with shapefile data
    if shapefile_stations:
        shapefile_loader.enhance_station_mapping(station_mapper)

    # Initialize matchers
    print("\n[Startup] Initializing trip matcher and interpolator...")
    trip_matcher = TripMatcher(gtfs_loader, station_mapper)
    interpolator = Interpolator(gtfs_loader, trip_matcher, station_mapper)

    # Start polling loop
    print("\n[Startup] Starting polling loop...")
    asyncio.create_task(poll_loop())

    print("\n" + "="*60)
    print("Startup complete! Server is ready.")
    print("="*60 + "\n")


async def poll_loop():
    """Poll ODPT API every 3 seconds"""
    global live_snapshot

    while True:
        try:
            # Fetch trains
            trains = await odpt_client.get_trains()

            current_time_sec = get_current_time_sec()
            service_start = get_service_day_start_epoch()

            vehicles = []
            match_success = 0
            match_failed = {}
            skip_no_stops = 0

            # DEBUG: Print sample train data on first loop
            if live_snapshot["seq"] == 0 and trains:
                print(f"\n{'='*60}")
                print("[DEBUG] Sample train data (first train):")
                print(f"{json.dumps(trains[0], indent=2)}")
                print(f"{'='*60}\n")

            for train in trains:
                if not train.get("from_stop") or not train.get("to_stop"):
                    skip_no_stops += 1
                    # DEBUG: Show skipped trains (first 3 only)
                    if live_snapshot["seq"] == 0 and skip_no_stops <= 3:
                        print(f"[DEBUG] SKIPPED (no stops):")
                        print(f"  trip_id: {train.get('trip_id')}")
                        print(f"  from_stop: {train.get('from_stop')}")
                        print(f"  to_stop: {train.get('to_stop')}\n")
                    continue

                position = interpolator.calculate_position(
                    train["trip_id"],
                    current_time_sec,
                    train["from_stop"],
                    train["to_stop"],
                    train["delay"]
                )

                if position:
                    vehicles.append({
                        "trip_id": train["trip_id"],
                        "lat": position["lat"],
                        "lng": position["lng"],
                        "progress": position["progress"],
                        "from_stop_id": train["from_stop"],
                        "to_stop_id": train["to_stop"],
                        "from_stop_gtfs": position.get("from_stop_gtfs"),
                        "to_stop_gtfs": position.get("to_stop_gtfs"),
                        "delay": train["delay"],
                        "status": "IN_TRANSIT_TO",
                        "interpolated": position["interpolated"],

                        # Debug info
                        "seg_dep_epoch": position["seg_dep_epoch"],
                        "seg_arr_epoch": position["seg_arr_epoch"],
                        "match_score": position["match_score"],
                        "match_reason": position["match_reason"],
                        "static_trip_id": position["static_trip_id"],
                        "rt_age_sec": 0
                    })

                    if position["interpolated"]:
                        match_success += 1
                else:
                    reason = "no-position"
                    match_failed[reason] = match_failed.get(reason, 0) + 1
                    # DEBUG: Show failed matches (first 3 only)
                    if live_snapshot["seq"] == 0 and match_failed.get(reason, 0) <= 3:
                        print(f"[DEBUG] POSITION FAILED:")
                        print(f"  trip_id: {train['trip_id']}")
                        print(f"  from_stop: {train['from_stop']}")
                        print(f"  to_stop: {train['to_stop']}\n")

            # Update snapshot
            live_snapshot = {
                "seq": live_snapshot["seq"] + 1,
                "timestamp": datetime.now().timestamp(),
                "service_day_start_epoch": service_start,
                "current_time_sec": current_time_sec,
                "vehicles": vehicles,
            }

            # Add rail paths only on first snapshot
            if live_snapshot["seq"] == 1:
                live_snapshot["rail_paths"] = rail_paths

            print(f"[poll_loop] Seq {live_snapshot['seq']} | "
                  f"Fetched {len(trains)} trains | "
                  f"Skipped: {skip_no_stops} | "
                  f"Matched: {match_success}/{len(trains) - skip_no_stops} | "
                  f"Failed: {dict(match_failed) if match_failed else 'None'}")

        except Exception as e:
            print(f"[poll_loop] Error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(POLL_INTERVAL_SEC)


@app.get("/api/trains/stream")
async def stream_trains():
    """SSE endpoint for real-time train data"""
    async def event_generator():
        last_seq = -1
        rail_sent = False

        while True:
            if live_snapshot["seq"] > last_seq:
                last_seq = live_snapshot["seq"]

                # Send snapshot
                snapshot = live_snapshot.copy()

                # Only send rail_paths once
                if rail_sent:
                    snapshot.pop("rail_paths", None)
                else:
                    rail_sent = True

                yield {
                    "event": "snapshot",
                    "data": json.dumps(snapshot)
                }

            await asyncio.sleep(1)

    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache"
        }
    )


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "gtfs_stops": len(gtfs_loader.stops) if gtfs_loader else 0,
        "gtfs_trips": len(gtfs_loader.stop_times) if gtfs_loader else 0,
        "odpt_stations": len(station_mapper.odpt_stations) if station_mapper else 0,
        "live_vehicles": len(live_snapshot["vehicles"]),
        "last_update": live_snapshot.get("timestamp", 0)
    }


@app.get("/debug/last-snapshot")
async def debug_snapshot():
    """Debug endpoint: return last snapshot"""
    return live_snapshot


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "JR East Real-time Train Tracker (DEBUG)",
        "version": "1.0.0",
        "endpoints": {
            "stream": "/api/trains/stream",
            "health": "/api/health",
            "debug": "/debug/last-snapshot"
        }
    }