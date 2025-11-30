"""
Case detail API endpoints
"""

from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
import structlog

from app.db.supabase_client import SupabaseDB, get_supabase_client
from app.services.embeddings import EmbeddingService
from app.models.planning import (
    PlanningDecision,
    CaseDetail,
    SearchFilters,
    Outcome,
    DevelopmentType,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_db() -> SupabaseDB:
    return SupabaseDB(get_supabase_client())


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@router.get("/cases/{case_reference}")
async def get_case_detail(
    case_reference: str,
    include_similar: bool = Query(True, description="Include similar cases"),
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """
    Get detailed information about a specific planning case.

    Returns the full case details including:
    - Application details and outcome
    - Full extracted text from documents
    - Related cases at the same/nearby address
    - Similar cases (by content similarity)
    - Key policy references

    Args:
        case_reference: The Camden planning reference (e.g., 2023/1234/P)
        include_similar: Whether to include similar cases in response
    """
    decision = await db.get_decision_by_reference(case_reference)
    if not decision:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get full text from chunks
    chunks = await db.get_chunks_for_decision(decision.id)
    full_text = "\n\n".join(c.text for c in chunks) if chunks else ""

    # Find related cases at the same address
    related = []
    if decision.postcode:
        filters = SearchFilters(postcode_prefix=decision.postcode[:4])
        related_decisions, _ = await db.list_decisions(filters=filters, page_size=10)
        related = [
            d for d in related_decisions
            if d.case_reference != case_reference
        ][:5]

    # Find similar cases
    similar = []
    if include_similar and chunks:
        query_embedding = await embedding_service.generate_embedding(
            f"{decision.description} {chunks[0].text[:500]}"
        )
        similar = await db.search_similar(
            query_embedding=query_embedding,
            limit=6,
            similarity_threshold=0.65,
        )
        # Remove the current case from similar results
        similar = [s for s in similar if s.decision.case_reference != case_reference][:5]

    # Extract key policies from the text
    key_policies = _extract_policies(full_text)

    # Try to extract officer conclusions
    officer_conclusions = _extract_conclusions(full_text)

    return CaseDetail(
        decision=decision,
        full_text=full_text,
        related_cases=related,
        similar_cases=similar,
        key_policies=key_policies,
        officer_conclusions=officer_conclusions,
    )


@router.get("/cases")
async def list_cases(
    ward: Optional[str] = Query(None, description="Filter by ward"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    development_type: Optional[str] = Query(None, description="Filter by development type"),
    date_from: Optional[date] = Query(None, description="Decisions from this date"),
    date_to: Optional[date] = Query(None, description="Decisions up to this date"),
    conservation_area: bool = Query(False, description="Only conservation area cases"),
    listed_building: bool = Query(False, description="Only listed building cases"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: SupabaseDB = Depends(get_db),
):
    """
    List planning cases with filters.

    Supports pagination and multiple filters.
    Use this to browse the database or export data.
    """
    # Build filters
    filters = SearchFilters(
        date_from=date_from,
        date_to=date_to,
        listed_building_only=listed_building,
    )

    if ward:
        filters.wards = [ward]

    if outcome:
        try:
            filters.outcome = Outcome(outcome)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid outcome. Valid values: {[o.value for o in Outcome]}"
            )

    if development_type:
        try:
            filters.development_types = [DevelopmentType(development_type)]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid development type"
            )

    # Get cases
    decisions, total = await db.list_decisions(
        filters=filters,
        page=page,
        page_size=page_size,
    )

    return {
        "cases": decisions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/cases/{case_reference}/timeline")
async def get_case_timeline(
    case_reference: str,
    db: SupabaseDB = Depends(get_db),
):
    """
    Get the planning timeline for an address.

    Shows all planning applications at the same address,
    useful for understanding the planning history of a site.
    """
    decision = await db.get_decision_by_reference(case_reference)
    if not decision:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get all cases at this address
    all_decisions, _ = await db.list_decisions(page_size=100)

    # Filter by address similarity
    address_lower = decision.address.lower()
    timeline = [
        d for d in all_decisions
        if address_lower in d.address.lower()
        or d.address.lower() in address_lower
        or (d.postcode and decision.postcode and d.postcode == decision.postcode)
    ]

    # Sort by date
    timeline.sort(key=lambda x: x.decision_date)

    return {
        "address": decision.address,
        "postcode": decision.postcode,
        "timeline": [
            {
                "case_reference": d.case_reference,
                "date": d.decision_date.isoformat(),
                "description": d.description[:200],
                "outcome": d.outcome.value,
                "development_type": d.development_type.value if d.development_type else None,
            }
            for d in timeline
        ],
        "total_applications": len(timeline),
    }


@router.get("/cases/{case_reference}/documents")
async def get_case_documents(
    case_reference: str,
    db: SupabaseDB = Depends(get_db),
):
    """
    Get document links for a planning case.

    Returns URLs to original council documents where available.
    """
    decision = await db.get_decision_by_reference(case_reference)
    if not decision:
        raise HTTPException(status_code=404, detail="Case not found")

    documents = []

    if decision.decision_notice_url:
        documents.append({
            "type": "Decision Notice",
            "url": decision.decision_notice_url,
            "description": "The formal decision notice from Camden Council",
        })

    if decision.officer_report_url:
        documents.append({
            "type": "Officer Report",
            "url": decision.officer_report_url,
            "description": "The delegated report with officer assessment",
        })

    # Add link to council portal
    documents.append({
        "type": "Council Portal",
        "url": f"https://planningrecords.camden.gov.uk/Northgate/PlanningExplorer/Generic/StdDetails.aspx?PT=Planning%20Applications%20702&PARAM0={case_reference}",
        "description": "View on Camden Council's planning portal",
    })

    return {
        "case_reference": case_reference,
        "documents": documents,
    }


def _extract_policies(text: str) -> list[str]:
    """Extract policy references from case text"""
    import re

    policies = set()

    patterns = [
        (r"Policy\s+([A-Z]\d+)", "Camden Policy {}"),
        (r"NPPF\s+(?:paragraph\s+)?(\d+)", "NPPF paragraph {}"),
        (r"London\s+Plan\s+Policy\s+(\w+)", "London Plan Policy {}"),
        (r"Section\s+(\d+)", "Section {}"),
    ]

    for pattern, template in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            policies.add(template.format(match))

    return sorted(list(policies))[:20]


def _extract_conclusions(text: str) -> Optional[str]:
    """Extract officer conclusions from the case text"""
    import re

    # Look for conclusion section
    patterns = [
        r"(?:CONCLUSION|RECOMMENDATION)\s*[\n:]+\s*(.{100,500})",
        r"(?:In conclusion|To conclude|Therefore|Accordingly)[,\s]+(.{100,300})",
        r"(?:it is recommended|officers recommend)[^.]+\.(.{50,200})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            conclusion = match.group(1).strip()
            # Clean up
            conclusion = re.sub(r"\s+", " ", conclusion)
            return conclusion[:500]

    return None
