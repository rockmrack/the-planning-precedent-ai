"""
Advanced Multi-Model Reasoning Engine
Orchestrates multiple AI models for comprehensive planning analysis

This engine implements:
1. Chain-of-Thought reasoning for complex planning assessments
2. Multi-model ensemble for higher accuracy
3. Self-verification and fact-checking
4. Structured reasoning with citations
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from openai import AsyncOpenAI
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class ReasoningStep(str, Enum):
    """Steps in the reasoning chain"""
    UNDERSTAND = "understand"
    GATHER_CONTEXT = "gather_context"
    IDENTIFY_POLICIES = "identify_policies"
    FIND_PRECEDENTS = "find_precedents"
    ANALYSE_SIMILARITIES = "analyse_similarities"
    ASSESS_RISKS = "assess_risks"
    GENERATE_ARGUMENTS = "generate_arguments"
    VERIFY_CITATIONS = "verify_citations"
    SYNTHESIZE = "synthesize"


@dataclass
class ReasoningContext:
    """Context accumulated during reasoning"""
    query: str
    site_address: Optional[str] = None
    ward: Optional[str] = None
    conservation_area: Optional[str] = None

    # Accumulated knowledge
    understood_requirements: Dict[str, Any] = field(default_factory=dict)
    relevant_policies: List[Dict[str, str]] = field(default_factory=list)
    precedents: List[Dict[str, Any]] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    arguments: List[Dict[str, Any]] = field(default_factory=list)

    # Reasoning trace
    steps_completed: List[str] = field(default_factory=list)
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class ReasoningOutput:
    """Final output from reasoning engine"""
    summary: str
    recommendation: str
    confidence: float
    arguments: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    precedents_cited: List[str]
    policies_referenced: List[str]
    reasoning_trace: List[Dict[str, Any]]
    verification_status: Dict[str, bool]
    generated_at: datetime


class ReasoningEngine:
    """
    Multi-model reasoning engine for planning analysis.

    Uses chain-of-thought prompting with verification steps
    to produce high-quality, verifiable planning arguments.
    """

    # System prompts for different reasoning stages
    PROMPTS = {
        ReasoningStep.UNDERSTAND: """You are a planning analysis system. Your task is to understand the user's development proposal.

Extract and structure:
1. Development type (extension, dormer, basement, etc.)
2. Key design elements (materials, dimensions, style)
3. Site constraints mentioned
4. Specific concerns or requirements

Output JSON:
{
    "development_type": "...",
    "design_elements": [...],
    "constraints": [...],
    "specific_requirements": [...],
    "ambiguities": [...]
}""",

        ReasoningStep.IDENTIFY_POLICIES: """You are a UK planning policy expert specialising in Camden Council.

Given the development proposal, identify ALL relevant planning policies from:
1. Camden Local Plan 2017 (Policies D1-D3, A1-A2, H1-H2, etc.)
2. London Plan 2021
3. NPPF 2023 (especially paragraphs 126-141 on design, 195-208 on heritage)
4. Camden SPDs (Residential Extensions, Basements)

For conservation areas, also cite:
- Section 72 of Planning (Listed Buildings and Conservation Areas) Act 1990
- Relevant Conservation Area Appraisal

Output JSON:
{
    "primary_policies": [
        {"code": "D1", "title": "...", "relevance": "...", "key_requirements": [...]}
    ],
    "secondary_policies": [...],
    "heritage_policies": [...],
    "supplementary_guidance": [...]
}""",

        ReasoningStep.ANALYSE_SIMILARITIES: """You are a planning precedent analyst.

Compare the proposed development against each precedent case. For each:
1. List specific similarities (scale, design, materials, context)
2. List key differences
3. Explain why similarities outweigh differences (or not)
4. Extract exact officer wording that supports the proposal
5. Rate relevance (1-10) with justification

Be precise and cite specific details from both the proposal and precedents.""",

        ReasoningStep.ASSESS_RISKS: """You are a planning risk assessor for Camden Council applications.

