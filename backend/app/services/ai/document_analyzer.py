"""
Advanced Document Analyzer
Deep analysis of planning documents with intelligent extraction

Features:
1. Automatic section identification
2. Key phrase extraction
3. Sentiment analysis of officer comments
4. Condition parsing and categorisation
5. Policy compliance checking
6. Comparison between documents
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from openai import AsyncOpenAI
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class SectionType(str, Enum):
    """Standard sections in planning documents"""
    PROPOSAL = "proposal"
    SITE_DESCRIPTION = "site_description"
    PLANNING_HISTORY = "planning_history"
    POLICY_CONTEXT = "policy_context"
    CONSULTATION = "consultation"
    ASSESSMENT = "assessment"
    DESIGN = "design"
    AMENITY = "amenity"
    HERITAGE = "heritage"
    CONCLUSION = "conclusion"
    CONDITIONS = "conditions"
    REASONS_FOR_REFUSAL = "refusal_reasons"


class SentimentLevel(str, Enum):
    """Sentiment levels for officer comments"""
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


@dataclass
class DocumentSection:
    """A section extracted from a planning document"""
    section_type: SectionType
    title: str
    content: str
    start_position: int
    end_position: int
    key_points: List[str] = field(default_factory=list)
    sentiment: Optional[SentimentLevel] = None
    policies_mentioned: List[str] = field(default_factory=list)


@dataclass
class ExtractedCondition:
    """A planning condition extracted from a decision"""
    number: int
    text: str
    category: str  # time_limit, materials, design, amenity, highways, etc.
    compliance_deadline: Optional[str] = None
    requires_submission: bool = False
    submission_type: Optional[str] = None


@dataclass
class OfficerStatement:
    """A key statement from an officer report"""
    text: str
    sentiment: SentimentLevel
    topic: str
    is_conclusion: bool
    supporting_policy: Optional[str] = None


@dataclass
class DocumentAnalysis:
    """Complete analysis of a planning document"""
    document_type: str  # decision_notice, officer_report, appeal_decision
    case_reference: Optional[str]
    outcome: Optional[str]
    sections: List[DocumentSection]
    conditions: List[ExtractedCondition]
    key_statements: List[OfficerStatement]
    policies_referenced: List[str]
    overall_sentiment: SentimentLevel
    word_count: int
    analysis_timestamp: datetime


@dataclass
class DocumentComparison:
    """Comparison between two planning documents"""
    document_a_ref: str
    document_b_ref: str
    similarities: List[str]
    differences: List[str]
    common_policies: List[str]
    divergent_policies: List[str]
    outcome_comparison: str
    relevance_score: float


class DocumentAnalyzer:
    """
    Advanced document analyzer for planning documents.

    Uses NLP and LLM techniques to extract structured
    information from planning decision notices and officer reports.
    """

    # Section header patterns
    SECTION_PATTERNS = {
        SectionType.PROPOSAL: [
            r"(?:PROPOSAL|THE PROPOSAL|DESCRIPTION OF DEVELOPMENT)",
            r"(?:1\.\s*)?(?:PROPOSAL|DEVELOPMENT PROPOSED)",
        ],
        SectionType.SITE_DESCRIPTION: [
            r"(?:SITE AND SURROUNDINGS|SITE DESCRIPTION|THE SITE)",
            r"(?:2\.\s*)?(?:SITE|LOCATION)",
        ],
        SectionType.PLANNING_HISTORY: [
            r"(?:PLANNING HISTORY|RELEVANT HISTORY)",
            r"(?:3\.\s*)?(?:HISTORY|BACKGROUND)",
        ],
        SectionType.POLICY_CONTEXT: [
            r"(?:POLICY CONTEXT|PLANNING POLICY|RELEVANT POLICIES)",
            r"(?:4\.\s*)?(?:POLICY|POLICIES)",
        ],
        SectionType.CONSULTATION: [
            r"(?:CONSULTATION|REPRESENTATIONS|NEIGHBOUR RESPONSES)",
            r"(?:5\.\s*)?(?:CONSULTATION|COMMENTS RECEIVED)",
        ],
        SectionType.ASSESSMENT: [
            r"(?:ASSESSMENT|PLANNING ASSESSMENT|CONSIDERATIONS)",
            r"(?:6\.\s*)?(?:ASSESSMENT|ANALYSIS)",
        ],
        SectionType.DESIGN: [
            r"(?:DESIGN|DESIGN AND APPEARANCE|VISUAL IMPACT)",
        ],
        SectionType.AMENITY: [
            r"(?:AMENITY|RESIDENTIAL AMENITY|IMPACT ON NEIGHBOURS)",
        ],
        SectionType.HERITAGE: [
            r"(?:HERITAGE|CONSERVATION|LISTED BUILDING)",
        ],
        SectionType.CONCLUSION: [
            r"(?:CONCLUSION|RECOMMENDATION|SUMMARY)",
            r"(?:7\.\s*)?(?:CONCLUSION|DECISION)",
        ],
        SectionType.CONDITIONS: [
            r"(?:CONDITIONS|SCHEDULE OF CONDITIONS)",
        ],
        SectionType.REASONS_FOR_REFUSAL: [
            r"(?:REASONS? FOR REFUSAL|REFUSAL REASONS)",
        ],
    }

    # Policy patterns
    POLICY_PATTERNS = [
        (r"Policy\s+([A-Z]\d+)", "Camden"),
        (r"NPPF\s+(?:paragraph\s+)?(\d+)", "NPPF"),
        (r"London\s+Plan\s+(?:Policy\s+)?(\w+)", "London Plan"),
        (r"Section\s+(\d+)", "Legislation"),
        (r"SPD\s+(\w+)", "SPD"),
    ]

    # Condition categories
    CONDITION_CATEGORIES = {
        "time_limit": ["commence", "begin", "start", "within 3 years"],
        "materials": ["materials", "samples", "finishes", "brick", "render"],
        "design": ["design", "details", "drawings", "specification"],
        "amenity": ["hours", "noise", "dust", "construction", "privacy"],
        "highways": ["parking", "access", "highway", "vehicle", "cycle"],
        "landscaping": ["landscaping", "planting", "trees", "garden"],
        "drainage": ["drainage", "surface water", "sewerage", "flood"],
        "contamination": ["contamination", "remediation", "soil"],
        "archaeology": ["archaeological", "heritage", "recording"],
    }

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def analyse_document(
        self,
        text: str,
        document_type: str = "officer_report"
    ) -> DocumentAnalysis:
        """
        Perform comprehensive analysis of a planning document.
        """
        logger.info("analysing_document", doc_type=document_type, length=len(text))

        # Extract sections
        sections = self._extract_sections(text)

        # Extract conditions
        conditions = self._extract_conditions(text)

        # Extract key statements
        key_statements = await self._extract_key_statements(text, sections)

        # Extract policies
        policies = self._extract_policies(text)

        # Determine overall sentiment
        overall_sentiment = self._calculate_overall_sentiment(key_statements)

        # Try to extract case reference
        case_ref = self._extract_case_reference(text)

        # Try to extract outcome
        outcome = self._extract_outcome(text)

        return DocumentAnalysis(
            document_type=document_type,
            case_reference=case_ref,
            outcome=outcome,
            sections=sections,
            conditions=conditions,
            key_statements=key_statements,
            policies_referenced=policies,
            overall_sentiment=overall_sentiment,
            word_count=len(text.split()),
            analysis_timestamp=datetime.utcnow()
        )

    def _extract_sections(self, text: str) -> List[DocumentSection]:
        """Extract and categorise document sections"""
        sections = []

        for section_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                for match in matches:
                    start = match.start()

                    # Find end (next section or end of document)
                    end = len(text)
                    for other_type, other_patterns in self.SECTION_PATTERNS.items():
                        if other_type == section_type:
                            continue
                        for other_pattern in other_patterns:
                            other_matches = re.finditer(other_pattern, text[start+100:], re.IGNORECASE)
                            for other_match in other_matches:
                                potential_end = start + 100 + other_match.start()
                                if potential_end < end and potential_end > start:
                                    end = potential_end
                                break

                    content = text[start:end].strip()

                    if len(content) > 50:  # Minimum content length
                        sections.append(DocumentSection(
                            section_type=section_type,
                            title=match.group(0),
                            content=content[:5000],  # Limit content length
                            start_position=start,
                            end_position=end,
                            key_points=self._extract_key_points(content),
                            policies_mentioned=self._extract_policies(content)
                        ))
                    break  # Only take first match for each pattern

        # Sort by position
        sections.sort(key=lambda x: x.start_position)

        return sections

    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key points from a section"""
        points = []

        # Look for bullet points
        bullet_matches = re.findall(r"[•\-\*]\s*(.+?)(?=\n|$)", text)
        points.extend(bullet_matches[:5])

        # Look for numbered points
        numbered_matches = re.findall(r"\d+\)\s*(.+?)(?=\n|$)", text)
        points.extend(numbered_matches[:5])

        # Look for key phrases
        key_patterns = [
            r"(?:is considered|would be)\s+(\w+\s+\w+\s+\w+)",
            r"(?:the proposal|the development)\s+(.+?)(?:\.|,)",
        ]

        for pattern in key_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            points.extend(matches[:3])

        return list(set(points))[:10]

    def _extract_policies(self, text: str) -> List[str]:
        """Extract policy references from text"""
        policies = []

        for pattern, source in self.POLICY_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                policies.append(f"{source} {match}")

        return list(set(policies))

    def _extract_conditions(self, text: str) -> List[ExtractedCondition]:
        """Extract planning conditions from a decision notice"""
        conditions = []

        # Pattern for numbered conditions
        condition_pattern = r"(?:Condition\s+)?(\d+)[.\)]\s*(.+?)(?=(?:Condition\s+)?\d+[.\)]|Informative|$)"
        matches = re.findall(condition_pattern, text, re.IGNORECASE | re.DOTALL)

        for number, content in matches:
            content = content.strip()[:500]

            # Categorise the condition
            category = "general"
            for cat, keywords in self.CONDITION_CATEGORIES.items():
                if any(kw in content.lower() for kw in keywords):
                    category = cat
                    break

            # Check if submission required
            requires_submission = any(
                phrase in content.lower()
                for phrase in ["submitted to", "approved by", "shall be submitted", "for approval"]
            )

            conditions.append(ExtractedCondition(
                number=int(number),
                text=content,
                category=category,
                requires_submission=requires_submission
            ))

        return conditions

    async def _extract_key_statements(
        self,
        text: str,
        sections: List[DocumentSection]
    ) -> List[OfficerStatement]:
        """Extract key officer statements using LLM"""
        statements = []

        # Get assessment and conclusion sections
        relevant_text = ""
        for section in sections:
            if section.section_type in [SectionType.ASSESSMENT, SectionType.CONCLUSION, SectionType.DESIGN]:
                relevant_text += section.content + "\n\n"

        if not relevant_text:
            relevant_text = text[:3000]

        # Use LLM to extract key statements
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Extract key officer statements from this planning document.
For each statement, identify:
1. The exact quote
2. Sentiment (very_positive, positive, neutral, negative, very_negative)
3. Topic (design, amenity, heritage, policy, conclusion)
4. Whether it's a conclusion statement

