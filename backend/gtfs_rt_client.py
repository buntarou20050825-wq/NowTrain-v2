"""
GTFS-RT Client
Fetches real-time vehicle positions from GTFS-RT feed
"""
import gzip
import httpx
from typing import List, Dict, Optional
from pathlib import Path
import gtfs_realtime_pb2


class GTFSRTClient:
    def __init__(self, feed_path: Optional[str] = None, feed_url: Optional[str] = None):
        """
        Initialize GTFS-RT client

        Args:
            feed_path: Path to local GTFS-RT file (for development)
            feed_url: URL to GTFS-RT feed (for production)
        """
        self.feed_path = feed_path
        self.feed_url = feed_url
        self.consecutive_failures = 0
        self.backoff_sec = 3

    async def get_vehicles(self) -> List[Dict]:
        """
        Get vehicle positions from GTFS-RT feed

        Returns:
            List of vehicle dictionaries with:
            - entity_id: Vehicle entity identifier
            - trip_id: Trip identifier (matches static GTFS)
            - route_id: Route identifier (if available)
            - timestamp: Vehicle position timestamp (unix epoch)
            - latitude: Vehicle latitude (if available)
            - longitude: Vehicle longitude (if available)
            - current_stop_sequence: Current stop sequence (if available)
            - current_status: Vehicle status (if available)
        """
        try:
            # Load feed data
            if self.feed_path:
                raw_data = self._load_from_file(self.feed_path)
            elif self.feed_url:
                raw_data = await self._load_from_url(self.feed_url)
            else:
                raise ValueError("Either feed_path or feed_url must be provided")

            # Parse GTFS-RT protobuf
            feed = gtfs_realtime_pb2.FeedMessage()

            # Handle gzip compression
            if raw_data[:2] == b"\x1f\x8b":
                raw_data = gzip.decompress(raw_data)

            feed.ParseFromString(raw_data)

            # Extract vehicle positions
            vehicles = []
            for entity in feed.entity:
                if not entity.HasField("vehicle"):
                    continue

                vehicle = entity.vehicle

                # Extract trip information
                trip_id = vehicle.trip.trip_id if vehicle.HasField("trip") else None
                route_id = vehicle.trip.route_id if vehicle.HasField("trip") else None

                # Skip if no trip_id
                if not trip_id:
                    continue

                vehicle_dict = {
                    "entity_id": entity.id,
                    "trip_id": trip_id,
                    "route_id": route_id or "",
                    "timestamp": vehicle.timestamp if vehicle.HasField("timestamp") else 0,
                }

                # Extract position if available
                if vehicle.HasField("position"):
                    vehicle_dict["latitude"] = vehicle.position.latitude
                    vehicle_dict["longitude"] = vehicle.position.longitude

                # Extract stop information if available
                if vehicle.HasField("current_stop_sequence"):
                    vehicle_dict["current_stop_sequence"] = vehicle.current_stop_sequence

                if vehicle.HasField("current_status"):
                    vehicle_dict["current_status"] = vehicle.current_status

                vehicles.append(vehicle_dict)

            print(f"[GTFSRTClient] Parsed {len(vehicles)} vehicles from feed")
            self.consecutive_failures = 0
            self.backoff_sec = 3

            return vehicles

        except Exception as e:
            print(f"[GTFSRTClient] Error fetching vehicles: {e}")
            import traceback
            traceback.print_exc()

            self.consecutive_failures += 1
            self.backoff_sec = min(30, self.backoff_sec * 2)

            return []

    def _load_from_file(self, file_path: str) -> bytes:
        """Load GTFS-RT data from local file"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"GTFS-RT file not found: {file_path}")

        with open(path, "rb") as f:
            return f.read()

    async def _load_from_url(self, url: str) -> bytes:
        """Load GTFS-RT data from HTTP URL"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
