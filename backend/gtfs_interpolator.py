"""
GTFS Interpolator
Calculates train position between stations based on GTFS-RT and static GTFS
"""
from typing import Dict, Optional
from datetime import datetime
import pytz


JST = pytz.timezone('Asia/Tokyo')


def time_to_seconds(time_str: str) -> Optional[int]:
    """
    Convert HH:MM:SS to seconds (supports 24+ hours)

    Args:
        time_str: Time string in HH:MM:SS format

    Returns:
        Seconds since midnight, or None if invalid
    """
    if not time_str or time_str.strip() == '':
        return None

    try:
        parts = time_str.split(':')
        if len(parts) != 3:
            return None
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        return None


def get_service_day_start_epoch() -> int:
    """Get service day start time as epoch seconds (JST midnight)"""
    now = datetime.now(JST)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start_of_day.timestamp())


class GTFSInterpolator:
    """
    Interpolates train positions using GTFS-RT timestamp and static GTFS timetables
    """

    def __init__(self, gtfs_loader):
        """
        Initialize interpolator

        Args:
            gtfs_loader: GTFSLoader instance with stops and stop_times
        """
        self.gtfs = gtfs_loader
        self.stops = gtfs_loader.stops
        self.stop_times = gtfs_loader.stop_times

    def calculate_position(
        self,
        trip_id: str,
        timestamp: int,
        entity_id: str = None
    ) -> Optional[Dict]:
        """
        Calculate train position between stations

        Args:
            trip_id: GTFS trip_id (matches static GTFS)
            timestamp: Unix timestamp from GTFS-RT
            entity_id: Vehicle entity ID (for debugging)

        Returns:
            Position dict with:
            - lat, lng: Interpolated coordinates
            - progress: Progress ratio (0.0 to 1.0)
            - from_stop_id: Origin stop (GTFS stop_id)
            - to_stop_id: Destination stop (GTFS stop_id)
            - seg_dep_epoch: Segment departure epoch time
            - seg_arr_epoch: Segment arrival epoch time
            - current_time_sec: Current time in seconds since midnight
            - interpolated: Whether position was interpolated (vs. fallback)
        """

        # Get stop_times for this trip
        stop_times_list = self.stop_times.get(trip_id)
        if not stop_times_list or len(stop_times_list) < 2:
            return None

        # Convert timestamp to seconds since midnight (service day time)
        current_time_sec = timestamp % 86400

        # Get service day start (for epoch conversion)
        service_start = get_service_day_start_epoch()

        # Find current segment
        # Iterate through consecutive stops to find where the train is
        for i in range(len(stop_times_list) - 1):
            from_st = stop_times_list[i]
            to_st = stop_times_list[i + 1]

            # Get departure time (fallback to arrival_time if empty)
            dep_time = time_to_seconds(from_st["departure_time"])
            if dep_time is None:
                dep_time = time_to_seconds(from_st["arrival_time"])
            if dep_time is None:
                continue  # Skip this segment if no valid time

            # Get arrival time (fallback to departure_time if empty)
            arr_time = time_to_seconds(to_st["arrival_time"])
            if arr_time is None:
                arr_time = time_to_seconds(to_st["departure_time"])
            if arr_time is None:
                continue  # Skip this segment if no valid time

            # Check if current time falls within this segment
            if dep_time <= current_time_sec <= arr_time:
                from_stop_id = from_st["stop_id"]
                to_stop_id = to_st["stop_id"]

                # Get station coordinates
                from_pos = self.stops.get(from_stop_id)
                to_pos = self.stops.get(to_stop_id)

                if not from_pos or not to_pos:
                    continue

                # Calculate progress
                duration = arr_time - dep_time
                if duration <= 0:
                    progress = 0.0
                else:
                    progress = (current_time_sec - dep_time) / duration
                    progress = max(0.0, min(1.0, progress))

                # Linear interpolation
                lat = from_pos["lat"] + (to_pos["lat"] - from_pos["lat"]) * progress
                lng = from_pos["lng"] + (to_pos["lng"] - from_pos["lng"]) * progress

                # Convert segment times to epoch
                seg_dep_epoch = service_start + dep_time
                seg_arr_epoch = service_start + arr_time

                return {
                    "lat": lat,
                    "lng": lng,
                    "progress": progress,
                    "from_stop_id": from_stop_id,
                    "to_stop_id": to_stop_id,
                    "seg_dep_epoch": seg_dep_epoch,
                    "seg_arr_epoch": seg_arr_epoch,
                    "current_time_sec": current_time_sec,
                    "interpolated": True
                }

        # No matching segment found -> fallback to first/last stop
        # This can happen if the train is before first departure or after last arrival

        first_stop_id = stop_times_list[0]["stop_id"]
        last_stop_id = stop_times_list[-1]["stop_id"]

        first_dep = time_to_seconds(stop_times_list[0]["departure_time"]) or \
                    time_to_seconds(stop_times_list[0]["arrival_time"]) or 0
        last_arr = time_to_seconds(stop_times_list[-1]["arrival_time"]) or \
                   time_to_seconds(stop_times_list[-1]["departure_time"]) or 86400

        # Before first departure -> show at first stop
        if first_dep is not None and current_time_sec < first_dep:
            stop_pos = self.stops.get(first_stop_id)
            if stop_pos:
                return {
                    "lat": stop_pos["lat"],
                    "lng": stop_pos["lng"],
                    "progress": 0.0,
                    "from_stop_id": first_stop_id,
                    "to_stop_id": None,
                    "seg_dep_epoch": service_start + first_dep,
                    "seg_arr_epoch": service_start + first_dep,
                    "current_time_sec": current_time_sec,
                    "interpolated": False
                }

        # After last arrival -> show at last stop
        if last_arr is not None and current_time_sec > last_arr:
            stop_pos = self.stops.get(last_stop_id)
            if stop_pos:
                return {
                    "lat": stop_pos["lat"],
                    "lng": stop_pos["lng"],
                    "progress": 1.0,
                    "from_stop_id": last_stop_id,
                    "to_stop_id": None,
                    "seg_dep_epoch": service_start + last_arr,
                    "seg_arr_epoch": service_start + last_arr,
                    "current_time_sec": current_time_sec,
                    "interpolated": False
                }

        return None
