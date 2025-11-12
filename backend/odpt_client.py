"""
ODPT API Client
Fetches real-time train data from Open Data Challenge for Public Transportation
"""
import httpx
import asyncio
from typing import List, Dict


class ODPTClient:
    def __init__(self, api_key: str, railways: List[str], base_url: str = "https://api-tokyochallenge.odpt.org/api/v4"):
        self.api_key = api_key
        self.base_url = base_url
        self.railways = railways
        self.consecutive_failures = 0
        self.backoff_sec = 3

    async def get_trains(self) -> List[Dict]:
        """
        Get train data for all configured railways

        Returns:
            List of train dictionaries with:
            - trip_id: ODPT trip identifier
            - from_stop: Departing station ID
            - to_stop: Arriving station ID
            - delay: Delay in seconds
            - train_number: Train number
            - railway: Railway ID
        """
        all_trains = []

        for railway in self.railways:
            try:
                trains = await self._fetch_railway(railway)
                all_trains.extend(trains)
                self.consecutive_failures = 0
                self.backoff_sec = 3
            except Exception as e:
                print(f"[ODPT] Failed to fetch {railway}: {e}")
                self.consecutive_failures += 1

                # Exponential backoff (max 30 seconds)
                self.backoff_sec = min(30, self.backoff_sec * 2)
                await asyncio.sleep(self.backoff_sec)

        return all_trains

    async def _fetch_railway(self, railway_id: str) -> List[Dict]:
        """Fetch train data for a specific railway"""
        url = f"{self.base_url}/odpt:Train"
        params = {
            "acl:consumerKey": self.api_key,
            "odpt:railway": railway_id
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

            if response.status_code == 429:
                raise Exception("Rate limited (429)")

            response.raise_for_status()
            data = response.json()

            # Normalize data
            trains = []
            for train in data:
                trains.append({
                    "trip_id": train.get("owl:sameAs") or train.get("odpt:train"),
                    "from_stop": train.get("odpt:fromStation"),
                    "to_stop": train.get("odpt:toStation"),
                    "delay": train.get("odpt:delay", 0),
                    "train_number": train.get("odpt:trainNumber", ""),
                    "railway": railway_id
                })

            return trains

    async def get_stations(self, railway_id: str) -> Dict[str, dict]:
        """
        Get station list for a specific railway

        Returns:
            Dictionary of station_id -> {lat, lon, name}
        """
        url = f"{self.base_url}/odpt:Station"
        params = {
            "acl:consumerKey": self.api_key,
            "odpt:railway": railway_id
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            stations = {}
            for station in data:
                station_id = station.get("owl:sameAs")
                if station_id and station.get("geo:lat") and station.get("geo:long"):
                    stations[station_id] = {
                        "lat": float(station["geo:lat"]),
                        "lon": float(station["geo:long"]),
                        "name": station.get("dc:title", "")
                    }

            return stations
