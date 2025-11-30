"""
Reference data API endpoints
Statistics, wards, and system information
"""

from fastapi import APIRouter, Depends
import structlog

from app.db.supabase_client import SupabaseDB, get_supabase_client
from app.models.planning import DatabaseStats, WardInfo

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_db() -> SupabaseDB:
    return SupabaseDB(get_supabase_client())


@router.get("/stats", response_model=DatabaseStats)
async def get_database_stats(
    db: SupabaseDB = Depends(get_db),
):
    """
    Get statistics about the planning database.

    Returns:
    - Total number of decisions
    - Granted vs refused counts
    - Date range covered
    - Wards included
    - Total indexed chunks
    """
    return await db.get_stats()


@router.get("/wards")
async def list_wards(
    db: SupabaseDB = Depends(get_db),
):
    """
    List all wards with case counts and approval rates.

    Useful for:
    - Understanding which areas have most precedent data
    - Comparing approval rates across wards
    - Filtering searches by area
    """
    stats = await db.get_stats()

    ward_details = []
    for ward in stats.wards_covered:
        ward_info = await db.get_ward_stats(ward)
        if ward_info:
            ward_details.append({
                "name": ward_info.name,
                "case_count": ward_info.case_count,
                "approval_rate": f"{ward_info.approval_rate:.1%}",
                "common_developments": ward_info.common_development_types[:5],
                "conservation_areas": ward_info.conservation_areas,
            })

    # Sort by case count
    ward_details.sort(key=lambda x: x["case_count"], reverse=True)

    return {
        "wards": ward_details,
        "total_wards": len(ward_details),
    }


@router.get("/wards/{ward_name}")
async def get_ward_detail(
    ward_name: str,
    db: SupabaseDB = Depends(get_db),
):
    """
    Get detailed statistics for a specific ward.
    """
    ward_info = await db.get_ward_stats(ward_name)

    if not ward_info:
        return {"error": "Ward not found", "available_wards": (await db.get_stats()).wards_covered}

    return {
        "ward": ward_info.name,
        "statistics": {
            "total_cases": ward_info.case_count,
            "approval_rate": ward_info.approval_rate,
            "common_development_types": ward_info.common_development_types,
            "conservation_areas": ward_info.conservation_areas,
        }
    }


@router.get("/policies")
async def list_planning_policies():
    """
    Reference list of relevant planning policies.

    Returns key policies from:
    - Camden Local Plan 2017
    - London Plan 2021
    - NPPF 2023

    Useful for understanding policy context in search results.
    """
    return {
        "camden_local_plan": {
            "title": "Camden Local Plan 2017",
            "key_policies": [
                {
                    "code": "D1",
                    "title": "Design",
                    "summary": "All development should be of high quality design that responds positively to local context."
                },
                {
                    "code": "D2",
                    "title": "Heritage",
                    "summary": "Development should preserve and enhance Camden's heritage assets."
                },
                {
                    "code": "D3",
                    "title": "Residential Extensions and Alterations",
                    "summary": "Extensions should be subordinate and respect the character of the property."
                },
                {
                    "code": "A1",
                    "title": "Managing the Impact of Development",
                    "summary": "Development should not cause unacceptable harm to amenity."
                },
                {
                    "code": "A2",
                    "title": "Open Space",
                    "summary": "Protection of open spaces and gardens."
                },
                {
                    "code": "H1",
                    "title": "Maximising Housing Supply",
                    "summary": "Encouraging new housing including through extensions."
                },
            ]
        },
        "london_plan": {
            "title": "London Plan 2021",
            "key_policies": [
                {
                    "code": "D3",
                    "title": "Optimising Site Capacity",
                    "summary": "Development should make best use of land."
                },
                {
                    "code": "D4",
                    "title": "Delivering Good Design",
                    "summary": "Design quality is essential for sustainable development."
                },
                {
                    "code": "HC1",
                    "title": "Heritage Conservation",
                    "summary": "Heritage assets should be conserved and enhanced."
                },
            ]
        },
        "nppf": {
            "title": "National Planning Policy Framework 2023",
            "key_paragraphs": [
                {
                    "paragraph": "130",
                    "summary": "Good design is a key aspect of sustainable development."
                },
                {
                    "paragraph": "199",
                    "summary": "Great weight should be given to conservation of heritage assets."
                },
                {
                    "paragraph": "200",
                    "summary": "Significance of heritage assets can be harmed through development."
                },
                {
                    "paragraph": "202",
                    "summary": "Less than substantial harm should be weighed against public benefits."
                },
            ]
        },
        "supplementary_guidance": [
            {
                "title": "Camden Planning Guidance: Residential Extensions and Alterations",
                "description": "Detailed guidance on acceptable design for residential extensions."
            },
            {
                "title": "Camden Conservation Area Statements",
                "description": "Character assessments for each conservation area."
            },
            {
                "title": "Camden Basement Development SPD",
                "description": "Specific guidance for subterranean development."
            },
        ]
    }


