"""
GTFS Static Data Loader
Loads stops, routes, trips, and stop_times from JSON files
"""
import json
import os
from pathlib import Path
from typing import Dict, List


class GTFSLoader:
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.stops: Dict[str, dict] = {}
        self.routes: Dict[str, dict] = {}
        self.trips: Dict[str, dict] = {}
        self.stop_times: Dict[str, List[dict]] = {}  # trip_id -> list of stop_times

        self.load_all()

    def load_all(self):
        """Load all GTFS data"""
        print(f"[GTFSLoader] Loading data from {self.data_path}")

        self._load_stops()
        self._load_routes()
        self._load_trips()
        self._load_stop_times()

        print(f"[GTFSLoader] Loaded: {len(self.stops)} stops, "
              f"{len(self.routes)} routes, {len(self.trips)} trips, "
              f"{len(self.stop_times)} trip stop_times")

    def _load_stops(self):
        """Load stops.json"""
        stops_file = self.data_path / "stops.json"
        if not stops_file.exists():
            print(f"[GTFSLoader] Warning: {stops_file} not found")
            return

        with open(stops_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for stop in data:
            stop_id = stop.get("stop_id")
            if stop_id:
                self.stops[stop_id] = {
                    "stop_id": stop_id,
                    "stop_name": stop.get("stop_name", ""),
                    "lat": float(stop.get("stop_lat", 0)),
                    "lng": float(stop.get("stop_lon", 0))
                }

        print(f"[GTFSLoader] Loaded {len(self.stops)} stops")

    def _load_routes(self):
        """Load routes.json"""
        routes_file = self.data_path / "routes.json"
        if not routes_file.exists():
            print(f"[GTFSLoader] Warning: {routes_file} not found")
            return

        with open(routes_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for route in data:
            route_id = route.get("route_id")
            if route_id:
                self.routes[route_id] = {
                    "route_id": route_id,
                    "route_short_name": route.get("route_short_name", ""),
                    "route_long_name": route.get("route_long_name", ""),
                    "route_color": route.get("route_color", "000000")
                }

        print(f"[GTFSLoader] Loaded {len(self.routes)} routes")

    def _load_trips(self):
        """Load trips.json"""
        trips_file = self.data_path / "trips.json"
        if not trips_file.exists():
            print(f"[GTFSLoader] Warning: {trips_file} not found")
            return

        with open(trips_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for trip in data:
            trip_id = trip.get("trip_id")
            if trip_id:
                self.trips[trip_id] = {
                    "trip_id": trip_id,
                    "route_id": trip.get("route_id", ""),
                    "service_id": trip.get("service_id", ""),
                    "trip_headsign": trip.get("trip_headsign", "")
                }

        print(f"[GTFSLoader] Loaded {len(self.trips)} trips")

    def _load_stop_times(self):
        """Load stop_times.json and group by trip_id"""
        stop_times_file = self.data_path / "stop_times.json"
        if not stop_times_file.exists():
            print(f"[GTFSLoader] Warning: {stop_times_file} not found")
            return

        with open(stop_times_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Group by trip_id
        for stop_time in data:
            trip_id = stop_time.get("trip_id")
            if not trip_id:
                continue

            if trip_id not in self.stop_times:
                self.stop_times[trip_id] = []

            self.stop_times[trip_id].append({
                "stop_id": stop_time.get("stop_id", ""),
                "arrival_time": stop_time.get("arrival_time", "00:00:00"),
                "departure_time": stop_time.get("departure_time", "00:00:00"),
                "stop_sequence": int(stop_time.get("stop_sequence", 0))
            })

        # Sort each trip's stop_times by stop_sequence
        for trip_id in self.stop_times:
            self.stop_times[trip_id].sort(key=lambda x: x["stop_sequence"])

        print(f"[GTFSLoader] Loaded stop_times for {len(self.stop_times)} trips")

    def get_stop(self, stop_id: str) -> dict | None:
        """Get stop by ID"""
        return self.stops.get(stop_id)

    def get_trip(self, trip_id: str) -> dict | None:
        """Get trip by ID"""
        return self.trips.get(trip_id)

    def get_stop_times_for_trip(self, trip_id: str) -> List[dict]:
        """Get stop_times for a trip"""
        return self.stop_times.get(trip_id, [])
