"""
Pydantic models for planning decisions and API operations
Designed for UK planning system terminology and requirements
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class Outcome(str, Enum):
    """Planning decision outcomes"""
    GRANTED = "Granted"
    REFUSED = "Refused"
    WITHDRAWN = "Withdrawn"
    PENDING = "Pending"
    APPEAL_ALLOWED = "Appeal Allowed"
    APPEAL_DISMISSED = "Appeal Dismissed"


class DevelopmentType(str, Enum):
    """Common development types in Camden"""
    REAR_EXTENSION = "Rear Extension"
    SIDE_EXTENSION = "Side Extension"
    LOFT_CONVERSION = "Loft Conversion"
    DORMER_WINDOW = "Dormer Window"
    BASEMENT = "Basement/Subterranean"
    ROOF_EXTENSION = "Roof Extension"
    CHANGE_OF_USE = "Change of Use"
    NEW_BUILD = "New Build"
    DEMOLITION = "Demolition"
    ALTERATIONS = "Alterations"
    LISTED_BUILDING = "Listed Building Consent"
    CONSERVATION = "Conservation Area"
    TREE_WORKS = "Tree Works"
    ADVERTISEMENT = "Advertisement"
    OTHER = "Other"


class PropertyType(str, Enum):
    """Property types"""
    TERRACED = "Terraced House"
    SEMI_DETACHED = "Semi-Detached"
    DETACHED = "Detached"
    FLAT = "Flat/Maisonette"
    MANSION_BLOCK = "Mansion Block"
    COMMERCIAL = "Commercial"
    MIXED_USE = "Mixed Use"
    OTHER = "Other"


class ConservationAreaStatus(str, Enum):
    """Conservation area designations in Camden"""
    HAMPSTEAD = "Hampstead Conservation Area"
    BELSIZE = "Belsize Conservation Area"
    SOUTH_HAMPSTEAD = "South Hampstead Conservation Area"
    FITZJOHNS_NETHERHALL = "Fitzjohn's/Netherhall Conservation Area"
    REDINGTON_FROGNAL = "Redington Frognal Conservation Area"
    WEST_HAMPSTEAD = "West Hampstead Conservation Area"
    SWISS_COTTAGE = "Swiss Cottage Conservation Area"
    PRIMROSE_HILL = "Primrose Hill Conservation Area"
    CHALK_FARM = "Chalk Farm Conservation Area"
    CAMDEN_TOWN = "Camden Town Conservation Area"
    KENTISH_TOWN = "Kentish Town Conservation Area"
    BLOOMSBURY = "Bloomsbury Conservation Area"
    NONE = "None"


# Base Planning Decision Model
class PlanningDecisionBase(BaseModel):
    """Base model for planning decision data"""
    case_reference: str = Field(
        ...,
        description="Camden planning reference (e.g., 2023/1234/P)",
        pattern=r"^\d{4}/\d{4,5}/[A-Z]+$"
    )
    address: str = Field(..., min_length=5, max_length=500)
    ward: str = Field(..., description="Camden ward name")
    postcode: Optional[str] = Field(
        None,
        description="UK postcode",
        pattern=r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$"
    )
    decision_date: date
    outcome: Outcome
    application_type: str = Field(..., description="Type of planning application")
    development_type: Optional[DevelopmentType] = None
    property_type: Optional[PropertyType] = None
    description: str = Field(..., description="Development description")
    conservation_area: Optional[ConservationAreaStatus] = ConservationAreaStatus.NONE
    listed_building: bool = False
    article_4: bool = Field(False, description="Subject to Article 4 Direction")

    @field_validator("case_reference")
    @classmethod
    def validate_case_reference(cls, v: str) -> str:
        """Validate and normalise case reference format"""
        v = v.upper().strip()
        if not re.match(r"^\d{4}/\d{4,5}/[A-Z]+$", v):
            raise ValueError("Invalid case reference format")
        return v

    @field_validator("postcode")
    @classmethod
    def validate_postcode(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalise UK postcode"""
        if v is None:
            return None
        v = v.upper().strip().replace(" ", "")
        # Add space in correct position
        if len(v) >= 5:
            v = v[:-3] + " " + v[-3:]
        return v


class PlanningDecision(PlanningDecisionBase):
    """Planning decision for API responses"""
    id: int
    full_text: Optional[str] = None
    officer_report_url: Optional[str] = None
    decision_notice_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanningDecisionCreate(PlanningDecisionBase):
    """Model for creating new planning decision records"""
    full_text: str = Field(..., description="Full extracted text from documents")
    officer_report_url: Optional[str] = None
    decision_notice_url: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


class PlanningDecisionInDB(PlanningDecision):
    """Internal model with embedding data"""
    embedding: Optional[List[float]] = None
    chunk_count: int = 0


# Document Chunks
class DocumentChunk(BaseModel):
    """A chunk of text from a planning document"""
    id: Optional[int] = None
    decision_id: int
    chunk_index: int
    text: str
    token_count: int
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


# Search Models
class SearchFilters(BaseModel):
    """Filters for planning decision search"""
    wards: Optional[List[str]] = None
    outcome: Optional[Outcome] = None
    development_types: Optional[List[DevelopmentType]] = None
    property_types: Optional[List[PropertyType]] = None
    conservation_areas: Optional[List[ConservationAreaStatus]] = None
    listed_building_only: bool = False
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    postcode_prefix: Optional[str] = None


class SearchQuery(BaseModel):
    """Search query for finding precedents"""
    query: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language description of the proposed development"
    )
    filters: Optional[SearchFilters] = None
    limit: int = Field(10, ge=1, le=50)
    include_refused: bool = Field(
        False,
        description="Include refused applications for comparison"
    )
    similarity_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1)"
    )


class PrecedentMatch(BaseModel):
    """A matching precedent from the database"""
    decision: PlanningDecision
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    relevant_excerpt: str = Field(
        ...,
        description="Most relevant text excerpt from the decision"
    )
    matched_chunk_id: int
    key_policies: List[str] = Field(
        default_factory=list,
        description="Referenced planning policies"
    )


class SearchResult(BaseModel):
    """Search results with precedents"""
    query: str
    total_matches: int
    precedents: List[PrecedentMatch]
    search_time_ms: float
    filters_applied: Optional[SearchFilters] = None


# Analysis Models
class AnalysisRequest(BaseModel):
    """Request for AI-powered analysis"""
    query: str = Field(
        ...,
        min_length=20,
        description="Detailed description of proposed development"
    )
    address: Optional[str] = Field(None, description="Site address if known")
    ward: Optional[str] = None
    conservation_area: Optional[ConservationAreaStatus] = None
    include_counter_arguments: bool = Field(
        True,
        description="Include potential objection points"
    )
    case_references: Optional[List[str]] = Field(
        None,
        description="Specific cases to analyse"
    )


class ArgumentSection(BaseModel):
    """A section of the generated planning argument"""
    heading: str
    content: str
    supporting_cases: List[str] = Field(
        default_factory=list,
        description="Case references supporting this argument"
    )
    policy_references: List[str] = Field(
        default_factory=list,
        description="Planning policy references"
    )
    officer_quotes: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Direct quotes from officer reports"
    )


class RiskAssessment(BaseModel):
    """Risk assessment for the proposed development"""
    approval_likelihood: str = Field(
        ...,
        description="High/Medium/Low likelihood of approval"
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    key_risks: List[str] = Field(
        default_factory=list,
        description="Main risks to approval"
    )
    mitigation_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions to improve chances"
    )
    similar_refusals: List[str] = Field(
        default_factory=list,
        description="Similar applications that were refused"
    )


class AnalysisResponse(BaseModel):
    """AI-generated analysis response"""
    summary: str = Field(..., description="Executive summary")
    recommendation: str = Field(..., description="Overall recommendation")
    arguments: List[ArgumentSection]
    risk_assessment: RiskAssessment
    precedents_used: List[PrecedentMatch]
    policies_referenced: List[str]
    generated_at: datetime
    model_version: str


# Export Models
class ExportFormat(str, Enum):
    """Available export formats"""
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"


class ExportRequest(BaseModel):
    """Request to export analysis as document"""
    analysis_id: Optional[str] = None
    precedent_ids: Optional[List[int]] = None
    format: ExportFormat = ExportFormat.PDF
    include_full_reports: bool = False
    client_name: Optional[str] = None
    site_address: Optional[str] = None


class ExportResponse(BaseModel):
    """Response with export download information"""
    download_url: str
    filename: str
    format: ExportFormat
    expires_at: datetime
    file_size_bytes: int


# Reference Data Models
class WardInfo(BaseModel):
    """Information about a Camden ward"""
    name: str
    case_count: int
    approval_rate: float
    common_development_types: List[DevelopmentType]
    conservation_areas: List[str]


class DatabaseStats(BaseModel):
    """Database statistics"""
    total_decisions: int
    granted_count: int
    refused_count: int
    date_range_start: date
    date_range_end: date
    wards_covered: List[str]
    last_updated: datetime
    total_chunks: int


class CaseDetail(BaseModel):
    """Detailed view of a planning case"""
    decision: PlanningDecision
    full_text: str
    related_cases: List[PlanningDecision] = Field(
        default_factory=list,
        description="Cases at the same or nearby addresses"
    )
    similar_cases: List[PrecedentMatch] = Field(
        default_factory=list,
        description="Semantically similar cases"
    )
    key_policies: List[str]
    officer_conclusions: Optional[str] = None


# API Response Wrappers
class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated list response"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
