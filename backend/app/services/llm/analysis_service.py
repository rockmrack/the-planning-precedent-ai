"""
LLM-Powered Planning Analysis Service
Uses GPT-4o to generate legal arguments and analyse planning precedents

This is the "brain" of the system - it takes precedent matches and
generates professional planning arguments citing specific cases.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from openai import AsyncOpenAI
import structlog

from app.core.config import settings
from app.models.planning import (
    AnalysisRequest,
    AnalysisResponse,
    ArgumentSection,
    RiskAssessment,
    PrecedentMatch,
    ConservationAreaStatus,
)

logger = structlog.get_logger(__name__)


# System prompts for different analysis types
SENIOR_PLANNER_PROMPT = """You are a Senior Planning Consultant with 20 years of experience
in London Borough of Camden. You specialise in residential extensions, basement developments,
and conservation area applications.

Your role is to analyse planning precedents and generate compelling, professional arguments
that planning officers will respect. You understand:

- Camden Local Plan 2017 policies (especially D1, D2, D3, H1, H2)
- London Plan 2021 policies
- National Planning Policy Framework (NPPF) 2023
- Town and Country Planning Act 1990
- Planning (Listed Buildings and Conservation Areas) Act 1990
- Camden's Supplementary Planning Documents (particularly on residential extensions)
- Conservation Area character assessments

When citing precedents:
- Use the exact case reference format (e.g., 2023/1234/P)
- Quote officer wording directly where available
- Reference specific policy justifications used
- Note any conditions that were applied

Your arguments must be:
- Professional and objective in tone
- Specific to Camden's planning context
- Legally sound and policy-compliant
- Persuasive but realistic about challenges"""


RISK_ASSESSOR_PROMPT = """You are a Planning Risk Analyst specialising in predicting
planning application outcomes. Based on the precedents provided and the proposed
development, you must:

1. Assess the likelihood of approval (High/Medium/Low)
2. Identify specific risks that could lead to refusal
3. Suggest mitigation measures
4. Highlight similar applications that were refused