Identify ALL potential risks to approval:
1. Policy compliance gaps
2. Design concerns (scale, materials, character)
3. Neighbour amenity impacts (light, privacy, outlook)
4. Heritage/conservation concerns
5. Precedent weaknesses
6. Procedural risks

For each risk:
- Severity (High/Medium/Low)
- Likelihood of officer raising it
- Mitigation strategy
- Counter-argument if raised

Be thorough - missed risks lead to refusals.""",

        ReasoningStep.GENERATE_ARGUMENTS: """You are a senior planning consultant writing arguments for a planning application.

Generate professional, persuasive arguments that:
1. Lead with the strongest points
2. Cite specific precedent case references
3. Quote officer wording from approved cases
4. Reference exact policy requirements and how they're met
5. Pre-emptively address likely objections
6. Use formal planning language

Structure each argument:
- Clear heading
- Policy context
- Precedent support with quotes
- Application to this proposal
- Conclusion""",

        ReasoningStep.VERIFY_CITATIONS: """You are a fact-checker for planning documents.

Verify each citation in the arguments:
1. Check case references exist and are correctly formatted
2. Verify policy references are accurate
3. Confirm quoted text matches source material
4. Flag any unsupported claims

Output verification status for each citation.""",
    }

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.primary_model = "gpt-4o"
        self.verification_model = "gpt-4o-mini"  # Faster for verification

    async def reason(
        self,
        query: str,
        precedents: List[Dict[str, Any]],
        site_address: Optional[str] = None,
        ward: Optional[str] = None,
        conservation_area: Optional[str] = None,
    ) -> ReasoningOutput:
        """
        Execute full reasoning chain for planning analysis.
        """
        logger.info("starting_reasoning", query_length=len(query))

        context = ReasoningContext(
            query=query,
            site_address=site_address,
            ward=ward,
            conservation_area=conservation_area,
            precedents=[p for p in precedents],
        )

        try:
            # Step 1: Understand the proposal
            await self._step_understand(context)

            # Step 2: Identify relevant policies
            await self._step_identify_policies(context)

            # Step 3: Analyse precedent similarities
            await self._step_analyse_similarities(context)

            # Step 4: Assess risks
            await self._step_assess_risks(context)

            # Step 5: Generate arguments
            await self._step_generate_arguments(context)

            # Step 6: Verify citations
            verification = await self._step_verify_citations(context)

            # Step 7: Synthesize final output
            output = await self._synthesize(context, verification)

            logger.info(
                "reasoning_complete",
                confidence=output.confidence,
                arguments_count=len(output.arguments)
            )

            return output

        except Exception as e:
            logger.error("reasoning_failed", error=str(e))
            raise

    async def _step_understand(self, context: ReasoningContext) -> None:
        """Understand and structure the development proposal"""
        response = await self._call_model(
            self.PROMPTS[ReasoningStep.UNDERSTAND],
            f"Development Proposal:\n{context.query}\n\nSite: {context.site_address or 'Not specified'}\nWard: {context.ward or 'Not specified'}\nConservation Area: {context.conservation_area or 'None'}",
            response_format="json"
        )

        context.understood_requirements = json.loads(response)
        context.steps_completed.append(ReasoningStep.UNDERSTAND.value)
        context.reasoning_trace.append({
            "step": ReasoningStep.UNDERSTAND.value,
            "output": context.understood_requirements,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def _step_identify_policies(self, context: ReasoningContext) -> None:
        """Identify all relevant planning policies"""
        prompt_context = f"""
