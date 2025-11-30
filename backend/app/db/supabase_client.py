"""
Supabase database client with vector search capabilities
Handles all database operations for planning decisions
"""

from datetime import date, datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from supabase import create_client, Client
import structlog

from app.core.config import settings
from app.models.planning import (
    PlanningDecision,
    PlanningDecisionCreate,
    PrecedentMatch,
    SearchFilters,
    Outcome,
    DatabaseStats,
    WardInfo,
    DocumentChunk,
)

logger = structlog.get_logger(__name__)


@lru_cache()
def get_supabase_client() -> Client:
    """Get cached Supabase client instance"""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )


async def get_async_supabase_client() -> Client:
    """Get Supabase client for async operations"""
    return get_supabase_client()


class SupabaseDB:
    """
    Database operations for planning decisions using Supabase with pgvector.
    Provides methods for CRUD operations and vector similarity search.
    """

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    # ==================== Planning Decisions ====================

    async def create_decision(
        self,
        decision: PlanningDecisionCreate
    ) -> PlanningDecision:
        """Create a new planning decision record"""
        data = decision.model_dump(exclude_none=True)
        data["decision_date"] = data["decision_date"].isoformat()

        result = self.client.table("planning_decisions").insert(data).execute()

        if not result.data:
            raise Exception("Failed to create planning decision")

        logger.info(
            "created_planning_decision",
            case_reference=decision.case_reference
        )
        return PlanningDecision(**result.data[0])

    async def get_decision_by_reference(
        self,
        case_reference: str
    ) -> Optional[PlanningDecision]:
        """Get a planning decision by its case reference"""
        result = (
            self.client.table("planning_decisions")
            .select("*")
            .eq("case_reference", case_reference)
            .execute()
        )

        if result.data:
            return PlanningDecision(**result.data[0])
        return None

    async def get_decision_by_id(self, decision_id: int) -> Optional[PlanningDecision]:
        """Get a planning decision by ID"""
        result = (
            self.client.table("planning_decisions")
            .select("*")
            .eq("id", decision_id)
            .execute()
        )

        if result.data:
            return PlanningDecision(**result.data[0])
        return None

    async def update_decision(
        self,
        decision_id: int,
        updates: Dict[str, Any]
    ) -> Optional[PlanningDecision]:
        """Update an existing planning decision"""
        updates["updated_at"] = datetime.utcnow().isoformat()

        result = (
            self.client.table("planning_decisions")
            .update(updates)
            .eq("id", decision_id)
            .execute()
        )

        if result.data:
            return PlanningDecision(**result.data[0])
        return None

    async def delete_decision(self, decision_id: int) -> bool:
        """Delete a planning decision and its chunks"""
        # Delete chunks first
        self.client.table("document_chunks").delete().eq(
            "decision_id", decision_id
        ).execute()

        # Delete the decision
        result = (
            self.client.table("planning_decisions")
            .delete()
            .eq("id", decision_id)
            .execute()
        )

        return bool(result.data)

    async def decision_exists(self, case_reference: str) -> bool:
        """Check if a decision already exists"""
        result = (
            self.client.table("planning_decisions")
            .select("id")
            .eq("case_reference", case_reference)
            .execute()
        )
        return bool(result.data)

    async def list_decisions(
        self,
        filters: Optional[SearchFilters] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[PlanningDecision], int]:
        """List planning decisions with filters and pagination"""
        query = self.client.table("planning_decisions").select("*", count="exact")

        if filters:
            if filters.wards:
                query = query.in_("ward", filters.wards)
            if filters.outcome:
                query = query.eq("outcome", filters.outcome.value)
            if filters.development_types:
                dev_types = [dt.value for dt in filters.development_types]
                query = query.in_("development_type", dev_types)
            if filters.conservation_areas:
                ca_values = [ca.value for ca in filters.conservation_areas]
                query = query.in_("conservation_area", ca_values)
            if filters.listed_building_only:
                query = query.eq("listed_building", True)
            if filters.date_from:
                query = query.gte("decision_date", filters.date_from.isoformat())
            if filters.date_to:
                query = query.lte("decision_date", filters.date_to.isoformat())

        # Pagination
        offset = (page - 1) * page_size
        query = query.order("decision_date", desc=True).range(
            offset, offset + page_size - 1
        )

        result = query.execute()

        decisions = [PlanningDecision(**d) for d in result.data]
        total = result.count or 0

        return decisions, total

    # ==================== Document Chunks ====================

    async def create_chunks(
        self,
        decision_id: int,
        chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """Create document chunks with embeddings"""
        chunk_data = []
        for chunk in chunks:
            data = chunk.model_dump(exclude_none=True)
            data["decision_id"] = decision_id
            chunk_data.append(data)

        result = self.client.table("document_chunks").insert(chunk_data).execute()

        logger.info(
            "created_document_chunks",
            decision_id=decision_id,
            chunk_count=len(chunks)
        )

        return [DocumentChunk(**c) for c in result.data]

    async def get_chunks_for_decision(
        self,
        decision_id: int
    ) -> List[DocumentChunk]:
        """Get all chunks for a decision"""
        result = (
            self.client.table("document_chunks")
            .select("*")
            .eq("decision_id", decision_id)
            .order("chunk_index")
            .execute()
        )

        return [DocumentChunk(**c) for c in result.data]

    # ==================== Vector Search ====================

    async def search_similar(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        include_refused: bool = False
    ) -> List[PrecedentMatch]:
        """
        Search for similar planning decisions using vector similarity.
        Uses Supabase's pgvector extension for cosine similarity search.
        """
        # Build the RPC function call for vector search
        params = {
            "query_embedding": query_embedding,
            "match_threshold": similarity_threshold,
            "match_count": limit * 2,  # Get more to filter
        }

        # Add filters
        if filters:
            if filters.wards:
                params["filter_wards"] = filters.wards
            if filters.date_from:
                params["filter_date_from"] = filters.date_from.isoformat()
            if filters.date_to:
                params["filter_date_to"] = filters.date_to.isoformat()
            if filters.development_types:
                params["filter_development_types"] = [
                    dt.value for dt in filters.development_types
                ]
            if filters.conservation_areas:
                params["filter_conservation_areas"] = [
                    ca.value for ca in filters.conservation_areas
                ]

        if not include_refused:
            params["filter_outcome"] = Outcome.GRANTED.value

        # Call the vector search RPC function
        result = self.client.rpc("search_planning_decisions", params).execute()

        if not result.data:
            return []

        # Process results into PrecedentMatch objects
        matches = []
        seen_decisions = set()

        for row in result.data:
            decision_id = row["decision_id"]

            # Deduplicate by decision
            if decision_id in seen_decisions:
                continue
            seen_decisions.add(decision_id)

            if len(matches) >= limit:
                break

            # Get full decision data
            decision = await self.get_decision_by_id(decision_id)
            if not decision:
                continue

            match = PrecedentMatch(
                decision=decision,
                similarity_score=row["similarity"],
                relevant_excerpt=row["chunk_text"][:500],
                matched_chunk_id=row["chunk_id"],
                key_policies=self._extract_policies(row.get("chunk_text", ""))
            )
            matches.append(match)

        logger.info(
            "vector_search_completed",
            matches_found=len(matches),
            threshold=similarity_threshold
        )

        return matches

    def _extract_policies(self, text: str) -> List[str]:
        """Extract policy references from text"""
        import re

        policies = []

        # Camden Local Plan policies (e.g., "Policy H1", "Policy D1")
        local_plan = re.findall(r"Policy\s+[A-Z]\d+", text, re.IGNORECASE)
        policies.extend(local_plan)

        # NPPF references
        nppf = re.findall(r"NPPF\s+(?:paragraph\s+)?\d+", text, re.IGNORECASE)
        policies.extend(nppf)

        # London Plan policies
        london_plan = re.findall(r"London\s+Plan\s+Policy\s+\w+", text, re.IGNORECASE)
        policies.extend(london_plan)

        return list(set(policies))[:10]

    # ==================== Statistics ====================

    async def get_stats(self) -> DatabaseStats:
        """Get database statistics"""
        # Total decisions
        total_result = (
            self.client.table("planning_decisions")
            .select("id", count="exact")
            .execute()
        )
        total = total_result.count or 0

        # Granted count
        granted_result = (
            self.client.table("planning_decisions")
            .select("id", count="exact")
            .eq("outcome", Outcome.GRANTED.value)
            .execute()
        )
        granted = granted_result.count or 0

        # Refused count
        refused_result = (
            self.client.table("planning_decisions")
            .select("id", count="exact")
            .eq("outcome", Outcome.REFUSED.value)
            .execute()
        )
        refused = refused_result.count or 0

        # Date range
        date_result = (
            self.client.table("planning_decisions")
            .select("decision_date")
            .order("decision_date", desc=False)
            .limit(1)
            .execute()
        )
        date_start = (
            date.fromisoformat(date_result.data[0]["decision_date"])
            if date_result.data else date.today()
        )

        date_end_result = (
            self.client.table("planning_decisions")
            .select("decision_date")
            .order("decision_date", desc=True)
            .limit(1)
            .execute()
        )
        date_end = (
            date.fromisoformat(date_end_result.data[0]["decision_date"])
            if date_end_result.data else date.today()
        )

        # Wards
        wards_result = (
            self.client.table("planning_decisions")
            .select("ward")
            .execute()
        )
        wards = list(set(r["ward"] for r in wards_result.data if r.get("ward")))

        # Total chunks
        chunks_result = (
            self.client.table("document_chunks")
            .select("id", count="exact")
            .execute()
        )
        total_chunks = chunks_result.count or 0

        return DatabaseStats(
            total_decisions=total,
            granted_count=granted,
            refused_count=refused,
            date_range_start=date_start,
            date_range_end=date_end,
            wards_covered=sorted(wards),
            last_updated=datetime.utcnow(),
            total_chunks=total_chunks
        )

    async def get_ward_stats(self, ward: str) -> Optional[WardInfo]:
        """Get statistics for a specific ward"""
        # Get all decisions for the ward
        result = (
            self.client.table("planning_decisions")
            .select("*")
            .eq("ward", ward)
            .execute()
        )

        if not result.data:
            return None

        decisions = result.data
        total = len(decisions)
        granted = sum(1 for d in decisions if d.get("outcome") == Outcome.GRANTED.value)

        # Count development types
        dev_type_counts: Dict[str, int] = {}
        conservation_areas: set = set()

        for d in decisions:
            if d.get("development_type"):
                dt = d["development_type"]
                dev_type_counts[dt] = dev_type_counts.get(dt, 0) + 1
            if d.get("conservation_area") and d["conservation_area"] != "None":
                conservation_areas.add(d["conservation_area"])

        # Sort development types by frequency
        sorted_types = sorted(dev_type_counts.items(), key=lambda x: x[1], reverse=True)
        common_types = [t[0] for t in sorted_types[:5]]

        return WardInfo(
            name=ward,
            case_count=total,
            approval_rate=granted / total if total > 0 else 0,
            common_development_types=common_types,
            conservation_areas=list(conservation_areas)
        )