Be honest and realistic - if there are significant risks, say so clearly.
Consider factors like:
- Conservation area sensitivity
- Neighbour amenity impact
- Design and materials
- Scale and massing
- Compliance with local policies"""


class AnalysisService:
    """
    Service for generating AI-powered planning analysis.

    Takes precedent matches from vector search and generates:
    - Professional planning arguments
    - Risk assessments
    - Counter-arguments and mitigations
    - Policy references
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_llm_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature

    async def analyse_precedents(
        self,
        request: AnalysisRequest,
        precedents: List[PrecedentMatch]
    ) -> AnalysisResponse:
        """
        Generate comprehensive analysis from precedent matches.

        Args:
            request: The analysis request with development details
            precedents: Matching precedents from vector search

        Returns:
            AnalysisResponse with arguments, risk assessment, and recommendations
        """
        logger.info(
            "starting_analysis",
            query_length=len(request.query),
            precedent_count=len(precedents)
        )

        try:
            # Build context from precedents
            context = self._build_precedent_context(precedents)

            # Generate main arguments
            arguments = await self._generate_arguments(request, context)

            # Generate risk assessment
            risk_assessment = await self._generate_risk_assessment(
                request, precedents, context
            )

            # Extract policy references from generated content
            policies = self._extract_all_policies(arguments, context)

            # Create summary
            summary = await self._generate_summary(request, arguments, risk_assessment)

            # Determine recommendation
            recommendation = self._determine_recommendation(
                risk_assessment, len([p for p in precedents if p.similarity_score > 0.8])
            )

            response = AnalysisResponse(
                summary=summary,
                recommendation=recommendation,
                arguments=arguments,
                risk_assessment=risk_assessment,
                precedents_used=precedents,
                policies_referenced=policies,
                generated_at=datetime.utcnow(),
                model_version=self.model
            )

            logger.info(
                "analysis_complete",
                argument_count=len(arguments),
                confidence=risk_assessment.confidence_score
            )

            return response

        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            raise

    def _build_precedent_context(
        self,
        precedents: List[PrecedentMatch]
    ) -> str:
        """Build context string from precedent matches"""
        context_parts = []

        for i, p in enumerate(precedents[:10], 1):
            part = f"""
PRECEDENT {i}:
Case Reference: {p.decision.case_reference}
Address: {p.decision.address}
Decision Date: {p.decision.decision_date}
Outcome: {p.decision.outcome.value}
Development Type: {p.decision.development_type.value if p.decision.development_type else 'Not specified'}
Similarity Score: {p.similarity_score:.2f}

Relevant Extract:
{p.relevant_excerpt}

Key Policies Referenced: {', '.join(p.key_policies) if p.key_policies else 'Not extracted'}
---"""
            context_parts.append(part)

        return "\n".join(context_parts)

    async def _generate_arguments(
        self,
        request: AnalysisRequest,
        context: str
    ) -> List[ArgumentSection]:
        """Generate structured planning arguments"""
        conservation_context = ""
        if request.conservation_area and request.conservation_area != ConservationAreaStatus.NONE:
            conservation_context = f"""
IMPORTANT: The site is within {request.conservation_area.value}.
The character and appearance of the conservation area must be preserved or enhanced.
Reference the relevant Conservation Area Appraisal and Statement in your arguments."""

        prompt = f"""Based on the precedents provided, generate professional planning arguments
for the following proposed development:

PROPOSED DEVELOPMENT:
{request.query}

SITE ADDRESS: {request.address or 'Not specified'}
WARD: {request.ward or 'Not specified'}
{conservation_context}

PRECEDENTS:
{context}

Generate 3-5 argument sections. Each section should:
1. Have a clear heading (e.g., "Design and Visual Impact", "Policy Compliance")
2. Cite specific case references from the precedents
3. Quote relevant officer wording where available
4. Reference applicable planning policies

Format your response as JSON with this structure:
{{
    "arguments": [
        {{
            "heading": "Section heading",
            "content": "Detailed argument text",
            "supporting_cases": ["2023/1234/P"],
            "policy_references": ["Policy D1", "NPPF para 130"],
            "officer_quotes": [{{"case": "2023/1234/P", "quote": "Officer wording..."}}]
        }}
    ]
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SENIOR_PLANNER_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        arguments = []
        for arg_data in result.get("arguments", []):
            arguments.append(ArgumentSection(
                heading=arg_data.get("heading", ""),
                content=arg_data.get("content", ""),
                supporting_cases=arg_data.get("supporting_cases", []),
                policy_references=arg_data.get("policy_references", []),
                officer_quotes=arg_data.get("officer_quotes", [])
            ))

        return arguments

    async def _generate_risk_assessment(
        self,
        request: AnalysisRequest,
        precedents: List[PrecedentMatch],
        context: str
    ) -> RiskAssessment:
        """Generate risk assessment for the proposed development"""
        # Calculate base confidence from precedent similarity
        if precedents:
            avg_similarity = sum(p.similarity_score for p in precedents) / len(precedents)
            granted_count = sum(
                1 for p in precedents
                if p.decision.outcome.value == "Granted"
            )
            granted_ratio = granted_count / len(precedents)
        else:
            avg_similarity = 0
            granted_ratio = 0

        prompt = f"""Assess the planning risk for this proposed development:

PROPOSED DEVELOPMENT:
{request.query}

SITE: {request.address or 'Not specified'}
WARD: {request.ward or 'Not specified'}
CONSERVATION AREA: {request.conservation_area.value if request.conservation_area else 'None'}

PRECEDENT CONTEXT:
{context}

PRECEDENT STATS:
- Average similarity to approved cases: {avg_similarity:.2f}
- Proportion of similar cases that were approved: {granted_ratio:.2%}

Provide a risk assessment in JSON format:
{{
    "approval_likelihood": "High/Medium/Low",
    "confidence_score": 0.0-1.0,
    "key_risks": ["Risk 1", "Risk 2"],
    "mitigation_suggestions": ["Suggestion 1", "Suggestion 2"],
    "similar_refusals": ["Brief description of any similar refused cases"]
}}