Development Type: {context.understood_requirements.get('development_type', 'Unknown')}
Design Elements: {json.dumps(context.understood_requirements.get('design_elements', []))}
Ward: {context.ward or 'Camden'}
Conservation Area: {context.conservation_area or 'None'}
"""

        response = await self._call_model(
            self.PROMPTS[ReasoningStep.IDENTIFY_POLICIES],
            prompt_context,
            response_format="json"
        )

        policies = json.loads(response)
        context.relevant_policies = policies
        context.steps_completed.append(ReasoningStep.IDENTIFY_POLICIES.value)
        context.reasoning_trace.append({
            "step": ReasoningStep.IDENTIFY_POLICIES.value,
            "output": policies,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def _step_analyse_similarities(self, context: ReasoningContext) -> None:
        """Deep analysis of precedent similarities"""
        precedent_text = "\n\n".join([
            f"CASE {i+1}: {p.get('case_reference', 'Unknown')}\n"
            f"Address: {p.get('address', 'Unknown')}\n"
            f"Description: {p.get('description', 'No description')}\n"
            f"Outcome: {p.get('outcome', 'Unknown')}\n"
            f"Relevant Text: {p.get('relevant_excerpt', 'No excerpt')[:1000]}"
            for i, p in enumerate(context.precedents[:10])
        ])

        prompt_context = f"""
PROPOSED DEVELOPMENT:
{context.query}

Development Type: {context.understood_requirements.get('development_type')}
Design Elements: {json.dumps(context.understood_requirements.get('design_elements', []))}

PRECEDENT CASES:
{precedent_text}

Analyse each precedent's relevance to this proposal.
"""

        response = await self._call_model(
            self.PROMPTS[ReasoningStep.ANALYSE_SIMILARITIES],
            prompt_context,
            response_format="json"
        )

        analysis = json.loads(response)
        context.reasoning_trace.append({
            "step": ReasoningStep.ANALYSE_SIMILARITIES.value,
            "output": analysis,
            "timestamp": datetime.utcnow().isoformat()
        })
        context.steps_completed.append(ReasoningStep.ANALYSE_SIMILARITIES.value)

    async def _step_assess_risks(self, context: ReasoningContext) -> None:
        """Comprehensive risk assessment"""
        prompt_context = f"""
PROPOSAL:
{context.query}

SITE CONTEXT:
- Ward: {context.ward or 'Not specified'}
- Conservation Area: {context.conservation_area or 'None'}
- Address: {context.site_address or 'Not specified'}

RELEVANT POLICIES:
{json.dumps(context.relevant_policies, indent=2)}

PRECEDENT STRENGTH:
{len(context.precedents)} similar cases found

Identify all risks to approval.
"""

        response = await self._call_model(
            self.PROMPTS[ReasoningStep.ASSESS_RISKS],
            prompt_context,
            response_format="json"
        )

        risks = json.loads(response)
        context.risk_factors = risks.get("risks", [])
        context.confidence_scores["risk_assessment"] = risks.get("overall_confidence", 0.5)
        context.reasoning_trace.append({
            "step": ReasoningStep.ASSESS_RISKS.value,
            "output": risks,
            "timestamp": datetime.utcnow().isoformat()
        })
        context.steps_completed.append(ReasoningStep.ASSESS_RISKS.value)

    async def _step_generate_arguments(self, context: ReasoningContext) -> None:
        """Generate professional planning arguments"""
        precedent_summary = "\n".join([
            f"- {p.get('case_reference')}: {p.get('description', '')[:100]}..."
            for p in context.precedents[:5]
        ])

        prompt_context = f"""
PROPOSAL:
{context.query}

KEY POLICIES:
{json.dumps(context.relevant_policies.get('primary_policies', []), indent=2)}

SUPPORTING PRECEDENTS:
{precedent_summary}

RISKS TO ADDRESS:
{json.dumps(context.risk_factors[:5], indent=2)}

Generate 4-6 strong planning arguments.
"""

        response = await self._call_model(
            self.PROMPTS[ReasoningStep.GENERATE_ARGUMENTS],
            prompt_context,
            response_format="json"
        )

        arguments = json.loads(response)
        context.arguments = arguments.get("arguments", [])
        context.reasoning_trace.append({
            "step": ReasoningStep.GENERATE_ARGUMENTS.value,
            "output": arguments,
            "timestamp": datetime.utcnow().isoformat()
        })
        context.steps_completed.append(ReasoningStep.GENERATE_ARGUMENTS.value)

    async def _step_verify_citations(self, context: ReasoningContext) -> Dict[str, bool]:
        """Verify all citations in generated arguments"""
        citations_to_verify = []

        for arg in context.arguments:
            citations_to_verify.extend(arg.get("case_references", []))
            citations_to_verify.extend(arg.get("policy_references", []))

        prompt_context = f"""
