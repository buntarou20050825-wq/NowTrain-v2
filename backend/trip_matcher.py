"""
Trip Matcher: Match ODPT trip_id to GTFS static trip_id
Uses scoring algorithm based on train number, time, and station sequence
"""
import re
from typing import Tuple, Dict, List
from datetime import datetime
import pytz


JST = pytz.timezone('Asia/Tokyo')


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds (supports 24+ hours)"""
    h, m, s = map(int, time_str.split(':'))
    return h * 3600 + m * 60 + s


def get_current_time_sec() -> int:
    """Get current time in seconds since midnight (JST)"""
    now = datetime.now(JST)
    return now.hour * 3600 + now.minute * 60 + now.second


def get_service_day_start_epoch() -> int:
    """Get service day start time as epoch seconds (JST midnight)"""
    now = datetime.now(JST)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start_of_day.timestamp())


class TripMatcher:
    def __init__(self, gtfs_loader, station_mapper):
        self.gtfs = gtfs_loader
        self.mapper = station_mapper
        self.cache: Dict[str, Tuple[str, int]] = {}  # rt_trip_id -> (static_trip_id, cached_time)
        self.train_number_index = self._build_index()

    def _build_index(self) -> Dict[str, List[str]]:
        """Build reverse index: train_number -> list of trip_ids"""
        print("[TripMatcher] Building train number index...")
        index = {}

        for trip_id in self.gtfs.stop_times.keys():
            train_number = self._extract_train_number(trip_id)
            if train_number not in index:
                index[train_number] = []
            index[train_number].append(trip_id)

        print(f"[TripMatcher] Indexed {len(index)} unique train numbers")
        return index

    def _extract_train_number(self, trip_id: str) -> str:
        """
        Extract train number from trip_id

        Examples:
            "JR-East.Chuo.554M" -> "554M"
            "1610554M" -> "554M"
            "4110554M" -> "554M"
        """
        if '.' in trip_id:
            # ODPT format: "JR-East.Chuo.554M"
            return trip_id.split('.')[-1]

        # GTFS format: "1610554M", "4110554M"
        # Extract trailing alphanumeric pattern
        match = re.search(r'[0-9]+[A-Z]$', trip_id)
        if match:
            return match.group()

        return trip_id

    def find_best_match(
        self,
        rt_trip_id: str,
        current_time_sec: int,
        from_stop_odpt: str,
        to_stop_odpt: str
    ) -> Tuple[str | None, Dict]:
        """
        Find best matching GTFS trip_id for real-time trip

        Args:
            rt_trip_id: Real-time trip ID (ODPT format)
            current_time_sec: Current time in seconds since midnight
            from_stop_odpt: Origin station (ODPT ID)
            to_stop_odpt: Destination station (ODPT ID)

        Returns:
            Tuple of (matched_trip_id, debug_info)
        """

        # Check cache (TTL: 15 minutes)
        if rt_trip_id in self.cache:
            cached_trip, cached_time = self.cache[rt_trip_id]
            age = current_time_sec - cached_time

            if age > 900:  # 15 minutes expired
                del self.cache[rt_trip_id]
            elif self._is_cache_valid(cached_trip, from_stop_odpt, to_stop_odpt):
                return cached_trip, {"reason": "cache-hit", "age_sec": age}
            else:
                # Direction changed -> invalidate
                del self.cache[rt_trip_id]

        # Extract train number
        train_number = self._extract_train_number(rt_trip_id)

        # Get candidates (O(1) lookup)
        candidates = self.train_number_index.get(train_number, [])

        if not candidates:
            return None, {"reason": "no-candidate", "train_number": train_number}

        # Convert ODPT station IDs to GTFS stop IDs
        from_stop_gtfs = self.mapper.get_gtfs_stop_id(from_stop_odpt)
        to_stop_gtfs = self.mapper.get_gtfs_stop_id(to_stop_odpt)

        # Scoring
        best_trip = None
        best_score = -float('inf')

        for candidate_id in candidates:
            stop_times = self.gtfs.stop_times.get(candidate_id, [])
            if not stop_times:
                continue

            # First departure time
            first_dep = time_to_seconds(stop_times[0]["departure_time"])

            # Time proximity score (closer is better)
            time_diff = abs(current_time_sec - first_dep)
            score = -time_diff

            # Station matching
            idx_from = -1
            idx_to = -1

            for i, st in enumerate(stop_times):
                if st["stop_id"] == from_stop_gtfs:
                    idx_from = i
                if st["stop_id"] == to_stop_gtfs:
                    idx_to = i

            # Station match bonuses
            if idx_from >= 0:
                score += 10000
            if idx_to >= 0:
                score += 10000

            # Station order check
            if idx_from >= 0 and idx_to >= 0:
                if idx_from < idx_to:
                    score += 1000  # Correct order

                    # Check if within segment
                    dep_time = time_to_seconds(stop_times[idx_from]["departure_time"])
                    arr_time = time_to_seconds(stop_times[idx_to]["arrival_time"])

                    # Too short segment -> penalty (exclude stop-only trips)
                    duration = arr_time - dep_time
                    if duration < 60:  # Less than 1 minute
                        score -= 5000

                    # Current time within segment -> big bonus
                    if dep_time <= current_time_sec <= arr_time:
                        score += 3000
                else:
                    score -= 10000  # Wrong order

            if score > best_score:
                best_score = score
                best_trip = candidate_id

        # Cache result
        if best_trip:
            self.cache[rt_trip_id] = (best_trip, current_time_sec)

        debug_info = {
            "reason": "matched" if best_trip else "low-score",
            "score": best_score,
            "candidates": len(candidates),
            "match_details": "time+from+to+order" if best_score > 20000 else "partial"
        }

        return best_trip, debug_info

    def _is_cache_valid(
        self,
        cached_trip: str,
        from_stop_odpt: str,
        to_stop_odpt: str
    ) -> bool:
        """Check if cached trip is still valid for current segment"""
        stop_times = self.gtfs.stop_times.get(cached_trip)
        if not stop_times:
            return False

        from_stop_gtfs = self.mapper.get_gtfs_stop_id(from_stop_odpt)
        to_stop_gtfs = self.mapper.get_gtfs_stop_id(to_stop_odpt)

        if not from_stop_gtfs or not to_stop_gtfs:
            return False

        # Check station order
        stop_ids = [st["stop_id"] for st in stop_times]
        try:
            idx_from = stop_ids.index(from_stop_gtfs)
            idx_to = stop_ids.index(to_stop_gtfs)
            return idx_from < idx_to  # Valid if correct order
        except ValueError:
            return False  # Station not found = invalid