Be honest and specific about risks. Consider:
- Design sensitivity in conservation areas
- Neighbour amenity (light, privacy, outlook)
- Scale, massing, and cumulative development
- Material choices
- Policy compliance"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RISK_ASSESSOR_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return RiskAssessment(
            approval_likelihood=result.get("approval_likelihood", "Medium"),
            confidence_score=float(result.get("confidence_score", 0.5)),
            key_risks=result.get("key_risks", []),
            mitigation_suggestions=result.get("mitigation_suggestions", []),
            similar_refusals=result.get("similar_refusals", [])
        )

    async def _generate_summary(
        self,
        request: AnalysisRequest,
        arguments: List[ArgumentSection],
        risk: RiskAssessment
    ) -> str:
        """Generate executive summary"""
        argument_texts = [f"- {a.heading}: {a.content[:200]}..." for a in arguments[:3]]

        prompt = f"""Write a brief executive summary (2-3 sentences) for this planning analysis:

Proposed Development: {request.query[:300]}
Site: {request.address or 'Not specified'}

Key Arguments:
{chr(10).join(argument_texts)}

Risk Assessment: {risk.approval_likelihood} likelihood of approval
Key Risks: {', '.join(risk.key_risks[:3])}

The summary should be professional, concise, and highlight the strength of the precedent case."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a planning consultant writing an executive summary."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )

        return response.choices[0].message.content.strip()

    def _determine_recommendation(
        self,
        risk: RiskAssessment,
        strong_precedent_count: int
    ) -> str:
        """Determine overall recommendation"""
        if risk.approval_likelihood == "High" and strong_precedent_count >= 3:
            return "Proceed with confidence. Strong precedent support exists for this type of development."
        elif risk.approval_likelihood == "Medium" or strong_precedent_count >= 1:
            return "Proceed with caution. Pre-application advice recommended to address identified risks."
        else:
            return "Consider design amendments or pre-application discussions before submitting a formal application."

    def _extract_all_policies(
        self,
        arguments: List[ArgumentSection],
        context: str
    ) -> List[str]:
        """Extract all unique policy references"""
        policies = set()

        for arg in arguments:
            policies.update(arg.policy_references)

        # Also extract from context
        import re
        patterns = [
            r"Policy\s+[A-Z]\d+",
            r"NPPF\s+(?:paragraph\s+)?\d+",
            r"London\s+Plan\s+Policy\s+\w+",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, context, re.IGNORECASE)
            policies.update(matches)

        return sorted(list(policies))

    async def generate_counter_arguments(
        self,
        arguments: List[ArgumentSection],
        context: str
    ) -> List[Dict[str, str]]:
        """Generate potential counter-arguments and rebuttals"""
        prompt = f"""You are a planning officer reviewing an application.
Based on these arguments submitted by the applicant, identify potential counter-arguments
that a planning officer might raise, and provide professional rebuttals.

APPLICANT'S ARGUMENTS:
{json.dumps([{"heading": a.heading, "content": a.content} for a in arguments], indent=2)}

For each potential counter-argument, provide:
1. The objection a planning officer might raise
2. A professional rebuttal citing the precedents or policies

Format as JSON:
{{
    "counter_arguments": [
        {{
            "objection": "The officer might argue...",
            "rebuttal": "However, the precedents show..."
        }}
    ]
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SENIOR_PLANNER_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.5,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return result.get("counter_arguments", [])

    async def generate_appeal_argument(
        self,
        decision: Dict[str, Any],
        precedents: List[PrecedentMatch]
    ) -> str:
        """Generate argument for planning appeal based on inconsistency"""
        prompt = f"""A planning application has been REFUSED. Generate an appeal argument
based on inconsistent decision-making, citing these APPROVED precedents for similar developments:

REFUSED APPLICATION:
Case Reference: {decision.get('case_reference')}
Address: {decision.get('address')}
Description: {decision.get('description')}
Refusal Reasons: {decision.get('refusal_reasons', 'Not specified')}

APPROVED PRECEDENTS (similar developments that WERE approved):
{self._build_precedent_context(precedents)}

Generate a compelling appeal argument that:
1. Highlights the inconsistency in decision-making
2. Cites the specific approved cases with similar characteristics
3. References the principle of consistency in planning decisions
4. Argues that the refusal is unreasonable given the approved precedents

The argument should be professional and suitable for a planning appeal statement."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SENIOR_PLANNER_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3
        )

        return response.choices[0].message.content.strip()
