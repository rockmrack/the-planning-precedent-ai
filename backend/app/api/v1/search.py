"""
Search API endpoints for precedent discovery
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
import structlog

from app.db.supabase_client import SupabaseDB, get_supabase_client
from app.services.embeddings import EmbeddingService
from app.models.planning import (
    SearchQuery,
    SearchResult,
    PrecedentMatch,
    SearchFilters,
    Outcome,
    DevelopmentType,
    ConservationAreaStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_db() -> SupabaseDB:
    """Dependency for database access"""
    return SupabaseDB(get_supabase_client())


def get_embedding_service() -> EmbeddingService:
    """Dependency for embedding service"""
    return EmbeddingService()


@router.post("/search", response_model=SearchResult)
async def search_precedents(
    query: SearchQuery,
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """
    Search for planning precedents using semantic similarity.

    This endpoint:
    1. Converts your query into a vector embedding
    2. Searches the database for similar planning decisions
    3. Returns matching precedents ranked by relevance

    The query should describe your proposed development in natural language.
    For best results, include details about:
    - Type of development (extension, dormer, basement, etc.)
    - Location context (conservation area, street name)
    - Materials and design approach
    - Scale and dimensions

    Example query:
    "Rear dormer window in Hampstead Conservation Area, zinc cladding, set back 1m from eaves"
    """
    start_time = datetime.utcnow()

    try:
        # Generate embedding for the query
        query_embedding = await embedding_service.generate_embedding(query.query)

        # Search for similar precedents
        precedents = await db.search_similar(
            query_embedding=query_embedding,
            filters=query.filters,
            limit=query.limit,
            similarity_threshold=query.similarity_threshold,
            include_refused=query.include_refused,
        )

        # Calculate search time
        search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            "search_completed",
            query_length=len(query.query),
            results_count=len(precedents),
            search_time_ms=search_time_ms,
        )

        return SearchResult(
            query=query.query,
            total_matches=len(precedents),
            precedents=precedents,
            search_time_ms=search_time_ms,
            filters_applied=query.filters,
        )

    except Exception as e:
        logger.error("search_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search/quick")
async def quick_search(
    q: str = Query(..., min_length=5, description="Search query"),
    ward: Optional[str] = Query(None, description="Filter by ward"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (Granted/Refused)"),
    limit: int = Query(5, ge=1, le=20),
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """
    Quick search endpoint for simpler queries.

    Use this for fast searches with basic filters.
    For more advanced filtering, use POST /search.
    """
    filters = SearchFilters()
    if ward:
        filters.wards = [ward]
    if outcome:
        try:
            filters.outcome = Outcome(outcome)
        except ValueError:
            pass

    query = SearchQuery(
        query=q,
        filters=filters,
        limit=limit,
    )

    return await search_precedents(query, db, embedding_service)


@router.get("/search/by-address")
async def search_by_address(
    address: str = Query(..., min_length=5, description="Property address or postcode"),
    radius_metres: int = Query(500, ge=100, le=2000),
    db: SupabaseDB = Depends(get_db),
):
    """
    Search for planning decisions near a specific address.

    Returns decisions for the exact address and nearby properties.
    Useful for understanding the planning history of a site.
    """
    # Search for exact address matches
    decisions, total = await db.list_decisions(
        filters=SearchFilters(postcode_prefix=address[:4] if len(address) >= 4 else None),
        page=1,
        page_size=20,
    )

    # Filter by address similarity
    address_lower = address.lower()
    matching = [
        d for d in decisions
        if address_lower in d.address.lower()
        or d.address.lower() in address_lower
    ]

    return {
        "address_searched": address,
        "exact_matches": matching[:5],
        "nearby_decisions": [d for d in decisions if d not in matching][:10],
        "total_found": total,
    }


@router.get("/search/similar-to/{case_reference}")
async def find_similar_cases(
    case_reference: str,
    limit: int = Query(10, ge=1, le=20),
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """
    Find cases similar to a specific planning decision.

    Useful for:
    - Finding additional precedents
    - Understanding how similar applications were handled
    - Building an appeal case based on inconsistency
    """
    # Get the original decision
    decision = await db.get_decision_by_reference(case_reference)
    if not decision:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get the chunks for this decision
    chunks = await db.get_chunks_for_decision(decision.id)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Case has no indexed content for similarity search"
        )

    # Use the decision's description and full text for similarity search
    search_text = f"{decision.description} {chunks[0].text if chunks else ''}"
    query_embedding = await embedding_service.generate_embedding(search_text[:2000])

    # Find similar cases (excluding the original)
    similar = await db.search_similar(
        query_embedding=query_embedding,
        limit=limit + 1,  # Get one extra in case original is included
        similarity_threshold=0.6,
    )

    # Remove the original case from results
    similar = [s for s in similar if s.decision.case_reference != case_reference][:limit]

    return {
        "original_case": decision,
        "similar_cases": similar,
    }


@router.get("/search/development-types")
async def list_development_types():
    """
    List available development type filters.

    Returns all development types that can be used for filtering searches.
    """
    return {
        "development_types": [
            {
                "value": dt.value,
                "name": dt.name,
                "description": _get_dev_type_description(dt),
            }
            for dt in DevelopmentType
        ]
    }


@router.get("/search/conservation-areas")
async def list_conservation_areas():
    """
    List Camden conservation areas for filtering.

    Conservation areas have special planning considerations.
    Searches can be filtered to specific conservation areas.
    """
    return {
        "conservation_areas": [
            {"value": ca.value, "name": ca.name}
            for ca in ConservationAreaStatus
            if ca != ConservationAreaStatus.NONE
        ]
    }


def _get_dev_type_description(dev_type: DevelopmentType) -> str:
    """Get description for a development type"""
    descriptions = {
        DevelopmentType.REAR_EXTENSION: "Extensions to the rear of a property",
        DevelopmentType.SIDE_EXTENSION: "Extensions to the side, including side returns",
        DevelopmentType.LOFT_CONVERSION: "Conversion of roof space, including dormers",
        DevelopmentType.DORMER_WINDOW: "Dormer windows and rooflights",
        DevelopmentType.BASEMENT: "Basement and subterranean development",
        DevelopmentType.ROOF_EXTENSION: "Roof extensions and mansard additions",
        DevelopmentType.CHANGE_OF_USE: "Change of use applications",
        DevelopmentType.NEW_BUILD: "New buildings and dwellings",
        DevelopmentType.DEMOLITION: "Demolition applications",
        DevelopmentType.ALTERATIONS: "Internal and external alterations",
        DevelopmentType.LISTED_BUILDING: "Listed building consent applications",
        DevelopmentType.TREE_WORKS: "Tree works and TPO applications",
        DevelopmentType.ADVERTISEMENT: "Advertisement and signage consent",
        DevelopmentType.OTHER: "Other development types",
    }
    return descriptions.get(dev_type, "")
