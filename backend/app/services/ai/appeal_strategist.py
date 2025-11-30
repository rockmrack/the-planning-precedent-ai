"""
Appeal Strategy Generator
Advanced AI for generating planning appeal strategies and documents

Features:
1. Refusal reason analysis
2. Inconsistency detection
3. Appeal grounds identification
4. Statement of case generation
5. Evidence bundle preparation
6. Appeal timeline management
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from openai import AsyncOpenAI
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class AppealType(str, Enum):
    """Types of planning appeals"""
    WRITTEN_REPRESENTATIONS = "written_representations"
    INFORMAL_HEARING = "informal_hearing"
    PUBLIC_INQUIRY = "public_inquiry"


class AppealGround(str, Enum):
    """Grounds for planning appeal"""
    POLICY_COMPLIANCE = "policy_compliance"
    INCONSISTENT_DECISIONS = "inconsistent_decisions"
    MATERIAL_CONSIDERATIONS = "material_considerations"
    INSUFFICIENT_REASONS = "insufficient_reasons"
    PROCEDURAL_ERROR = "procedural_error"
    CHANGED_CIRCUMSTANCES = "changed_circumstances"


@dataclass
class RefusalReasonAnalysis:
    """Analysis of a single refusal reason"""
    reason_number: int
    original_text: str
    summary: str
    policies_cited: List[str]
    key_issues: List[str]
    weakness_assessment: str  # strong, moderate, weak
    counter_arguments: List[str]
    supporting_precedents: List[str]
    recommended_approach: str


@dataclass
class InconsistencyFinding:
    """A finding of inconsistent decision-making"""
    approved_case_ref: str
    approved_case_address: str
    similarity_score: float
    key_similarities: List[str]
    approval_reasoning: str
    inconsistency_argument: str
    strength: str  # strong, moderate, weak


@dataclass
class AppealStrategy:
    """Complete appeal strategy"""
    recommended_appeal_type: AppealType
    appeal_type_reasoning: str
    primary_grounds: List[AppealGround]
    secondary_grounds: List[AppealGround]
    refusal_analysis: List[RefusalReasonAnalysis]
    inconsistency_findings: List[InconsistencyFinding]
    key_arguments: List[Dict[str, Any]]
    evidence_required: List[str]
    estimated_success_rate: float
    estimated_timeline_weeks: int
    estimated_cost_range: Tuple[int, int]
    risks: List[str]
    recommendations: List[str]


@dataclass
class StatementOfCase:
    """Generated statement of case for appeal"""
    introduction: str
    site_description: str
    proposal_description: str
    planning_history: str
    policy_context: str
    grounds_of_appeal: List[Dict[str, str]]
    response_to_refusal_reasons: List[Dict[str, str]]
    precedent_analysis: str
    conclusion: str
    word_count: int
    generated_at: datetime


@dataclass
class AppealTimeline:
    """Timeline for appeal process"""
    appeal_deadline: datetime
    submission_target: datetime
    key_milestones: List[Dict[str, Any]]
    critical_dates: List[Dict[str, Any]]
    preparation_checklist: List[Dict[str, bool]]


class AppealStrategist:
    """
    AI-powered appeal strategy generator.

    Analyses refusal reasons, identifies weaknesses, finds inconsistencies,
    and generates comprehensive appeal documentation.
    """

    APPEAL_COSTS = {
        AppealType.WRITTEN_REPRESENTATIONS: (500, 2000),
        AppealType.INFORMAL_HEARING: (2000, 5000),
        AppealType.PUBLIC_INQUIRY: (10000, 50000),
    }

    APPEAL_TIMELINES = {
        AppealType.WRITTEN_REPRESENTATIONS: 16,  # weeks
        AppealType.INFORMAL_HEARING: 24,
        AppealType.PUBLIC_INQUIRY: 40,
    }

    def __init__(self, db, embedding_service):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.db = db
        self.embedding_service = embedding_service

    async def generate_strategy(
        self,
        case_reference: str,
        refusal_reasons: List[str],
        proposal_description: str,
        site_address: str,
        ward: str,
        conservation_area: Optional[str] = None,
    ) -> AppealStrategy:
        """
        Generate comprehensive appeal strategy.
        """
        logger.info(
            "generating_appeal_strategy",
            case_ref=case_reference,
            reason_count=len(refusal_reasons)
        )

        # Analyse each refusal reason
        refusal_analysis = await self._analyse_refusal_reasons(
            refusal_reasons, proposal_description
        )

        # Find inconsistent decisions
        inconsistencies = await self._find_inconsistencies(
            proposal_description, refusal_reasons, ward, conservation_area
        )

        # Determine appeal grounds
        primary_grounds, secondary_grounds = self._determine_grounds(
            refusal_analysis, inconsistencies
        )

        # Determine best appeal type
        appeal_type, type_reasoning = self._recommend_appeal_type(
            refusal_analysis, inconsistencies, primary_grounds
        )

        # Generate key arguments
        key_arguments = await self._generate_key_arguments(
            refusal_analysis, inconsistencies, primary_grounds
        )

        # Identify required evidence
        evidence_required = self._identify_evidence_needs(
            refusal_analysis, primary_grounds
        )

        # Estimate success rate
        success_rate = self._estimate_success_rate(
            refusal_analysis, inconsistencies, primary_grounds
        )

        # Identify risks
        risks = self._identify_risks(refusal_analysis, inconsistencies)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            appeal_type, success_rate, risks
        )

        return AppealStrategy(
            recommended_appeal_type=appeal_type,
            appeal_type_reasoning=type_reasoning,
            primary_grounds=primary_grounds,
            secondary_grounds=secondary_grounds,
            refusal_analysis=refusal_analysis,
            inconsistency_findings=inconsistencies,
            key_arguments=key_arguments,
            evidence_required=evidence_required,
            estimated_success_rate=success_rate,
            estimated_timeline_weeks=self.APPEAL_TIMELINES[appeal_type],
            estimated_cost_range=self.APPEAL_COSTS[appeal_type],
            risks=risks,
            recommendations=recommendations
        )

    async def _analyse_refusal_reasons(
        self,
        reasons: List[str],
        proposal: str
    ) -> List[RefusalReasonAnalysis]:
        """Analyse each refusal reason in detail"""
        analyses = []

        for i, reason in enumerate(reasons, 1):
            prompt = f"""Analyse this planning refusal reason:

