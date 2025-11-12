"""
Station Mapper: ODPT <-> GTFS
Maps station IDs between ODPT and GTFS using coordinate-based matching and overrides
"""
import math
import json
from pathlib import Path
from typing import Dict


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in kilometers using Haversine formula

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


class StationMapper:
    def __init__(self, gtfs_loader, odpt_stations: Dict[str, dict], overrides_path: str = None):
        self.gtfs_stops = gtfs_loader.stops
        self.odpt_stations = odpt_stations
        self.odpt_to_gtfs: Dict[str, str] = {}
        self.overrides: Dict[str, str] = {}

        # Load overrides
        if overrides_path and Path(overrides_path).exists():
            try:
                with open(overrides_path, 'r', encoding='utf-8') as f:
                    self.overrides = json.load(f)
                print(f"[Mapper] Loaded {len(self.overrides)} overrides")
            except Exception as e:
                print(f"[Mapper] Error loading overrides: {e}")

        self.create_mapping()

    def create_mapping(self):
        """Create station mapping using coordinates and overrides"""
        print("[Mapper] Creating station mapping...")

        matched_300m = 0
        matched_500m = 0
        override_count = 0

        for odpt_id, odpt_station in self.odpt_stations.items():
            # 1. Check overrides first
            if odpt_id in self.overrides:
                self.odpt_to_gtfs[odpt_id] = self.overrides[odpt_id]
                override_count += 1
                continue

            # 2. Coordinate-based matching
            best_match = None
            best_distance = float('inf')

            odpt_lat = odpt_station.get("lat")
            odpt_lon = odpt_station.get("lon")

            if not odpt_lat or not odpt_lon:
                continue

            for gtfs_id, gtfs_stop in self.gtfs_stops.items():
                distance = haversine_distance(
                    odpt_lat, odpt_lon,
                    gtfs_stop["lat"], gtfs_stop["lng"]
                )

                if distance < best_distance:
                    best_distance = distance
                    best_match = gtfs_id

            # Within 300m - good match
            if best_distance < 0.3:
                self.odpt_to_gtfs[odpt_id] = best_match
                matched_300m += 1
            # Within 500m - acceptable fallback
            elif best_distance < 0.5:
                self.odpt_to_gtfs[odpt_id] = best_match
                matched_500m += 1
                print(f"[Mapper] Warning: {odpt_id} matched at {best_distance*1000:.0f}m")

        total = len(self.odpt_stations)
        print(f"[Mapper] Mapped {matched_300m}/{total} stations (300m), "
              f"{matched_500m} (500m), {override_count} overrides")

    def get_gtfs_stop_id(self, odpt_station_id: str) -> str | None:
        """
        Get GTFS stop ID from ODPT station ID

        Args:
            odpt_station_id: ODPT station identifier

        Returns:
            GTFS stop_id or None if not found
        """
        return self.odpt_to_gtfs.get(odpt_station_id)

    def get_odpt_station_info(self, odpt_station_id: str) -> dict | None:
        """
        Get ODPT station information

        Args:
            odpt_station_id: ODPT station identifier

        Returns:
            Station info dict or None
        """
        return self.odpt_stations.get(odpt_station_id)
