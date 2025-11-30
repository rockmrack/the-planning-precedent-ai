"""
Maps and GIS API Routes
Geographic search and visualization endpoints
"""

from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.services.geo import (
    GeocodingService, SpatialSearchService, MapService,
    GeoLocation, MapLayer
)
from app.services.geo.spatial_search import BoundingBox, SpatialSearchResult
from app.services.geo.map_service import MapLayerType

router = APIRouter(prefix="/maps", tags=["Maps"])

# Initialize services
geocoding_service = GeocodingService()
spatial_service = SpatialSearchService()
map_service = MapService()


# Request/Response Models
class GeocodeRequest(BaseModel):
    """Geocoding request"""
    address: str = Field(..., min_length=5)


class GeocodeResponse(BaseModel):
    """Geocoding response"""
    success: bool
    latitude: Optional[float]
    longitude: Optional[float]
    formatted_address: Optional[str]
    postcode: Optional[str]
    ward: Optional[str]
    borough: Optional[str]
    confidence: Optional[float]


class RadiusSearchRequest(BaseModel):
    """Radius search request"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: int = Field(500, ge=100, le=5000)
    limit: int = Field(50, ge=1, le=200)


class AddressSearchRequest(BaseModel):
    """Address-based search request"""
    address: str = Field(..., min_length=5)
    radius_meters: int = Field(500, ge=100, le=5000)
    limit: int = Field(50, ge=1, le=200)


class SpatialResultResponse(BaseModel):
    """Spatial search result"""
    case_reference: str
    address: str
    latitude: float
    longitude: float
    distance_meters: Optional[float]
    postcode: Optional[str]
    ward: Optional[str]
    description: Optional[str]
    decision: Optional[str]
    decision_date: Optional[str]
    development_type: Optional[str]


class SpatialSearchResponse(BaseModel):
    """Spatial search response"""
    center: Optional[GeocodeResponse]
    results: List[SpatialResultResponse]
    total_count: int


class MapMarkerResponse(BaseModel):
    """Map marker"""
    id: str
    latitude: float
    longitude: float
    title: str
    description: Optional[str]
    color: str
    icon: Optional[str]
    popup_content: Optional[str]
    metadata: dict


class MapLayerResponse(BaseModel):
    """Map layer response"""
    id: str
    name: str
    layer_type: str
    visible: bool
    markers: List[MapMarkerResponse]
    marker_count: int


class MapConfigResponse(BaseModel):
    """Map configuration response"""
    center_lat: float
    center_lon: float
    zoom: int
    bounds: dict
    layers: List[MapLayerResponse]


class WardResponse(BaseModel):
    """Ward information"""
    name: str
    latitude: float
    longitude: float


# Geocoding endpoints
@router.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(request: GeocodeRequest):
    """
    Geocode an address to coordinates.

    Returns latitude, longitude, and additional location metadata
    for UK addresses.
    """
    result = await geocoding_service.geocode(request.address)

    if not result.success:
        return GeocodeResponse(
            success=False,
            latitude=None,
            longitude=None,
            formatted_address=None,
            postcode=None,
            ward=None,
            borough=None,
            confidence=None
        )

    location = result.location
    return GeocodeResponse(
        success=True,
        latitude=location.latitude,
        longitude=location.longitude,
        formatted_address=location.address,
        postcode=location.postcode,
        ward=location.ward,
        borough=location.borough,
        confidence=location.confidence
    )


@router.get("/reverse-geocode", response_model=GeocodeResponse)
async def reverse_geocode(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180)
):
    """
    Reverse geocode coordinates to an address.
    """
    result = await geocoding_service.reverse_geocode(latitude, longitude)

    if not result.success:
        return GeocodeResponse(
            success=False,
            latitude=latitude,
            longitude=longitude,
            formatted_address=None,
            postcode=None,
            ward=None,
            borough=None,
            confidence=None
        )

    location = result.location
    return GeocodeResponse(
        success=True,
        latitude=location.latitude,
        longitude=location.longitude,
        formatted_address=location.address,
        postcode=location.postcode,
        ward=location.ward,
        borough=location.borough,
        confidence=location.confidence
    )


@router.get("/postcode/{postcode}")
async def get_postcode_info(postcode: str):
    """
    Get detailed information about a UK postcode.
    """
    info = await geocoding_service.get_postcode_info(postcode)

    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Postcode not found"
        )

    return {
        "postcode": info.get("postcode"),
        "latitude": info.get("latitude"),
        "longitude": info.get("longitude"),
        "ward": info.get("admin_ward"),
        "borough": info.get("admin_district"),
        "region": info.get("region"),
        "constituency": info.get("parliamentary_constituency"),
        "lsoa": info.get("lsoa"),
        "msoa": info.get("msoa")
    }


# Spatial search endpoints
@router.post("/search/radius", response_model=SpatialSearchResponse)
async def search_by_radius(request: RadiusSearchRequest):
    """
    Search for planning applications within a radius of a point.
    """
    results = await spatial_service.search_by_radius(
        center_lat=request.latitude,
        center_lon=request.longitude,
        radius_meters=request.radius_meters,
        limit=request.limit
    )

    return SpatialSearchResponse(
        center=GeocodeResponse(
            success=True,
            latitude=request.latitude,
            longitude=request.longitude,
            formatted_address=None,
            postcode=None,
            ward=None,
            borough=None,
            confidence=1.0
        ),
        results=[_to_result_response(r) for r in results],
        total_count=len(results)
    )


@router.post("/search/address", response_model=SpatialSearchResponse)
async def search_by_address(request: AddressSearchRequest):
    """
    Search for planning applications near an address.

    First geocodes the address, then searches within the specified radius.
    """
    location, results = await spatial_service.search_by_address(
        address=request.address,
        radius_meters=request.radius_meters,
        limit=request.limit
    )

    if not location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not geocode address"
        )

    return SpatialSearchResponse(
        center=GeocodeResponse(
            success=True,
            latitude=location.latitude,
            longitude=location.longitude,
            formatted_address=location.address,
            postcode=location.postcode,
            ward=location.ward,
            borough=location.borough,
            confidence=location.confidence
        ),
        results=[_to_result_response(r) for r in results],
        total_count=len(results)
    )


@router.get("/search/postcode/{postcode}", response_model=SpatialSearchResponse)
async def search_by_postcode(
    postcode: str,
    radius_meters: int = Query(500, ge=100, le=2000),
    include_nearby: bool = True
):
    """
    Search for planning applications in or near a postcode.
    """
    results = await spatial_service.search_by_postcode(
        postcode=postcode,
        include_nearby=include_nearby,
        radius_meters=radius_meters
    )

    # Get postcode center
    info = await geocoding_service.get_postcode_info(postcode)

    center = None
    if info:
        center = GeocodeResponse(
            success=True,
            latitude=info.get("latitude"),
            longitude=info.get("longitude"),
            formatted_address=postcode.upper(),
            postcode=postcode.upper(),
            ward=info.get("admin_ward"),
            borough=info.get("admin_district"),
            confidence=1.0
        )

    return SpatialSearchResponse(
        center=center,
        results=[_to_result_response(r) for r in results],
        total_count=len(results)
    )


@router.get("/search/ward/{ward}", response_model=SpatialSearchResponse)
async def search_by_ward(
    ward: str,
    limit: int = Query(100, ge=1, le=500)
):
    """
    Search for planning applications in a specific ward.
    """
    results = await spatial_service.search_by_ward(ward, limit=limit)

    # Get ward center
    wards = spatial_service.get_camden_wards()
    ward_info = next((w for w in wards if w["name"].lower() == ward.lower()), None)

    center = None
    if ward_info:
        center = GeocodeResponse(
            success=True,
            latitude=ward_info["latitude"],
            longitude=ward_info["longitude"],
            formatted_address=ward,
            postcode=None,
            ward=ward,
            borough="Camden",
            confidence=1.0
        )

    return SpatialSearchResponse(
        center=center,
        results=[_to_result_response(r) for r in results],
        total_count=len(results)
    )


@router.get("/search/nearby/{case_reference}")
async def search_nearby_cases(
    case_reference: str,
    radius_meters: int = Query(200, ge=50, le=1000)
):
    """
    Find planning applications near an existing case.
    """
    results = await spatial_service.get_nearby_cases(
        case_reference=case_reference,
        radius_meters=radius_meters
    )

    return {
        "reference": case_reference,
        "radius_meters": radius_meters,
        "nearby_cases": [_to_result_response(r) for r in results],
        "count": len(results)
    }


# Map layer endpoints
@router.post("/layers/planning", response_model=MapLayerResponse)
async def create_planning_layer(cases: List[dict]):
    """
    Create a map layer from planning cases.
    """
    layer = map_service.create_planning_layer(cases)

    return MapLayerResponse(
        id=layer.id,
        name=layer.name,
        layer_type=layer.layer_type.value,
        visible=layer.visible,
        markers=[
            MapMarkerResponse(
                id=m.id,
                latitude=m.latitude,
                longitude=m.longitude,
                title=m.title,
                description=m.description,
                color=m.color,
                icon=m.icon,
                popup_content=m.popup_content,
                metadata=m.metadata
            )
            for m in layer.markers
        ],
        marker_count=len(layer.markers)
    )


@router.post("/layers/heatmap")
async def create_heatmap_layer(cases: List[dict]):
    """
    Create a heatmap layer showing application density.
    """
    layer = map_service.create_heatmap_layer(cases)

    return {
        "id": layer.id,
        "name": layer.name,
        "layer_type": layer.layer_type.value,
        "data_points": len(layer.heatmap_data),
        "heatmap_data": layer.heatmap_data
    }


@router.get("/layers/wards", response_model=MapLayerResponse)
async def get_ward_boundaries_layer():
    """
    Get map layer with Camden ward boundaries.
    """
    layer = map_service.create_ward_boundaries_layer()

    return MapLayerResponse(
        id=layer.id,
        name=layer.name,
        layer_type=layer.layer_type.value,
        visible=layer.visible,
        markers=[],
        marker_count=0
    )


@router.get("/layers/conservation-areas")
async def get_conservation_areas_layer():
    """
    Get map layer with conservation area boundaries.
    """
    layer = map_service.create_conservation_areas_layer()

    return {
        "id": layer.id,
        "name": layer.name,
        "layer_type": layer.layer_type.value,
        "areas": [
            {
                "id": p.id,
                "name": p.name,
                "fill_color": p.fill_color,
                "metadata": p.metadata
            }
            for p in layer.polygons
        ]
    }


# Reference data endpoints
@router.get("/wards", response_model=List[WardResponse])
async def get_camden_wards():
    """
    Get list of Camden wards with center coordinates.
    """
    wards = spatial_service.get_camden_wards()
    return [
        WardResponse(
            name=w["name"],
            latitude=w["latitude"],
            longitude=w["longitude"]
        )
        for w in wards
    ]


@router.get("/bounds")
async def get_camden_bounds():
    """
    Get bounding box for Camden borough.
    """
    return {
        "min_lat": 51.5072,
        "max_lat": 51.5712,
        "min_lon": -0.2136,
        "max_lon": -0.1036,
        "center_lat": 51.5392,
        "center_lon": -0.1586
    }


# Helper functions
def _to_result_response(result: SpatialSearchResult) -> SpatialResultResponse:
    """Convert spatial result to response model"""
    return SpatialResultResponse(
        case_reference=result.case_reference,
        address=result.address,
        latitude=result.latitude,
        longitude=result.longitude,
        distance_meters=result.distance_meters,
        postcode=result.postcode,
        ward=result.ward,
        description=result.description,
        decision=result.decision,
        decision_date=result.decision_date,
        development_type=result.development_type
    )
