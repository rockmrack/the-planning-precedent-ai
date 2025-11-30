"""
Analysis API endpoints for AI-powered planning arguments
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import structlog

from app.db.supabase_client import SupabaseDB, get_supabase_client
from app.services.embeddings import EmbeddingService
from app.services.llm import AnalysisService
from app.models.planning import (
    AnalysisRequest,
    AnalysisResponse,
    SearchQuery,
    SearchFilters,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_db() -> SupabaseDB:
    return SupabaseDB(get_supabase_client())


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_analysis_service() -> AnalysisService:
    return AnalysisService()


@router.post("/analyse", response_model=AnalysisResponse)
async def analyse_development(
    request: AnalysisRequest,
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Generate comprehensive planning analysis with AI-powered arguments.

    This endpoint:
    1. Finds relevant precedents for your proposed development
    2. Analyses the precedents using GPT-4o
    3. Generates professional planning arguments
    4. Provides risk assessment and recommendations

    The response includes:
    - Executive summary
    - Structured arguments with policy references
    - Officer quotes from successful applications
    - Risk assessment with mitigation suggestions
    - List of supporting precedents

    For best results, provide a detailed description of your proposal including:
    - Development type and scale
    - Materials and design approach
    - Site context (conservation area, listed building, etc.)
    - Any special circumstances
    """
    logger.info(
        "starting_analysis",
        query_length=len(request.query),
        address=request.address,
        ward=request.ward,
    )

    try:
        # Build search filters
        filters = SearchFilters()
        if request.ward:
            filters.wards = [request.ward]
        if request.conservation_area:
            filters.conservation_areas = [request.conservation_area]

        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)

        # Search for precedents
        precedents = await db.search_similar(
            query_embedding=query_embedding,
            filters=filters,
            limit=10,
            similarity_threshold=0.65,
            include_refused=request.include_counter_arguments,
        )

        if not precedents:
            raise HTTPException(
                status_code=404,
                detail="No relevant precedents found. Try broadening your search criteria."
            )

        # Generate analysis
        response = await analysis_service.analyse_precedents(request, precedents)

        logger.info(
            "analysis_completed",
            precedent_count=len(precedents),
            argument_count=len(response.arguments),
            confidence=response.risk_assessment.confidence_score,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyse/quick")
async def quick_analysis(
    query: str,
    ward: Optional[str] = None,
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Quick analysis for simple development queries.

    Returns a simplified analysis with key precedents and recommendations.
    For full analysis with detailed arguments, use POST /analyse.
    """
    if len(query) < 20:
        raise HTTPException(
            status_code=400,
            detail="Query too short. Please provide more details about your proposal."
        )

    request = AnalysisRequest(
        query=query,
        ward=ward,
        include_counter_arguments=False,
    )

    response = await analyse_development(
        request, db, embedding_service, analysis_service
    )

    # Return simplified response
    return {
        "summary": response.summary,
        "recommendation": response.recommendation,
        "approval_likelihood": response.risk_assessment.approval_likelihood,
        "confidence": response.risk_assessment.confidence_score,
        "key_precedents": [
            {
                "case_reference": p.decision.case_reference,
                "address": p.decision.address,
                "similarity": p.similarity_score,
            }
            for p in response.precedents_used[:5]
        ],
        "key_risks": response.risk_assessment.key_risks[:3],
    }


@router.post("/analyse/appeal")
async def generate_appeal_argument(
    case_reference: str,
    refusal_reasons: str,
    db: SupabaseDB = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Generate an appeal argument for a refused application.

    Uses precedent search to find similar applications that were APPROVED,
    then generates an argument based on inconsistent decision-making.

    This is particularly powerful because planning authorities must
    apply policies consistently - if they approved similar developments,
    they need to justify why yours was different.

    Args:
        case_reference: The case reference of your refused application
        refusal_reasons: The reasons given for refusal
    """
    # Get the refused decision
    decision = await db.get_decision_by_reference(case_reference)
    if not decision:
        raise HTTPException(status_code=404, detail="Case not found")

    # Search for similar APPROVED cases
    query_text = f"{decision.description} {refusal_reasons}"
    query_embedding = await embedding_service.generate_embedding(query_text)

    # Only search granted cases
    filters = SearchFilters()
    if decision.ward:
        filters.wards = [decision.ward]

    similar_approved = await db.search_similar(
        query_embedding=query_embedding,
        filters=filters,
        limit=10,
        similarity_threshold=0.6,
        include_refused=False,  # Only approved cases
    )

    if len(similar_approved) < 2:
        return {
            "warning": "Few similar approved precedents found",
            "precedents_found": len(similar_approved),
            "recommendation": "Consider design amendments before appeal",
        }

    # Generate appeal argument
    appeal_argument = await analysis_service.generate_appeal_argument(
        decision={
            "case_reference": case_reference,
            "address": decision.address,
            "description": decision.description,
            "refusal_reasons": refusal_reasons,
        },
        precedents=similar_approved,
    )

    return {
        "refused_case": {
            "reference": case_reference,
            "address": decision.address,
            "refusal_reasons": refusal_reasons,
        },
        "similar_approved_cases": [
            {
                "reference": p.decision.case_reference,
                "address": p.decision.address,
                "similarity": p.similarity_score,
                "decision_date": p.decision.decision_date.isoformat(),
            }
            for p in similar_approved
        ],
        "appeal_argument": appeal_argument,
        "strength_assessment": _assess_appeal_strength(similar_approved),
    }


def _assess_appeal_strength(precedents: list) -> dict:
    """Assess the strength of an appeal case"""
    if not precedents:
        return {
            "rating": "Weak",
            "score": 0.2,
            "reason": "No similar approved precedents found",
        }

    avg_similarity = sum(p.similarity_score for p in precedents) / len(precedents)
    recent_count = sum(
        1 for p in precedents
        if (2024 - p.decision.decision_date.year) <= 2
    )

    if avg_similarity > 0.8 and recent_count >= 3:
        return {
            "rating": "Strong",
            "score": 0.85,
            "reason": f"Found {recent_count} recent similar approvals with high similarity",
        }
    elif avg_similarity > 0.7 or recent_count >= 2:
        return {
            "rating": "Moderate",
            "score": 0.6,
            "reason": "Reasonable precedent support exists",
        }
    else:
        return {
            "rating": "Weak",
            "score": 0.35,
            "reason": "Limited precedent support - design amendments recommended",
        }


@router.post("/analyse/batch")
async def batch_analysis(
    queries: list[str],
    background_tasks: BackgroundTasks,
    db: SupabaseDB = Depends(get_db),
):
    """
    Submit multiple queries for batch analysis.

    Results are processed in the background and can be retrieved later.
    Useful for analysing multiple development options or sites.
    """
    if len(queries) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 queries per batch"
        )

    # Generate batch ID
    import uuid
    batch_id = str(uuid.uuid4())

    # Queue background processing
    # In production, this would use Celery
    background_tasks.add_task(
        _process_batch,
        batch_id,
        queries,
    )

    return {
        "batch_id": batch_id,
        "query_count": len(queries),
        "status": "processing",
        "message": "Results will be available at /analyse/batch/{batch_id}",
    }


async def _process_batch(batch_id: str, queries: list[str]):
    """Background task to process batch queries"""
    logger.info("processing_batch", batch_id=batch_id, count=len(queries))
    # Implementation would store results in cache/database
    pass