Output JSON array:
[{"text": "...", "sentiment": "...", "topic": "...", "is_conclusion": true/false}]"""
                    },
                    {"role": "user", "content": relevant_text[:4000]}
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            result = response.choices[0].message.content
            import json
            data = json.loads(result)

            for item in data.get("statements", data if isinstance(data, list) else []):
                if isinstance(item, dict) and "text" in item:
                    statements.append(OfficerStatement(
                        text=item["text"],
                        sentiment=SentimentLevel(item.get("sentiment", "neutral")),
                        topic=item.get("topic", "general"),
                        is_conclusion=item.get("is_conclusion", False)
                    ))

        except Exception as e:
            logger.warning("statement_extraction_failed", error=str(e))

        return statements

    def _calculate_overall_sentiment(
        self,
        statements: List[OfficerStatement]
    ) -> SentimentLevel:
        """Calculate overall document sentiment"""
        if not statements:
            return SentimentLevel.NEUTRAL

        sentiment_scores = {
            SentimentLevel.VERY_POSITIVE: 2,
            SentimentLevel.POSITIVE: 1,
            SentimentLevel.NEUTRAL: 0,
            SentimentLevel.NEGATIVE: -1,
            SentimentLevel.VERY_NEGATIVE: -2,
        }

        # Weight conclusions more heavily
        total_score = 0
        total_weight = 0

        for stmt in statements:
            weight = 2 if stmt.is_conclusion else 1
            total_score += sentiment_scores[stmt.sentiment] * weight
            total_weight += weight

        avg_score = total_score / total_weight if total_weight else 0

        if avg_score >= 1.5:
            return SentimentLevel.VERY_POSITIVE
        elif avg_score >= 0.5:
            return SentimentLevel.POSITIVE
        elif avg_score >= -0.5:
            return SentimentLevel.NEUTRAL
        elif avg_score >= -1.5:
            return SentimentLevel.NEGATIVE
        else:
            return SentimentLevel.VERY_NEGATIVE

    def _extract_case_reference(self, text: str) -> Optional[str]:
        """Extract case reference from document"""
        pattern = r"(\d{4}/\d{4,5}/[A-Z]+)"
        match = re.search(pattern, text)
        return match.group(1) if match else None

    def _extract_outcome(self, text: str) -> Optional[str]:
        """Extract decision outcome from document"""
        text_lower = text.lower()

        if "permission is granted" in text_lower or "approved" in text_lower:
            return "Granted"
        elif "permission is refused" in text_lower or "refused" in text_lower:
            return "Refused"
        elif "appeal allowed" in text_lower:
            return "Appeal Allowed"
        elif "appeal dismissed" in text_lower:
            return "Appeal Dismissed"

        return None

    async def compare_documents(
        self,
        doc_a_text: str,
        doc_b_text: str,
        doc_a_ref: str,
        doc_b_ref: str
    ) -> DocumentComparison:
        """
        Compare two planning documents.
        """
        # Analyse both documents
        analysis_a = await self.analyse_document(doc_a_text)
        analysis_b = await self.analyse_document(doc_b_text)

        # Find common and divergent policies
        policies_a = set(analysis_a.policies_referenced)
        policies_b = set(analysis_b.policies_referenced)

        common_policies = list(policies_a & policies_b)
        divergent_policies = list(policies_a ^ policies_b)

        # Use LLM to compare
        prompt = f"""Compare these two planning documents:

Document A ({doc_a_ref}):
{doc_a_text[:2000]}

Document B ({doc_b_ref}):
{doc_b_text[:2000]}

Identify:
1. Key similarities in development type, design, context
2. Key differences
3. Why one was approved and one refused (if applicable)
4. Relevance score (0-1) for using one as precedent for the other

Output JSON:
{{"similarities": [...], "differences": [...], "outcome_comparison": "...", "relevance_score": 0.0}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a planning document analyst."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            return DocumentComparison(
                document_a_ref=doc_a_ref,
                document_b_ref=doc_b_ref,
                similarities=result.get("similarities", []),
                differences=result.get("differences", []),
                common_policies=common_policies,
                divergent_policies=divergent_policies,
                outcome_comparison=result.get("outcome_comparison", ""),
                relevance_score=result.get("relevance_score", 0.5)
            )

        except Exception as e:
            logger.error("document_comparison_failed", error=str(e))
            return DocumentComparison(
                document_a_ref=doc_a_ref,
                document_b_ref=doc_b_ref,
                similarities=[],
                differences=[],
                common_policies=common_policies,
                divergent_policies=divergent_policies,
                outcome_comparison="Comparison failed",
                relevance_score=0.0
            )
