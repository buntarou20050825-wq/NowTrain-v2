"""
Position Interpolator
Calculates train position between stations based on timetable
"""
from typing import Dict
from trip_matcher import time_to_seconds, get_service_day_start_epoch


class Interpolator:
    def __init__(self, gtfs_loader, trip_matcher, station_mapper):
        self.gtfs = gtfs_loader
        self.matcher = trip_matcher
        self.mapper = station_mapper

    def calculate_position(
        self,
        rt_trip_id: str,
        current_time_sec: int,
        from_stop_odpt: str,
        to_stop_odpt: str,
        delay_sec: int
    ) -> Dict | None:
        """
        Calculate train position between stations

        Args:
            rt_trip_id: Real-time trip ID (ODPT)
            current_time_sec: Current time in seconds since midnight
            from_stop_odpt: Origin station (ODPT ID)
            to_stop_odpt: Destination station (ODPT ID)
            delay_sec: Delay in seconds

        Returns:
            Position dict with:
            - lat, lng: Interpolated coordinates
            - progress: Progress ratio (0.0 to 1.0)
            - from_stop_gtfs, to_stop_gtfs: GTFS stop IDs
            - seg_dep_epoch, seg_arr_epoch: Segment departure/arrival epoch times
            - match_score, match_reason: Matching debug info
            - static_trip_id: Matched GTFS trip ID
            - interpolated: Whether position was interpolated
        """

        # Clip delay to ±10 minutes
        delay_sec = max(-600, min(600, delay_sec))
        if abs(delay_sec) > 600:
            print(f"[Interpolator] Warning: Large delay clipped: {delay_sec}s -> ±600s")

        # Match trip_id
        static_trip_id, debug_info = self.matcher.find_best_match(
            rt_trip_id,
            current_time_sec,
            from_stop_odpt,
            to_stop_odpt
        )

        if not static_trip_id:
            # Matching failed -> fallback to from_stop position
            from_stop_gtfs = self.mapper.get_gtfs_stop_id(from_stop_odpt)
            if from_stop_gtfs and from_stop_gtfs in self.gtfs.stops:
                stop_pos = self.gtfs.stops[from_stop_gtfs]
                return {
                    "lat": stop_pos["lat"],
                    "lng": stop_pos["lng"],
                    "progress": 0.0,
                    "from_stop_gtfs": from_stop_gtfs,
                    "to_stop_gtfs": None,
                    "seg_dep_epoch": 0,
                    "seg_arr_epoch": 0,
                    "match_score": 0,
                    "match_reason": debug_info["reason"],
                    "static_trip_id": None,
                    "interpolated": False
                }
            return None

        # Get stop_times
        stop_times = self.gtfs.stop_times.get(static_trip_id, [])
        if not stop_times:
            return None

        # Convert ODPT -> GTFS stop IDs
        from_stop_gtfs = self.mapper.get_gtfs_stop_id(from_stop_odpt)
        to_stop_gtfs = self.mapper.get_gtfs_stop_id(to_stop_odpt)

        if not from_stop_gtfs or not to_stop_gtfs:
            return None

        # Find segment indices
        idx_from = -1
        idx_to = -1

        for i, st in enumerate(stop_times):
            if st["stop_id"] == from_stop_gtfs:
                idx_from = i
            if st["stop_id"] == to_stop_gtfs:
                idx_to = i

        if idx_from < 0 or idx_to < 0 or idx_from >= idx_to:
            return None

        # Get segment times
        from_st = stop_times[idx_from]
        to_st = stop_times[idx_to]

        dep_time = time_to_seconds(from_st["departure_time"]) + delay_sec
        arr_time = time_to_seconds(to_st["arrival_time"]) + delay_sec

        # Convert to epoch time
        service_start = get_service_day_start_epoch()
        seg_dep_epoch = service_start + dep_time
        seg_arr_epoch = service_start + arr_time

        # Calculate progress
        duration = arr_time - dep_time
        if duration <= 0:
            progress = 0.0
        else:
            progress = (current_time_sec - dep_time) / duration
            progress = max(0.0, min(1.0, progress))

        # Get station coordinates
        from_pos = self.gtfs.stops.get(from_stop_gtfs)
        to_pos = self.gtfs.stops.get(to_stop_gtfs)

        if not from_pos or not to_pos:
            return None

        # Linear interpolation
        lat = from_pos["lat"] + (to_pos["lat"] - from_pos["lat"]) * progress
        lng = from_pos["lng"] + (to_pos["lng"] - from_pos["lng"]) * progress

        return {
            "lat": lat,
            "lng": lng,
            "progress": progress,
            "from_stop_gtfs": from_stop_gtfs,
            "to_stop_gtfs": to_stop_gtfs,
            "seg_dep_epoch": seg_dep_epoch,
            "seg_arr_epoch": seg_arr_epoch,
            "match_score": debug_info.get("score", 0),
            "match_reason": debug_info.get("match_details", "unknown"),
            "static_trip_id": static_trip_id,
            "interpolated": True
        }
