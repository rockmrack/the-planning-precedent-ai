"""
Spatial Search Service
Location-based search for planning applications
"""

import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .geocoding_service import GeocodingService, GeoLocation

logger = logging.getLogger(__name__)


class SpatialSearchType(str, Enum):
    """Types of spatial searches"""
    RADIUS = "radius"  # Within X meters of a point
    BOUNDING_BOX = "bounding_box"  # Within a rectangle
    WARD = "ward"  # Within a specific ward
    POSTCODE_AREA = "postcode_area"  # Within postcode outcode
    POLYGON = "polygon"  # Within a custom polygon


@dataclass
class BoundingBox:
    """Geographic bounding box"""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        """Check if point is within bounding box"""
        return (
            self.min_lat <= lat <= self.max_lat and
            self.min_lon <= lon <= self.max_lon
        )

    def expand(self, meters: float) -> 'BoundingBox':
        """Expand bounding box by approximate meters"""
        # Rough approximation: 1 degree lat = 111km
        lat_delta = meters / 111000
        # Lon varies by latitude, use average
        lon_delta = meters / (111000 * 0.7)  # ~51 degrees latitude

        return BoundingBox(
            min_lat=self.min_lat - lat_delta,
            max_lat=self.max_lat + lat_delta,
            min_lon=self.min_lon - lon_delta,
            max_lon=self.max_lon + lon_delta
        )


@dataclass
class SpatialSearchQuery:
    """Spatial search parameters"""
    search_type: SpatialSearchType
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    radius_meters: Optional[int] = None
    bounding_box: Optional[BoundingBox] = None
    ward: Optional[str] = None
    postcode_area: Optional[str] = None
    polygon: Optional[List[Tuple[float, float]]] = None


@dataclass
class SpatialSearchResult:
    """Result with distance information"""
    case_reference: str
    address: str
    latitude: float
    longitude: float
    distance_meters: Optional[float] = None
    postcode: Optional[str] = None
    ward: Optional[str] = None
    # Planning data
    description: Optional[str] = None
    decision: Optional[str] = None
    decision_date: Optional[str] = None
    development_type: Optional[str] = None


