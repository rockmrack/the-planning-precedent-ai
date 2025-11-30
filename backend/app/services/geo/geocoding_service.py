"""
Geocoding Service
Converts addresses to coordinates and provides location context
"""

import logging
import re
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import httpx

logger = logging.getLogger(__name__)


class GeocodingProvider(str, Enum):
    """Geocoding providers"""
    POSTCODES_IO = "postcodes_io"  # Free UK postcode API
    NOMINATIM = "nominatim"  # OpenStreetMap
    OS_PLACES = "os_places"  # Ordnance Survey (UK)
    GOOGLE = "google"


@dataclass
class GeoLocation:
    """Geographic location with metadata"""
    latitude: float
    longitude: float
    address: str
    postcode: Optional[str] = None
    ward: Optional[str] = None
    borough: Optional[str] = None
    region: Optional[str] = None
    country: str = "United Kingdom"

    # Additional UK-specific data
    parish: Optional[str] = None
    constituency: Optional[str] = None
    lsoa: Optional[str] = None  # Lower Super Output Area
    msoa: Optional[str] = None  # Middle Super Output Area

    # Planning-specific
    conservation_area: Optional[str] = None
    listed_building_grade: Optional[str] = None
    flood_zone: Optional[str] = None

    # Confidence
    confidence: float = 1.0
    source: str = "unknown"


@dataclass
class GeocodingResult:
    """Result from geocoding operation"""
    success: bool
    location: Optional[GeoLocation] = None
    error: Optional[str] = None
    candidates: List[GeoLocation] = field(default_factory=list)