Refusal Reason {i}:
{reason}

Proposal:
{proposal}

Provide:
1. Summary of the core issue
2. Policies cited (extract exact references)
3. Key issues raised
4. Assessment of weakness (strong/moderate/weak reason)
5. Potential counter-arguments
6. Recommended approach for appeal

Output JSON:
{{
    "summary": "...",
    "policies_cited": [...],
    "key_issues": [...],
    "weakness_assessment": "strong/moderate/weak",
    "counter_arguments": [...],
    "recommended_approach": "..."
}}"""

            try:
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a planning appeal specialist analysing refusal reasons."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                analyses.append(RefusalReasonAnalysis(
                    reason_number=i,
                    original_text=reason,
                    summary=result.get("summary", ""),
                    policies_cited=result.get("policies_cited", []),
                    key_issues=result.get("key_issues", []),
                    weakness_assessment=result.get("weakness_assessment", "moderate"),
                    counter_arguments=result.get("counter_arguments", []),
                    supporting_precedents=[],  # Filled in later
                    recommended_approach=result.get("recommended_approach", "")
                ))

            except Exception as e:
                logger.error("refusal_analysis_failed", reason=i, error=str(e))

        return analyses

    async def _find_inconsistencies(
        self,
        proposal: str,
        refusal_reasons: List[str],
        ward: str,
        conservation_area: Optional[str]
    ) -> List[InconsistencyFinding]:
        """Find inconsistent decisions that support the appeal"""
        findings = []

        # Search for similar approved cases
        search_query = f"{proposal} {' '.join(refusal_reasons[:2])}"
        embedding = await self.embedding_service.generate_embedding(search_query)

        from app.models.planning import SearchFilters, Outcome
        filters = SearchFilters(
            wards=[ward],
            outcome=Outcome.GRANTED
        )

        similar_cases = await self.db.search_similar(
            query_embedding=embedding,
            filters=filters,
            limit=10,
            similarity_threshold=0.65,
            include_refused=False
        )

        for case in similar_cases:
            if case.similarity_score < 0.7:
                continue

            # Analyse the inconsistency
            prompt = f"""Compare these two planning applications:

REFUSED APPLICATION:
{proposal[:500]}
Refusal reasons: {refusal_reasons[0] if refusal_reasons else 'Not specified'}

APPROVED APPLICATION:
Case: {case.decision.case_reference}
Address: {case.decision.address}
Description: {case.decision.description}
Relevant text: {case.relevant_excerpt[:500]}

