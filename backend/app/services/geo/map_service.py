"""
Map Service
Generates map data and visualization layers for planning applications
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MapLayerType(str, Enum):
    """Types of map layers"""
    PLANNING_APPLICATIONS = "planning_applications"
    APPROVED = "approved"
    REFUSED = "refused"
    PENDING = "pending"
    CONSERVATION_AREAS = "conservation_areas"
    LISTED_BUILDINGS = "listed_buildings"
    FLOOD_ZONES = "flood_zones"
    WARD_BOUNDARIES = "ward_boundaries"
    HEATMAP = "heatmap"


class MarkerStyle(str, Enum):
    """Marker display styles"""
    PIN = "pin"
    CIRCLE = "circle"
    CLUSTER = "cluster"
    HEATMAP = "heatmap"


@dataclass
class MapMarker:
    """A marker on the map"""
    id: str
    latitude: float
    longitude: float
    title: str
    description: Optional[str] = None
    style: MarkerStyle = MarkerStyle.PIN
    color: str = "#3B82F6"  # Default blue
    icon: Optional[str] = None
    popup_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapPolygon:
    """A polygon area on the map"""
    id: str
    name: str
    coordinates: List[List[float]]  # [[lat, lon], ...]
    fill_color: str = "#3B82F6"
    fill_opacity: float = 0.2
    stroke_color: str = "#1D4ED8"
    stroke_width: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapLayer:
    """A layer of map data"""
    id: str
    name: str
    layer_type: MapLayerType
    visible: bool = True
    markers: List[MapMarker] = field(default_factory=list)
    polygons: List[MapPolygon] = field(default_factory=list)
    heatmap_data: List[Dict[str, float]] = field(default_factory=list)
    min_zoom: int = 0
    max_zoom: int = 22
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapConfig:
    """Map configuration"""
    center_lat: float = 51.5504  # Default to Camden
    center_lon: float = -0.1692
    zoom: int = 13
    min_zoom: int = 10
    max_zoom: int = 18
    style: str = "streets"  # streets, satellite, dark, light
    show_scale: bool = True
    show_zoom_controls: bool = True
    layers: List[MapLayer] = field(default_factory=list)


class MapService:
    """Generates map data for visualization"""

    def __init__(self):
        # Color schemes for different outcomes
        self.outcome_colors = {
            "granted": "#22C55E",  # Green
            "approved": "#22C55E",
            "refused": "#EF4444",  # Red
            "withdrawn": "#F59E0B",  # Amber
            "pending": "#3B82F6",  # Blue
            "appeal allowed": "#10B981",  # Teal
            "appeal dismissed": "#DC2626",  # Dark red
        }

        # Development type icons
        self.development_icons = {
            "householder": "🏠",
            "extension": "📐",
            "basement": "⬇️",
            "loft": "⬆️",
            "change_of_use": "🔄",
            "new_build": "🏗️",
            "demolition": "🔨",
            "listed_building": "🏛️",
            "conservation": "🌳",
        }

        # Conservation areas in Camden (simplified boundaries)
        self.conservation_areas = self._load_conservation_areas()

    def create_planning_layer(
        self,
        cases: List[Dict],
        layer_type: MapLayerType = MapLayerType.PLANNING_APPLICATIONS
    ) -> MapLayer:
        """Create a map layer from planning cases"""
        markers = []

        for case in cases:
            lat = case.get("latitude")
            lon = case.get("longitude")

            if not lat or not lon:
                continue

            outcome = (case.get("outcome") or "pending").lower()
            color = self.outcome_colors.get(outcome, "#6B7280")

            dev_type = (case.get("development_type") or "").lower()
            icon = self.development_icons.get(dev_type, "📍")

            popup = self._create_popup_content(case)

            markers.append(MapMarker(
                id=case.get("reference", ""),
                latitude=lat,
                longitude=lon,
                title=case.get("address", "Unknown"),
                description=case.get("description", ""),
                color=color,
                icon=icon,
                popup_content=popup,
                metadata={
                    "reference": case.get("reference"),
                    "outcome": outcome,
                    "development_type": dev_type,
                    "decision_date": case.get("decision_date")
                }
            ))

        return MapLayer(
            id=f"layer_{layer_type.value}",
            name=layer_type.value.replace("_", " ").title(),
            layer_type=layer_type,
            markers=markers
        )

    def create_heatmap_layer(
        self,
        cases: List[Dict],
        weight_field: str = None
    ) -> MapLayer:
        """Create a heatmap layer showing application density"""
        heatmap_data = []

        for case in cases:
            lat = case.get("latitude")
            lon = case.get("longitude")

            if not lat or not lon:
                continue

            # Weight by outcome or custom field
            weight = 1.0
            if weight_field and weight_field in case:
                weight = float(case[weight_field])
            elif case.get("outcome", "").lower() == "granted":
                weight = 1.5  # Boost approved applications

            heatmap_data.append({
                "lat": lat,
                "lon": lon,
                "weight": weight
            })

        return MapLayer(
            id="heatmap",
            name="Application Density",
            layer_type=MapLayerType.HEATMAP,
            heatmap_data=heatmap_data
        )

    def create_ward_boundaries_layer(self) -> MapLayer:
        """Create layer with Camden ward boundaries"""
        polygons = []

        # Simplified ward boundaries (would use actual GeoJSON in production)
        for ward_name in self._get_ward_names():
            bounds = self._get_ward_bounds(ward_name)
            if bounds:
                polygons.append(MapPolygon(
                    id=f"ward_{ward_name.lower().replace(' ', '_')}",
                    name=ward_name,
                    coordinates=bounds,
                    fill_color="#3B82F6",
                    fill_opacity=0.1,
                    stroke_color="#1D4ED8",
                    metadata={"ward": ward_name}
                ))

        return MapLayer(
            id="ward_boundaries",
            name="Ward Boundaries",
            layer_type=MapLayerType.WARD_BOUNDARIES,
            polygons=polygons
        )

    def create_conservation_areas_layer(self) -> MapLayer:
        """Create layer with conservation area boundaries"""
        polygons = []

        for area in self.conservation_areas:
            polygons.append(MapPolygon(
                id=f"ca_{area['id']}",
                name=area["name"],
                coordinates=area.get("coordinates", []),
                fill_color="#22C55E",
                fill_opacity=0.15,
                stroke_color="#15803D",
                metadata={
                    "designation_date": area.get("designation_date"),
                    "description": area.get("description")
                }
            ))

        return MapLayer(
            id="conservation_areas",
            name="Conservation Areas",
            layer_type=MapLayerType.CONSERVATION_AREAS,
            polygons=polygons
        )

    def create_map_config(
        self,
        center_lat: float = None,
        center_lon: float = None,
        zoom: int = 13,
        layers: List[MapLayer] = None
    ) -> MapConfig:
        """Create full map configuration"""
        return MapConfig(
            center_lat=center_lat or 51.5504,
            center_lon=center_lon or -0.1692,
            zoom=zoom,
            layers=layers or []
        )

    def get_map_bounds(self, cases: List[Dict]) -> Dict:
        """Calculate bounding box to fit all cases"""
        lats = [c["latitude"] for c in cases if c.get("latitude")]
        lons = [c["longitude"] for c in cases if c.get("longitude")]

        if not lats or not lons:
            return {
                "min_lat": 51.5,
                "max_lat": 51.6,
                "min_lon": -0.2,
                "max_lon": -0.1
            }

        padding = 0.01  # Add some padding

        return {
            "min_lat": min(lats) - padding,
            "max_lat": max(lats) + padding,
            "min_lon": min(lons) - padding,
            "max_lon": max(lons) + padding
        }

    def _create_popup_content(self, case: Dict) -> str:
        """Create HTML content for map popup"""
        outcome = case.get("outcome", "Pending")
        outcome_color = self.outcome_colors.get(outcome.lower(), "#6B7280")

        return f"""