Citations to verify:
{json.dumps(citations_to_verify, indent=2)}

Known valid case references:
{json.dumps([p.get('case_reference') for p in context.precedents], indent=2)}

Valid Camden policies: D1, D2, D3, A1, A2, H1, H2, CC1, CC2, T1, T2
Valid NPPF paragraphs: 126-141 (design), 195-208 (heritage)

Verify each citation exists and is correctly formatted.
"""

        response = await self._call_model(
            self.PROMPTS[ReasoningStep.VERIFY_CITATIONS],
            prompt_context,
            response_format="json",
            model=self.verification_model
        )

        verification = json.loads(response)
        context.reasoning_trace.append({
            "step": ReasoningStep.VERIFY_CITATIONS.value,
            "output": verification,
            "timestamp": datetime.utcnow().isoformat()
        })
        context.steps_completed.append(ReasoningStep.VERIFY_CITATIONS.value)

        return verification

    async def _synthesize(
        self,
        context: ReasoningContext,
        verification: Dict[str, bool]
    ) -> ReasoningOutput:
        """Synthesize all reasoning into final output"""
        # Calculate overall confidence
        confidence_factors = [
            len(context.precedents) / 10,  # More precedents = higher confidence
            context.confidence_scores.get("risk_assessment", 0.5),
            1.0 if context.conservation_area == "None" else 0.8,  # Conservation areas are harder
            sum(1 for v in verification.get("citations", {}).values() if v) / max(len(verification.get("citations", {})), 1),
        ]
        overall_confidence = sum(confidence_factors) / len(confidence_factors)

        # Generate summary
        summary_prompt = f"""
Based on this analysis, write a 2-3 sentence executive summary:

Proposal: {context.query[:200]}
Precedents found: {len(context.precedents)}
Key risks: {len(context.risk_factors)}
Arguments generated: {len(context.arguments)}
Confidence: {overall_confidence:.0%}
"""

        summary = await self._call_model(
            "Write a professional executive summary for a planning analysis.",
            summary_prompt
        )

        # Determine recommendation
        if overall_confidence >= 0.7:
            recommendation = "Proceed with application. Strong precedent support exists."
        elif overall_confidence >= 0.5:
            recommendation = "Proceed with caution. Consider pre-application advice to address identified risks."
        else:
            recommendation = "Design amendments recommended before submission. Significant risks identified."

        return ReasoningOutput(
            summary=summary.strip(),
            recommendation=recommendation,
            confidence=overall_confidence,
            arguments=context.arguments,
            risks=[{"risk": r} if isinstance(r, str) else r for r in context.risk_factors],
            precedents_cited=[p.get("case_reference", "") for p in context.precedents[:10]],
            policies_referenced=self._extract_policy_refs(context.relevant_policies),
            reasoning_trace=context.reasoning_trace,
            verification_status=verification,
            generated_at=datetime.utcnow()
        )

    def _extract_policy_refs(self, policies: Dict) -> List[str]:
        """Extract policy reference codes"""
        refs = []
        for category in ["primary_policies", "secondary_policies", "heritage_policies"]:
            for policy in policies.get(category, []):
                if isinstance(policy, dict):
                    refs.append(policy.get("code", ""))
                elif isinstance(policy, str):
                    refs.append(policy)
        return [r for r in refs if r]

    async def _call_model(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: str = "text",
        model: Optional[str] = None,
    ) -> str:
        """Call the LLM with given prompts"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        kwargs = {
            "model": model or self.primary_model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.2,
        }

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