class GeocodingService:
    """Handles geocoding operations"""

    def __init__(self, providers: List[GeocodingProvider] = None):
        self.providers = providers or [
            GeocodingProvider.POSTCODES_IO,
            GeocodingProvider.NOMINATIM
        ]
        self.cache: Dict[str, GeoLocation] = {}

        # UK postcode regex
        self.postcode_pattern = re.compile(
            r'([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})',
            re.IGNORECASE
        )

    async def geocode(self, address: str) -> GeocodingResult:
        """
        Geocode an address to coordinates.
        Tries multiple providers for best results.
        """
        # Check cache
        cache_key = address.lower().strip()
        if cache_key in self.cache:
            return GeocodingResult(
                success=True,
                location=self.cache[cache_key]
            )

        # Extract postcode if present
        postcode_match = self.postcode_pattern.search(address)
        postcode = postcode_match.group(1).upper() if postcode_match else None

        # Try UK postcode API first if we have a postcode
        if postcode:
            result = await self._geocode_postcode(postcode, address)
            if result.success:
                self.cache[cache_key] = result.location
                return result

        # Try Nominatim (OpenStreetMap)
        result = await self._geocode_nominatim(address)
        if result.success:
            self.cache[cache_key] = result.location
            return result

        return GeocodingResult(
            success=False,
            error="Could not geocode address"
        )

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> GeocodingResult:
        """Convert coordinates to address"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={
                        "format": "json",
                        "lat": latitude,
                        "lon": longitude,
                        "addressdetails": 1
                    },
                    headers={"User-Agent": "PlanningPrecedentAI/1.0"}
                )

                if response.status_code == 200:
                    data = response.json()
                    address = data.get("display_name", "")
                    addr_details = data.get("address", {})

                    location = GeoLocation(
                        latitude=latitude,
                        longitude=longitude,
                        address=address,
                        postcode=addr_details.get("postcode"),
                        borough=addr_details.get("city_district") or addr_details.get("suburb"),
                        region=addr_details.get("state"),
                        source="nominatim"
                    )

                    return GeocodingResult(success=True, location=location)

        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")

        return GeocodingResult(
            success=False,
            error="Could not reverse geocode coordinates"
        )

    async def get_postcode_info(self, postcode: str) -> Optional[Dict]:
        """Get detailed information about a UK postcode"""
        clean_postcode = postcode.upper().replace(" ", "")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.postcodes.io/postcodes/{clean_postcode}"
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 200:
                        return data.get("result", {})

        except Exception as e:
            logger.error(f"Postcode lookup error: {e}")

        return None

    async def _geocode_postcode(
        self,
        postcode: str,
        full_address: str
    ) -> GeocodingResult:
        """Geocode using UK Postcodes.io API"""
        clean_postcode = postcode.upper().replace(" ", "")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.postcodes.io/postcodes/{clean_postcode}"
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 200:
                        result = data.get("result", {})

                        location = GeoLocation(
                            latitude=result.get("latitude", 0),
                            longitude=result.get("longitude", 0),
                            address=full_address,
                            postcode=result.get("postcode"),
                            ward=result.get("admin_ward"),
                            borough=result.get("admin_district"),
                            region=result.get("region"),
                            parish=result.get("parish"),
                            constituency=result.get("parliamentary_constituency"),
                            lsoa=result.get("lsoa"),
                            msoa=result.get("msoa"),
                            confidence=0.9,
                            source="postcodes.io"
                        )

                        return GeocodingResult(success=True, location=location)

        except Exception as e:
            logger.error(f"Postcodes.io error: {e}")

        return GeocodingResult(success=False)

    async def _geocode_nominatim(self, address: str) -> GeocodingResult:
        """Geocode using OpenStreetMap Nominatim"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": address,
                        "format": "json",
                        "addressdetails": 1,
                        "limit": 5,
                        "countrycodes": "gb"  # UK only
                    },
                    headers={"User-Agent": "PlanningPrecedentAI/1.0"},
                    timeout=10.0
                )

                if response.status_code == 200:
                    results = response.json()

                    if results:
                        candidates = []
                        for r in results:
                            addr = r.get("address", {})
                            loc = GeoLocation(
                                latitude=float(r.get("lat", 0)),
                                longitude=float(r.get("lon", 0)),
                                address=r.get("display_name", address),
                                postcode=addr.get("postcode"),
                                ward=addr.get("suburb"),
                                borough=addr.get("city_district"),
                                region=addr.get("state"),
                                confidence=float(r.get("importance", 0.5)),
                                source="nominatim"
                            )
                            candidates.append(loc)

                        return GeocodingResult(
                            success=True,
                            location=candidates[0],
                            candidates=candidates
                        )

        except Exception as e:
            logger.error(f"Nominatim error: {e}")

        return GeocodingResult(success=False)

    async def batch_geocode(
        self,
        addresses: List[str]
    ) -> List[GeocodingResult]:
        """Geocode multiple addresses in parallel"""
        tasks = [self.geocode(addr) for addr in addresses]
        return await asyncio.gather(*tasks)

    def calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two points in meters.
        Uses Haversine formula.
        """
        from math import radians, sin, cos, sqrt, atan2

        R = 6371000  # Earth's radius in meters

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def is_within_radius(
        self,
        center_lat: float,
        center_lon: float,
        point_lat: float,
        point_lon: float,
        radius_meters: float
    ) -> bool:
        """Check if a point is within radius of center"""
        distance = self.calculate_distance(
            center_lat, center_lon, point_lat, point_lon
        )
        return distance <= radius_meters

    async def get_nearby_postcodes(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 500
    ) -> List[str]:
        """Get nearby postcodes within radius"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.postcodes.io/postcodes",
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "radius": min(radius_meters, 2000)  # Max 2km
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 200:
                        return [
                            r.get("postcode")
                            for r in data.get("result", [])
                            if r.get("postcode")
                        ]

        except Exception as e:
            logger.error(f"Nearby postcodes error: {e}")

        return []

    async def validate_uk_address(self, address: str) -> Tuple[bool, str]:
        """
        Validate if an address is in the UK and well-formed.
        Returns (is_valid, message)
        """
        result = await self.geocode(address)

        if not result.success:
            return False, "Could not validate address"

        location = result.location

        # Check if in UK
        if location.country != "United Kingdom":
            return False, "Address is not in the United Kingdom"

        # Check for required fields
        if not location.postcode:
            return False, "Could not identify postcode"

        return True, "Address validated successfully"