<div class="popup-content">
    <h3 class="font-bold">{case.get('reference', 'Unknown')}</h3>
    <p class="text-sm">{case.get('address', '')}</p>
    <p class="text-xs text-gray-500">{case.get('description', '')[:100]}...</p>
    <div class="mt-2">
        <span class="px-2 py-1 rounded text-white text-xs" style="background:{outcome_color}">
            {outcome}
        </span>
    </div>
    <p class="text-xs mt-1">
        <strong>Ward:</strong> {case.get('ward', 'Unknown')}<br>
        <strong>Type:</strong> {case.get('development_type', 'Unknown')}<br>
        <strong>Date:</strong> {case.get('decision_date', 'N/A')}
    </p>
</div>
"""

    def _load_conservation_areas(self) -> List[Dict]:
        """Load Camden conservation areas"""
        # Simplified data - would load from GeoJSON in production
        return [
            {
                "id": "hampstead",
                "name": "Hampstead Conservation Area",
                "designation_date": "1968",
                "description": "Historic village character with Georgian and Victorian architecture"
            },
            {
                "id": "hampstead_garden_suburb",
                "name": "Hampstead Garden Suburb",
                "designation_date": "1968",
                "description": "Arts and Crafts planned suburb"
            },
            {
                "id": "belsize",
                "name": "Belsize Conservation Area",
                "designation_date": "1978",
                "description": "Victorian and Edwardian residential character"
            },
            {
                "id": "fitzjohns",
                "name": "Fitzjohn's/Netherhall Conservation Area",
                "designation_date": "1980",
                "description": "Victorian mansion blocks and villas"
            },
            {
                "id": "bloomsbury",
                "name": "Bloomsbury Conservation Area",
                "designation_date": "1969",
                "description": "Georgian squares and terraces"
            }
        ]

    def _get_ward_names(self) -> List[str]:
        """Get list of Camden ward names"""
        return [
            "Belsize", "Bloomsbury", "Camden Town with Primrose Hill",
            "Cantelowes", "Fortune Green", "Frognal", "Gospel Oak",
            "Hampstead Town", "Haverstock", "Highgate",
            "Holborn and Covent Garden", "Kentish Town", "Kilburn",
            "King's Cross", "Regent's Park", "St Pancras and Somers Town",
            "Swiss Cottage", "West Hampstead"
        ]

    def _get_ward_bounds(self, ward_name: str) -> List[List[float]]:
        """Get simplified ward boundary coordinates"""
        # Would load actual GeoJSON boundaries in production
        # Returning empty for now
        return []

    def export_to_geojson(self, layer: MapLayer) -> Dict:
        """Export layer to GeoJSON format"""
        features = []

        # Add markers as points
        for marker in layer.markers:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [marker.longitude, marker.latitude]
                },
                "properties": {
                    "id": marker.id,
                    "title": marker.title,
                    "description": marker.description,
                    "color": marker.color,
                    **marker.metadata
                }
            })

        # Add polygons
        for polygon in layer.polygons:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon.coordinates]
                },
                "properties": {
                    "id": polygon.id,
                    "name": polygon.name,
                    "fill": polygon.fill_color,
                    "fill-opacity": polygon.fill_opacity,
                    "stroke": polygon.stroke_color,
                    "stroke-width": polygon.stroke_width,
                    **polygon.metadata
                }
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }
