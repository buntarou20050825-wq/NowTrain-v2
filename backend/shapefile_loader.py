"""
Shapefile Loader for Station and Rail Section Data
Loads geographic data from Japanese national land information shapefiles
"""
import shapefile
from pathlib import Path
from typing import Dict, List


class ShapefileLoader:
    def __init__(self, station_shp_path: str, rail_shp_path: str = None):
        self.station_shp = Path(station_shp_path)
        self.rail_shp = Path(rail_shp_path) if rail_shp_path else None
        self.stations: Dict[str, dict] = {}
        self.rail_paths: Dict[str, List[List[dict]]] = {}

    def load_stations(self) -> Dict[str, dict]:
        """Load station data from shapefile"""
        if not self.station_shp.exists():
            print(f"[Shapefile] Warning: {self.station_shp} not found")
            return {}

        print("[Shapefile] Loading station data...")
        try:
            sf = shapefile.Reader(str(self.station_shp))

            for record in sf.iterShapeRecords():
                try:
                    # Get attributes (field names may vary)
                    rec = record.record
                    fields = [field[0] for field in sf.fields[1:]]  # Skip DeletionFlag

                    # Try to get station name and railway info
                    station_name = None
                    railway_name = None
                    operator = None

                    for i, field in enumerate(fields):
                        if 'N02_005' in field:
                            station_name = rec[i] if i < len(rec) else None
                        elif 'N02_003' in field:
                            railway_name = rec[i] if i < len(rec) else None
                        elif 'N02_004' in field:
                            operator = rec[i] if i < len(rec) else None

                    # Get coordinates
                    if record.shape.points:
                        point = record.shape.points[0]

                        if station_name:
                            self.stations[station_name] = {
                                "lat": point[1],
                                "lng": point[0],
                                "railway": railway_name or "",
                                "operator": operator or ""
                            }
                except Exception as e:
                    print(f"[Shapefile] Error processing station record: {e}")
                    continue

            print(f"[Shapefile] Loaded {len(self.stations)} stations")
        except Exception as e:
            print(f"[Shapefile] Error loading stations: {e}")

        return self.stations

    def load_rail_sections(self) -> Dict[str, List[List[dict]]]:
        """Load rail section data from shapefile"""
        if not self.rail_shp or not self.rail_shp.exists():
            print("[Shapefile] Rail section file not provided or not found")
            return {}

        print("[Shapefile] Loading rail section data...")
        try:
            sf = shapefile.Reader(str(self.rail_shp))

            for record in sf.iterShapeRecords():
                try:
                    # Get railway information
                    rec = record.record
                    fields = [field[0] for field in sf.fields[1:]]

                    railway_name = None
                    line_name = None

                    for i, field in enumerate(fields):
                        if 'N02_003' in field:
                            railway_name = rec[i] if i < len(rec) else None
                        elif 'N02_002' in field:
                            line_name = rec[i] if i < len(rec) else None

                    # Get line coordinates
                    if record.shape.points and railway_name:
                        points = record.shape.points
                        coordinates = [{"lat": p[1], "lng": p[0]} for p in points]

                        key = railway_name
                        if key not in self.rail_paths:
                            self.rail_paths[key] = []

                        self.rail_paths[key].append(coordinates)
                except Exception as e:
                    print(f"[Shapefile] Error processing rail record: {e}")
                    continue

            print(f"[Shapefile] Loaded {len(self.rail_paths)} rail paths")
        except Exception as e:
            print(f"[Shapefile] Error loading rail sections: {e}")

        return self.rail_paths

    def enhance_station_mapping(self, station_mapper):
        """Enhance station mapping with shapefile data"""
        print("[Shapefile] Enhancing station mapping...")
        enhanced = 0

        try:
            for odpt_id, odpt_station in station_mapper.odpt_stations.items():
                odpt_name = odpt_station.get("name", "")

                # Search for matching station in shapefile
                for sf_name, sf_station in self.stations.items():
                    if odpt_name and (odpt_name in sf_name or sf_name in odpt_name):
                        # Update with more accurate coordinates
                        odpt_station["lat"] = sf_station["lat"]
                        odpt_station["lon"] = sf_station["lng"]
                        enhanced += 1
                        break

            print(f"[Shapefile] Enhanced {enhanced} station coordinates")
        except Exception as e:
            print(f"[Shapefile] Error enhancing mapping: {e}")