Are these similar enough to argue inconsistent decision-making?
Output JSON:
{{
    "key_similarities": [...],
    "approval_reasoning": "...",
    "inconsistency_argument": "...",
    "strength": "strong/moderate/weak"
}}"""

            try:
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are analysing planning decisions for inconsistency."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                if result.get("strength") in ["strong", "moderate"]:
                    findings.append(InconsistencyFinding(
                        approved_case_ref=case.decision.case_reference,
                        approved_case_address=case.decision.address,
                        similarity_score=case.similarity_score,
                        key_similarities=result.get("key_similarities", []),
                        approval_reasoning=result.get("approval_reasoning", ""),
                        inconsistency_argument=result.get("inconsistency_argument", ""),
                        strength=result.get("strength", "moderate")
                    ))

            except Exception as e:
                logger.warning("inconsistency_analysis_failed", error=str(e))

        # Sort by strength
        strength_order = {"strong": 0, "moderate": 1, "weak": 2}
        findings.sort(key=lambda x: strength_order.get(x.strength, 2))

        return findings[:5]  # Return top 5

    def _determine_grounds(
        self,
        refusal_analysis: List[RefusalReasonAnalysis],
        inconsistencies: List[InconsistencyFinding]
    ) -> Tuple[List[AppealGround], List[AppealGround]]:
        """Determine appeal grounds based on analysis"""
        primary = []
        secondary = []

        # Check for policy compliance issues
        weak_reasons = [r for r in refusal_analysis if r.weakness_assessment == "weak"]
        if weak_reasons:
            primary.append(AppealGround.POLICY_COMPLIANCE)

        # Check for inconsistencies
        strong_inconsistencies = [i for i in inconsistencies if i.strength == "strong"]
        if strong_inconsistencies:
            primary.append(AppealGround.INCONSISTENT_DECISIONS)
        elif inconsistencies:
            secondary.append(AppealGround.INCONSISTENT_DECISIONS)

        # Check for insufficient reasons
        vague_reasons = [
            r for r in refusal_analysis
            if len(r.policies_cited) == 0 or "insufficient" in r.recommended_approach.lower()
        ]
        if vague_reasons:
            secondary.append(AppealGround.INSUFFICIENT_REASONS)

        # Material considerations
        if any("material" in r.recommended_approach.lower() for r in refusal_analysis):
            secondary.append(AppealGround.MATERIAL_CONSIDERATIONS)

        # Ensure we have at least one ground
        if not primary and not secondary:
            primary.append(AppealGround.POLICY_COMPLIANCE)

        return primary, secondary

    def _recommend_appeal_type(
        self,
        refusal_analysis: List[RefusalReasonAnalysis],
        inconsistencies: List[InconsistencyFinding],
        grounds: List[AppealGround]
    ) -> Tuple[AppealType, str]:
        """Recommend the best appeal type"""
        # Most householder appeals are written representations
        weak_count = sum(1 for r in refusal_analysis if r.weakness_assessment == "weak")
        strong_inconsistencies = sum(1 for i in inconsistencies if i.strength == "strong")

        if len(refusal_analysis) <= 2 and weak_count >= 1:
            return (
                AppealType.WRITTEN_REPRESENTATIONS,
                "Written representations recommended - straightforward issues that can be addressed in writing"
            )
        elif strong_inconsistencies >= 2:
            return (
                AppealType.WRITTEN_REPRESENTATIONS,
                "Written representations with strong inconsistency evidence - inspector can assess without hearing"
            )
        elif len(grounds) > 3 or any(r.weakness_assessment == "strong" for r in refusal_analysis):
            return (
                AppealType.INFORMAL_HEARING,
                "Informal hearing recommended - complex issues benefit from discussion"
            )
        else:
            return (
                AppealType.WRITTEN_REPRESENTATIONS,
                "Written representations is the most cost-effective approach for this appeal"
            )

    async def _generate_key_arguments(
        self,
        refusal_analysis: List[RefusalReasonAnalysis],
        inconsistencies: List[InconsistencyFinding],
        grounds: List[AppealGround]
    ) -> List[Dict[str, Any]]:
        """Generate key arguments for the appeal"""
        arguments = []

        # Arguments from refusal analysis
        for analysis in refusal_analysis:
            for counter in analysis.counter_arguments[:2]:
                arguments.append({
                    "type": "counter_to_refusal",
                    "refusal_reason": analysis.reason_number,
                    "argument": counter,
                    "supporting_policies": analysis.policies_cited
                })

        # Arguments from inconsistencies
        for inconsistency in inconsistencies[:3]:
            arguments.append({
                "type": "inconsistency",
                "approved_case": inconsistency.approved_case_ref,
                "argument": inconsistency.inconsistency_argument,
                "strength": inconsistency.strength
            })

        return arguments

    def _identify_evidence_needs(
        self,
        refusal_analysis: List[RefusalReasonAnalysis],
        grounds: List[AppealGround]
    ) -> List[str]:
        """Identify evidence needed for the appeal"""
        evidence = [
            "Original application documents",
            "Decision notice with refusal reasons",
            "Site photographs",
            "Copy of relevant policies cited",
        ]

        if AppealGround.INCONSISTENT_DECISIONS in grounds:
            evidence.append("Decision notices for comparable approved cases")
            evidence.append("Analysis of similarities between cases")

        # Check for specific evidence needs
        for analysis in refusal_analysis:
            for issue in analysis.key_issues:
                issue_lower = issue.lower()
                if "design" in issue_lower:
                    evidence.append("Design and Access Statement")
                if "heritage" in issue_lower or "conservation" in issue_lower:
                    evidence.append("Heritage Impact Assessment")
                if "neighbour" in issue_lower or "amenity" in issue_lower:
                    evidence.append("Daylight/Sunlight assessment if applicable")
                if "material" in issue_lower:
                    evidence.append("Material samples or specifications")

        return list(set(evidence))

    def _estimate_success_rate(
        self,
        refusal_analysis: List[RefusalReasonAnalysis],
        inconsistencies: List[InconsistencyFinding],
        grounds: List[AppealGround]
    ) -> float:
        """Estimate probability of appeal success"""
        base_rate = 0.35  # UK householder appeal success rate

        # Adjust based on analysis
        weak_reasons = sum(1 for r in refusal_analysis if r.weakness_assessment == "weak")
        strong_reasons = sum(1 for r in refusal_analysis if r.weakness_assessment == "strong")

        # Weak reasons increase chances
        base_rate += weak_reasons * 0.1

        # Strong reasons decrease chances
        base_rate -= strong_reasons * 0.1

        # Inconsistencies increase chances
        strong_inconsistencies = sum(1 for i in inconsistencies if i.strength == "strong")
        base_rate += strong_inconsistencies * 0.12

        moderate_inconsistencies = sum(1 for i in inconsistencies if i.strength == "moderate")
        base_rate += moderate_inconsistencies * 0.05

        return max(0.15, min(0.80, base_rate))

    def _identify_risks(
        self,
        refusal_analysis: List[RefusalReasonAnalysis],
        inconsistencies: List[InconsistencyFinding]
    ) -> List[str]:
        """Identify risks to appeal success"""
        risks = []

        strong_reasons = [r for r in refusal_analysis if r.weakness_assessment == "strong"]
        if strong_reasons:
            risks.append(f"{len(strong_reasons)} refusal reason(s) are strong and may be difficult to overcome")

        if not inconsistencies:
            risks.append("No clear precedent inconsistencies found - appeal relies on policy arguments alone")

        if any("heritage" in r.original_text.lower() for r in refusal_analysis):
            risks.append("Heritage/conservation issues are given significant weight by inspectors")

        if any("neighbour" in r.original_text.lower() for r in refusal_analysis):
            risks.append("Neighbour amenity concerns must be carefully addressed")

        risks.append("Appeal costs are not recoverable even if successful")
        risks.append("If unsuccessful, costs of any subsequent appeal may be awarded against appellant")

        return risks

    def _generate_recommendations(
        self,
        appeal_type: AppealType,
        success_rate: float,
        risks: List[str]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        if success_rate >= 0.6:
            recommendations.append("Appeal has reasonable prospects - proceed if development is important")
        elif success_rate >= 0.4:
            recommendations.append("Consider pre-appeal discussions with LPA to resolve issues")
            recommendations.append("Design amendments may strengthen appeal case")
        else:
            recommendations.append("Significant redesign may be more effective than appeal")
            recommendations.append("Seek professional planning advice before proceeding")

        recommendations.append(f"Use {appeal_type.value.replace('_', ' ')} procedure as recommended")
        recommendations.append("Submit appeal within 6 months of decision date")
        recommendations.append("Engage planning consultant experienced in Camden appeals")

        return recommendations

    async def generate_statement_of_case(
        self,
        strategy: AppealStrategy,
        site_address: str,
        proposal: str,
        planning_history: Optional[str] = None
    ) -> StatementOfCase:
        """Generate a full statement of case for the appeal"""
        prompt = f"""Generate a professional planning appeal statement of case.

