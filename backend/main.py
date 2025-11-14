"""
JR East Real-time Train Tracking System - Main Application (GTFS-RT Version)
FastAPI server with SSE streaming using GTFS-RT + static GTFS
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Import our modules
from config import (
    GTFS_DATA_PATH,
    SHAPEFILE_STATION_PATH, SHAPEFILE_RAIL_PATH,
    POLL_INTERVAL_SEC
)
from gtfs_loader import GTFSLoader
from shapefile_loader import ShapefileLoader
from gtfs_rt_client import GTFSRTClient
from gtfs_interpolator import GTFSInterpolator, get_service_day_start_epoch


app = FastAPI(title="JR East Real-time Train Tracker (GTFS-RT)")

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
gtfs_rt_client = None
interpolator = None
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
    global gtfs_loader, shapefile_loader, gtfs_rt_client, interpolator, rail_paths

    print("\n" + "="*60)
    print("JR East Real-time Train Tracking System (GTFS-RT)")
    print("="*60 + "\n")

    # Load GTFS data
    print("[Startup] Loading static GTFS data...")
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

    # Initialize GTFS-RT client
    print("\n[Startup] Initializing GTFS-RT client...")
    rt_feed_path = gtfs_path / "jreast_odpt_train_vehicle (5)"

    if rt_feed_path.exists():
        print(f"[Startup] Using local GTFS-RT feed: {rt_feed_path}")
        gtfs_rt_client = GTFSRTClient(feed_path=str(rt_feed_path))
    else:
        print("[Startup] WARNING: GTFS-RT feed file not found!")
        print("[Startup] Using placeholder client (no vehicles)")
        gtfs_rt_client = None

    # Initialize interpolator
    print("\n[Startup] Initializing interpolator...")
    interpolator = GTFSInterpolator(gtfs_loader)

    # Start polling loop
    print("\n[Startup] Starting polling loop...")
    asyncio.create_task(poll_loop())

    print("\n" + "="*60)
    print("Startup complete! Server is ready.")
    print("="*60 + "\n")


async def poll_loop():
    """Poll GTFS-RT feed every N seconds"""
    global live_snapshot

    if gtfs_rt_client is None:
        print("[poll_loop] No GTFS-RT client configured, skipping polling")
        return

    while True:
        try:
            # Fetch vehicles from GTFS-RT
            rt_vehicles = await gtfs_rt_client.get_vehicles()

            service_start = get_service_day_start_epoch()
            current_time = datetime.now().timestamp()

            vehicles = []
            success_count = 0
            fail_count = 0

            # Process each vehicle
            for rt_vehicle in rt_vehicles:
                trip_id = rt_vehicle.get("trip_id")
                timestamp = rt_vehicle.get("timestamp", 0)
                entity_id = rt_vehicle.get("entity_id")

                if not trip_id or not timestamp:
                    fail_count += 1
                    continue

                # Calculate position using interpolator
                position = interpolator.calculate_position(
                    trip_id=trip_id,
                    timestamp=timestamp,
                    entity_id=entity_id
                )

                if position:
                    # Calculate delay (difference between GTFS-RT timestamp and current time)
                    # For now, we don't have explicit delay info in GTFS-RT, so set to 0
                    delay_sec = 0

                    vehicles.append({
                        "trip_id": trip_id,
                        "entity_id": entity_id,
                        "lat": position["lat"],
                        "lng": position["lng"],
                        "progress": position["progress"],

                        # GTFS stop IDs (compatible with frontend)
                        "from_stop_gtfs": position.get("from_stop_id"),
                        "to_stop_gtfs": position.get("to_stop_id"),

                        "delay": delay_sec,
                        "status": "IN_TRANSIT_TO",
                        "interpolated": position["interpolated"],

                        # Timing info
                        "seg_dep_epoch": position.get("seg_dep_epoch", 0),
                        "seg_arr_epoch": position.get("seg_arr_epoch", 0),
                        "current_time_sec": position.get("current_time_sec", 0),
                        "rt_age_sec": int(current_time - timestamp) if timestamp else 0,
                    })

                    if position["interpolated"]:
                        success_count += 1
                else:
                    fail_count += 1

            # Update snapshot
            live_snapshot = {
                "seq": live_snapshot["seq"] + 1,
                "timestamp": current_time,
                "service_day_start_epoch": service_start,
                "current_time_sec": int(current_time % 86400),
                "vehicles": vehicles,
            }

            # Add rail paths only on first snapshot
            if live_snapshot["seq"] == 1:
                live_snapshot["rail_paths"] = rail_paths

            print(f"[poll_loop] Seq {live_snapshot['seq']} | "
                  f"RT vehicles: {len(rt_vehicles)} | "
                  f"Positioned: {len(vehicles)} | "
                  f"Interpolated: {success_count} | "
                  f"Failed: {fail_count}")

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
        "version": "GTFS-RT",
        "gtfs_stops": len(gtfs_loader.stops) if gtfs_loader else 0,
        "gtfs_trips": len(gtfs_loader.stop_times) if gtfs_loader else 0,
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
        "name": "JR East Real-time Train Tracker (GTFS-RT)",
        "version": "2.0.0",
        "endpoints": {
            "stream": "/api/trains/stream",
            "health": "/api/health",
            "debug": "/debug/last-snapshot"
        }
    }