class SpatialSearchService:
    """Handles spatial/geographic searches"""

    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.geocoding = GeocodingService()

        # Camden wards with approximate centroids
        self.camden_wards = {
            "Belsize": {"lat": 51.5504, "lon": -0.1692},
            "Bloomsbury": {"lat": 51.5228, "lon": -0.1245},
            "Camden Town with Primrose Hill": {"lat": 51.5434, "lon": -0.1474},
            "Cantelowes": {"lat": 51.5521, "lon": -0.1329},
            "Fortune Green": {"lat": 51.5553, "lon": -0.1931},
            "Frognal": {"lat": 51.5556, "lon": -0.1794},
            "Gospel Oak": {"lat": 51.5546, "lon": -0.1512},
            "Hampstead Town": {"lat": 51.5569, "lon": -0.1751},
            "Haverstock": {"lat": 51.5462, "lon": -0.1556},
            "Highgate": {"lat": 51.5664, "lon": -0.1470},
            "Holborn and Covent Garden": {"lat": 51.5154, "lon": -0.1224},
            "Kentish Town": {"lat": 51.5510, "lon": -0.1398},
            "Kilburn": {"lat": 51.5443, "lon": -0.1946},
            "King's Cross": {"lat": 51.5305, "lon": -0.1247},
            "Regent's Park": {"lat": 51.5277, "lon": -0.1541},
            "St Pancras and Somers Town": {"lat": 51.5324, "lon": -0.1304},
            "Swiss Cottage": {"lat": 51.5449, "lon": -0.1752},
            "West Hampstead": {"lat": 51.5486, "lon": -0.1911}
        }

    async def search_by_radius(
        self,
        center_lat: float,
        center_lon: float,
        radius_meters: int,
        limit: int = 50
    ) -> List[SpatialSearchResult]:
        """
        Search for planning applications within radius of a point.
        Uses PostGIS ST_DWithin for efficiency.
        """
        if not self.supabase:
            return self._demo_radius_search(center_lat, center_lon, radius_meters)

        try:
            # Use Supabase RPC function for spatial query
            result = self.supabase.rpc(
                "search_by_radius",
                {
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "radius_m": radius_meters,
                    "result_limit": limit
                }
            ).execute()

            if result.data:
                return [
                    self._dict_to_result(d, center_lat, center_lon)
                    for d in result.data
                ]

        except Exception as e:
            logger.error(f"Spatial search error: {e}")

        return []

    async def search_by_address(
        self,
        address: str,
        radius_meters: int = 500,
        limit: int = 50
    ) -> Tuple[Optional[GeoLocation], List[SpatialSearchResult]]:
        """
        Search near an address. First geocodes, then does radius search.
        """
        # Geocode the address
        geo_result = await self.geocoding.geocode(address)

        if not geo_result.success:
            return None, []

        location = geo_result.location

        # Search around the location
        results = await self.search_by_radius(
            center_lat=location.latitude,
            center_lon=location.longitude,
            radius_meters=radius_meters,
            limit=limit
        )

        return location, results

    async def search_by_postcode(
        self,
        postcode: str,
        include_nearby: bool = True,
        radius_meters: int = 200
    ) -> List[SpatialSearchResult]:
        """Search for applications in or near a postcode"""
        # Get postcode info
        info = await self.geocoding.get_postcode_info(postcode)

        if not info:
            return []

        lat = info.get("latitude", 0)
        lon = info.get("longitude", 0)

        if include_nearby:
            return await self.search_by_radius(lat, lon, radius_meters)
        else:
            # Exact postcode match only
            if self.supabase:
                clean_postcode = postcode.upper().replace(" ", "")
                result = self.supabase.table("planning_decisions").select(
                    "*"
                ).ilike("postcode", f"{clean_postcode}%").limit(50).execute()

                if result.data:
                    return [
                        self._dict_to_result(d, lat, lon)
                        for d in result.data
                    ]

            return []

    async def search_by_ward(
        self,
        ward: str,
        limit: int = 100
    ) -> List[SpatialSearchResult]:
        """Search for applications in a specific ward"""
        if not self.supabase:
            return self._demo_ward_search(ward)

        try:
            result = self.supabase.table("planning_decisions").select(
                "*"
            ).ilike("ward", f"%{ward}%").order(
                "decision_date", desc=True
            ).limit(limit).execute()

            if result.data:
                ward_info = self.camden_wards.get(ward)
                center_lat = ward_info["lat"] if ward_info else 51.55
                center_lon = ward_info["lon"] if ward_info else -0.17

                return [
                    self._dict_to_result(d, center_lat, center_lon)
                    for d in result.data
                ]

        except Exception as e:
            logger.error(f"Ward search error: {e}")

        return []

    async def search_by_bounding_box(
        self,
        bbox: BoundingBox,
        limit: int = 100
    ) -> List[SpatialSearchResult]:
        """Search within a geographic bounding box"""
        if not self.supabase:
            return []

        try:
            result = self.supabase.rpc(
                "search_by_bbox",
                {
                    "min_lat": bbox.min_lat,
                    "max_lat": bbox.max_lat,
                    "min_lon": bbox.min_lon,
                    "max_lon": bbox.max_lon,
                    "result_limit": limit
                }
            ).execute()

            if result.data:
                center_lat = (bbox.min_lat + bbox.max_lat) / 2
                center_lon = (bbox.min_lon + bbox.max_lon) / 2

                return [
                    self._dict_to_result(d, center_lat, center_lon)
                    for d in result.data
                ]

        except Exception as e:
            logger.error(f"Bounding box search error: {e}")

        return []

    async def get_nearby_cases(
        self,
        case_reference: str,
        radius_meters: int = 200
    ) -> List[SpatialSearchResult]:
        """Find cases near an existing case"""
        if not self.supabase:
            return []

        try:
            # First get the case location
            case = self.supabase.table("planning_decisions").select(
                "latitude, longitude"
            ).eq("reference", case_reference).single().execute()

            if case.data and case.data.get("latitude"):
                return await self.search_by_radius(
                    center_lat=case.data["latitude"],
                    center_lon=case.data["longitude"],
                    radius_meters=radius_meters
                )

        except Exception as e:
            logger.error(f"Nearby cases error: {e}")

        return []

    def get_camden_wards(self) -> List[Dict]:
        """Get list of Camden wards with locations"""
        return [
            {
                "name": name,
                "latitude": coords["lat"],
                "longitude": coords["lon"]
            }
            for name, coords in self.camden_wards.items()
        ]

    def get_ward_for_location(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[str]:
        """Estimate which ward a location is in based on proximity"""
        min_distance = float('inf')
        closest_ward = None

        for ward, coords in self.camden_wards.items():
            distance = self.geocoding.calculate_distance(
                latitude, longitude, coords["lat"], coords["lon"]
            )
            if distance < min_distance:
                min_distance = distance
                closest_ward = ward

        return closest_ward

    def _dict_to_result(
        self,
        data: dict,
        center_lat: float,
        center_lon: float
    ) -> SpatialSearchResult:
        """Convert database record to result with distance"""
        lat = data.get("latitude", 0)
        lon = data.get("longitude", 0)

        distance = None
        if lat and lon:
            distance = self.geocoding.calculate_distance(
                center_lat, center_lon, lat, lon
            )

        return SpatialSearchResult(
            case_reference=data.get("reference", ""),
            address=data.get("address", ""),
            latitude=lat or 0,
            longitude=lon or 0,
            distance_meters=distance,
            postcode=data.get("postcode"),
            ward=data.get("ward"),
            description=data.get("description"),
            decision=data.get("outcome"),
            decision_date=data.get("decision_date"),
            development_type=data.get("development_type")
        )

    def _demo_radius_search(
        self,
        center_lat: float,
        center_lon: float,
        radius_meters: int
    ) -> List[SpatialSearchResult]:
        """Demo data for radius search"""
        # Sample data around Hampstead
        demo_cases = [
            {
                "reference": "2024/0123/P",
                "address": "15 Flask Walk, London NW3 1HJ",
                "latitude": 51.5568,
                "longitude": -0.1775,
                "postcode": "NW3 1HJ",
                "ward": "Hampstead Town",
                "description": "Single storey rear extension",
                "decision": "Granted",
                "development_type": "Householder"
            },
            {
                "reference": "2024/0156/P",
                "address": "28 Well Walk, London NW3 1BX",
                "latitude": 51.5572,
                "longitude": -0.1702,
                "postcode": "NW3 1BX",
                "ward": "Hampstead Town",
                "description": "Basement extension with lightwell",
                "decision": "Granted",
                "development_type": "Householder"
            },
            {
                "reference": "2024/0189/P",
                "address": "42 Church Row, London NW3 6UP",
                "latitude": 51.5548,
                "longitude": -0.1787,
                "postcode": "NW3 6UP",
                "ward": "Hampstead Town",
                "description": "Replacement windows in conservation area",
                "decision": "Granted",
                "development_type": "Listed Building"
            }
        ]

        results = []
        for case in demo_cases:
            distance = self.geocoding.calculate_distance(
                center_lat, center_lon,
                case["latitude"], case["longitude"]
            )

            if distance <= radius_meters:
                results.append(SpatialSearchResult(
                    case_reference=case["reference"],
                    address=case["address"],
                    latitude=case["latitude"],
                    longitude=case["longitude"],
                    distance_meters=distance,
                    postcode=case["postcode"],
                    ward=case["ward"],
                    description=case["description"],
                    decision=case["decision"],
                    development_type=case["development_type"]
                ))

        return sorted(results, key=lambda x: x.distance_meters or 0)

    def _demo_ward_search(self, ward: str) -> List[SpatialSearchResult]:
        """Demo data for ward search"""
        ward_lower = ward.lower()

        if "hampstead" in ward_lower:
            return self._demo_radius_search(51.5569, -0.1751, 2000)
        elif "belsize" in ward_lower:
            return self._demo_radius_search(51.5504, -0.1692, 2000)
        elif "frognal" in ward_lower:
            return self._demo_radius_search(51.5556, -0.1794, 2000)

        return []