Site: {site_address}
Proposal: {proposal}
Planning History: {planning_history or 'None relevant'}

Refusal Reasons:
{json.dumps([{"number": r.reason_number, "text": r.original_text, "counter": r.counter_arguments} for r in strategy.refusal_analysis], indent=2)}

Key Inconsistencies:
{json.dumps([{"case": i.approved_case_ref, "argument": i.inconsistency_argument} for i in strategy.inconsistency_findings[:3]], indent=2)}

Primary Appeal Grounds: {[g.value for g in strategy.primary_grounds]}

Generate a formal statement of case with these sections:
1. Introduction (appellant details, appeal reference)
2. Site Description
3. The Proposal
4. Planning History
5. Policy Context
6. Grounds of Appeal
7. Response to each Refusal Reason
8. Precedent Analysis
9. Conclusion

Use formal planning language. Cite specific policies and cases."""

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a senior planning consultant drafting an appeal statement."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )

        full_text = response.choices[0].message.content

        # Parse sections (simplified)
        sections = full_text.split("\n\n")

        return StatementOfCase(
            introduction=sections[0] if sections else "",
            site_description=self._extract_section(full_text, "Site Description"),
            proposal_description=self._extract_section(full_text, "Proposal"),
            planning_history=self._extract_section(full_text, "Planning History"),
            policy_context=self._extract_section(full_text, "Policy Context"),
            grounds_of_appeal=[{"ground": g.value, "text": self._extract_section(full_text, g.value)} for g in strategy.primary_grounds],
            response_to_refusal_reasons=[{"reason": r.reason_number, "response": r.counter_arguments[0] if r.counter_arguments else ""} for r in strategy.refusal_analysis],
            precedent_analysis=self._extract_section(full_text, "Precedent"),
            conclusion=self._extract_section(full_text, "Conclusion"),
            word_count=len(full_text.split()),
            generated_at=datetime.utcnow()
        )

    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from the generated text"""
        import re
        pattern = rf"(?:{section_name}|{section_name.upper()})[:\n]+(.+?)(?=\n[A-Z]|\n\d+\.|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip()[:2000] if match else ""

    def calculate_appeal_timeline(
        self,
        decision_date: datetime,
        appeal_type: AppealType
    ) -> AppealTimeline:
        """Calculate appeal timeline and deadlines"""
        # Appeal deadline is 6 months from decision
        appeal_deadline = decision_date + timedelta(days=180)

        # Submission target (allow 4 weeks before deadline)
        submission_target = appeal_deadline - timedelta(weeks=4)

        milestones = [
            {"name": "Decision received", "date": decision_date, "status": "complete"},
            {"name": "Initial assessment", "date": decision_date + timedelta(days=7), "status": "pending"},
            {"name": "Evidence gathering", "date": decision_date + timedelta(days=30), "status": "pending"},
            {"name": "Statement drafting", "date": decision_date + timedelta(days=60), "status": "pending"},
            {"name": "Review and finalise", "date": submission_target - timedelta(weeks=2), "status": "pending"},
            {"name": "Appeal submission", "date": submission_target, "status": "pending"},
            {"name": "PINS acknowledgement", "date": submission_target + timedelta(weeks=2), "status": "pending"},
            {"name": "LPA response deadline", "date": submission_target + timedelta(weeks=6), "status": "pending"},
            {"name": "Expected decision", "date": submission_target + timedelta(weeks=self.APPEAL_TIMELINES[appeal_type]), "status": "pending"},
        ]

        critical_dates = [
            {"event": "Appeal deadline", "date": appeal_deadline, "importance": "critical"},
            {"event": "Recommended submission", "date": submission_target, "importance": "high"},
        ]

        checklist = [
            {"item": "Review decision notice", "completed": False},
            {"item": "Gather application documents", "completed": False},
            {"item": "Take site photographs", "completed": False},
            {"item": "Research precedent cases", "completed": False},
            {"item": "Draft statement of case", "completed": False},
            {"item": "Prepare evidence bundle", "completed": False},
            {"item": "Complete appeal form", "completed": False},
            {"item": "Pay appeal fee (if applicable)", "completed": False},
            {"item": "Submit via Planning Portal", "completed": False},
        ]

        return AppealTimeline(
            appeal_deadline=appeal_deadline,
            submission_target=submission_target,
            key_milestones=milestones,
            critical_dates=critical_dates,
            preparation_checklist=checklist
        )