@router.get("/conservation-areas")
async def list_conservation_areas():
    """
    List Camden's conservation areas with key information.

    Conservation areas have enhanced protection and stricter design requirements.
    """
    return {
        "conservation_areas": [
            {
                "name": "Hampstead Conservation Area",
                "designation_date": "1967",
                "character": "Historic village character with Georgian and Victorian properties",
                "key_considerations": [
                    "Village character preservation",
                    "Traditional materials",
                    "Modest extensions only",
                    "Protection of trees and gardens"
                ]
            },
            {
                "name": "Belsize Conservation Area",
                "designation_date": "1973",
                "character": "Victorian and Edwardian residential streets",
                "key_considerations": [
                    "Unified streetscape",
                    "Original architectural features",
                    "Front garden retention",
                    "Roof profile preservation"
                ]
            },
            {
                "name": "Redington Frognal Conservation Area",
                "designation_date": "1978",
                "character": "Large detached houses in substantial gardens",
                "key_considerations": [
                    "Spacious character",
                    "Garden settings",
                    "Individual architectural quality",
                    "Tree preservation"
                ]
            },
            {
                "name": "Fitzjohn's/Netherhall Conservation Area",
                "designation_date": "1980",
                "character": "Mixed Victorian development with artist studios",
                "key_considerations": [
                    "Artistic heritage",
                    "Mixed character",
                    "Original features"
                ]
            },
            {
                "name": "South Hampstead Conservation Area",
                "designation_date": "1985",
                "character": "Victorian terraces and semi-detached houses",
                "key_considerations": [
                    "Consistency of scale",
                    "Original features",
                    "Front boundaries"
                ]
            },
            {
                "name": "Swiss Cottage Conservation Area",
                "designation_date": "1990",
                "character": "Mixed period properties around Swiss Cottage",
                "key_considerations": [
                    "Diverse character",
                    "Landmark buildings",
                    "Public realm"
                ]
            },
        ],
        "general_guidance": {
            "extensions": "Must preserve or enhance the character and appearance of the conservation area",
            "materials": "Traditional or high-quality contemporary materials appropriate to context",
            "demolition": "Requires conservation area consent with strong justification",
            "trees": "Six weeks' notice required for tree works"
        }
    }


@router.get("/health")
async def health_check(db: SupabaseDB = Depends(get_db)):
    """
    System health check endpoint.

    Returns status of all system components.
    """
    try:
        stats = await db.get_stats()
        db_status = "healthy"
        db_message = f"{stats.total_decisions} decisions indexed"
    except Exception as e:
        db_status = "unhealthy"
        db_message = str(e)

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "components": {
            "database": {
                "status": db_status,
                "message": db_message,
            },
            "api": {
                "status": "healthy",
                "version": "1.0.0",
            }
        },
        "timestamp": "2024-01-01T00:00:00Z",  # Would use actual time
    }
