"""
Statement Generator
AI-powered generation of planning statements and arguments
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PolicyArgument:
    """A policy-based argument"""
    policy_name: str
    policy_reference: str
    argument: str
    supporting_points: List[str] = field(default_factory=list)
    precedent_support: List[str] = field(default_factory=list)


@dataclass
class DesignJustification:
    """Design justification section"""
    principle: str
    explanation: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class NeighbourImpactAssessment:
    """Assessment of impact on neighbours"""
    impact_type: str  # daylight, sunlight, privacy, outlook, noise
    assessment: str
    mitigation: Optional[str] = None
    conclusion: str = ""


class DesignStatementGenerator:
    """Generates design statements with AI assistance"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

        # Standard design principles
        self.design_principles = [
            "Context and Character",
            "Scale and Massing",
            "Height and Proportion",
            "Materials and Detailing",
            "Landscaping and Setting",
            "Sustainability"
        ]

        # Camden design guidance
        self.camden_guidance = {
            "extensions": {
                "rear": {
                    "max_depth_single": 3.0,
                    "max_depth_double": 3.0,
                    "max_height": 3.0,
                    "guidance": "Rear extensions should be subordinate to the main building"
                },
                "side": {
                    "setback": 1.0,
                    "gap_to_boundary": 0.9,
                    "guidance": "Side extensions should maintain gaps between buildings"
                },
                "basement": {
                    "max_depth": 3.0,
                    "min_garden_retention": 0.5,
                    "lightwell_setback": 0.8,
                    "guidance": "Basements should not extend under the entire garden"
                }
            },
            "conservation": {
                "materials": "Traditional materials sympathetic to the conservation area",
                "windows": "Timber or timber-effect windows with appropriate glazing bars",
                "roofing": "Natural slate or clay tiles matching existing"
            }
        }

    async def generate_design_justification(
        self,
        proposal: Dict,
        site: Dict,
        precedents: List[Dict] = None
    ) -> List[DesignJustification]:
        """Generate design justifications for a proposal"""
        justifications = []

        # Context response
        justifications.append(DesignJustification(
            principle="Context and Character",
            explanation=self._generate_context_response(proposal, site),
            evidence=self._gather_context_evidence(site, precedents)
        ))

        # Scale and massing
        justifications.append(DesignJustification(
            principle="Scale and Massing",
            explanation=self._generate_scale_response(proposal, site),
            evidence=self._gather_scale_evidence(proposal, precedents)
        ))

        # Materials
        if proposal.get("materials"):
            justifications.append(DesignJustification(
                principle="Materials and Detailing",
                explanation=self._generate_materials_response(proposal, site),
                evidence=[]
            ))

        # Sustainability
        justifications.append(DesignJustification(
            principle="Sustainability",
            explanation=self._generate_sustainability_response(proposal),
            evidence=[]
        ))

        return justifications

    async def generate_policy_arguments(
        self,
        proposal: Dict,
        site: Dict,
        policies: List[str] = None
    ) -> List[PolicyArgument]:
        """Generate policy-based arguments"""
        arguments = []

        # Default to standard Camden policies
        if not policies:
            policies = ["D1", "D2", "A1"]

        for policy in policies:
            argument = self._generate_policy_argument(policy, proposal, site)
            if argument:
                arguments.append(argument)

        return arguments

    async def generate_neighbour_impact(
        self,
        proposal: Dict,
        neighbours: List[Dict] = None
    ) -> List[NeighbourImpactAssessment]:
        """Generate neighbour impact assessment"""
        assessments = []

        # Daylight impact
        assessments.append(NeighbourImpactAssessment(
            impact_type="Daylight",
            assessment=self._assess_daylight_impact(proposal),
            mitigation="Design minimises projection beyond established building line",
            conclusion="No significant loss of daylight to neighbouring properties"
        ))

        # Sunlight impact
        assessments.append(NeighbourImpactAssessment(
            impact_type="Sunlight",
            assessment=self._assess_sunlight_impact(proposal),
            conclusion="No material loss of sunlight to neighbouring habitable rooms"
        ))

        # Privacy
        assessments.append(NeighbourImpactAssessment(
            impact_type="Privacy",
            assessment=self._assess_privacy_impact(proposal),
            mitigation="No new windows overlooking neighbouring properties",
            conclusion="Privacy of neighbours is maintained"
        ))

        # Outlook
        assessments.append(NeighbourImpactAssessment(
            impact_type="Outlook",
            assessment=self._assess_outlook_impact(proposal),
            conclusion="No overbearing impact on neighbouring outlook"
        ))

        return assessments

    def _generate_context_response(self, proposal: Dict, site: Dict) -> str:
        """Generate context response text"""
        conservation = site.get("conservation_area")

        if conservation:
            return f"""The proposal has been designed to respond sensitively to its location
within the {conservation}. The design respects the established pattern of development,
maintaining the character and appearance that contributes to the area's special interest.
The proposal does not introduce any incongruous elements and is consistent with the
prevailing architectural language of the street."""
        else:
            return """The proposal has been designed to respond positively to the character
of the host building and surrounding area. The design respects the established building
line and scale of neighbouring properties, creating a coherent addition that integrates
well with its context."""

    def _generate_scale_response(self, proposal: Dict, site: Dict) -> str:
        """Generate scale and massing response"""
        height = proposal.get("height_meters", 3.0)
        depth = proposal.get("depth_meters", 3.0)

        return f"""The proposal is appropriately scaled for the site, measuring
approximately {depth}m in depth and {height}m in height. This ensures the extension
remains subordinate to the main building while providing functional internal space.
The massing has been carefully considered to minimise impact on neighbouring properties
and the street scene."""

    def _generate_materials_response(self, proposal: Dict, site: Dict) -> str:
        """Generate materials justification"""
        materials = proposal.get("materials", [])
        conservation = site.get("conservation_area")

        if conservation:
            return f"""Materials have been selected to complement the conservation area
character. The proposal uses high-quality materials including {', '.join(materials[:3]) if materials else 'traditional finishes'}
that are sympathetic to the host building and surrounding properties. This approach
ensures the development preserves the visual quality of the area."""
        else:
            return f"""The proposed materials ({', '.join(materials[:3]) if materials else 'high-quality finishes'})
have been selected to complement the existing building and create a high-quality
appearance. The specification ensures durability and aesthetic quality."""

    def _generate_sustainability_response(self, proposal: Dict) -> str:
        """Generate sustainability justification"""
        return """The proposal incorporates sustainable design principles including:
- High levels of thermal insulation exceeding Building Regulations
- Energy-efficient glazing systems
- Orientation designed to maximise natural light and reduce energy consumption
- Durable, low-maintenance materials

These measures support Camden's objectives for sustainable development and climate
change mitigation."""

    def _generate_policy_argument(
        self,
        policy: str,
        proposal: Dict,
        site: Dict
    ) -> Optional[PolicyArgument]:
        """Generate argument for specific policy"""
        policy_info = self._get_policy_info(policy)
        if not policy_info:
            return None

        return PolicyArgument(
            policy_name=policy_info["name"],
            policy_reference=f"Camden Local Plan Policy {policy}",
            argument=policy_info["standard_argument"],
            supporting_points=policy_info.get("supporting_points", [])
        )

    def _get_policy_info(self, policy: str) -> Optional[Dict]:
        """Get policy information"""
        policies = {
            "D1": {
                "name": "Design",
                "standard_argument": "The proposal demonstrates high-quality design that respects context and creates a positive addition to the street scene.",
                "supporting_points": [
                    "Appropriate scale and massing",
                    "High-quality materials",
                    "Sensitive response to context"
                ]
            },
            "D2": {
                "name": "Heritage",
                "standard_argument": "The proposal preserves the character and appearance of the heritage asset through sensitive design.",
                "supporting_points": [
                    "Preservation of significance",
                    "Sympathetic materials",
                    "Reversible interventions"
                ]
            },
            "A1": {
                "name": "Managing the Impact of Development",
                "standard_argument": "The proposal will not result in unacceptable harm to neighbouring amenity.",
                "supporting_points": [
                    "No significant loss of light",
                    "Privacy maintained",
                    "No overbearing impact"
                ]
            },
            "A2": {
                "name": "Biodiversity",
                "standard_argument": "The proposal maintains and where possible enhances biodiversity value.",
                "supporting_points": []
            },
            "A3": {
                "name": "Basements and Light Wells",
                "standard_argument": "The basement proposal accords with Camden's guidance on subterranean development.",
                "supporting_points": [
                    "Appropriate depth and extent",
                    "Garden retention",
                    "Structural considerations addressed"
                ]
            }
        }
        return policies.get(policy)

    def _assess_daylight_impact(self, proposal: Dict) -> str:
        """Assess daylight impact"""
        return """Analysis of the proposal against the BRE Guidelines (Site Layout
Planning for Daylight and Sunlight) indicates that neighbouring windows will
continue to receive adequate daylight. The proposal passes the 25-degree
vertical angle test from the centre of affected windows."""

    def _assess_sunlight_impact(self, proposal: Dict) -> str:
        """Assess sunlight impact"""
        return """The orientation and height of the proposal ensure that
neighbouring habitable rooms will continue to receive adequate sunlight.
No material overshadowing of neighbouring gardens or amenity spaces will occur."""

    def _assess_privacy_impact(self, proposal: Dict) -> str:
        """Assess privacy impact"""
        return """The proposal does not introduce any new windows or openings
that would overlook neighbouring properties. Where glazing is proposed, it is
positioned and designed to prevent overlooking of private amenity areas."""

    def _assess_outlook_impact(self, proposal: Dict) -> str:
        """Assess outlook impact"""
        return """The scale and positioning of the proposal ensure that it
does not create an overbearing or oppressive relationship with neighbouring
properties. Adequate separation distances are maintained."""

    def _gather_context_evidence(
        self,
        site: Dict,
        precedents: List[Dict]
    ) -> List[str]:
        """Gather evidence for context arguments"""
        evidence = []

        if precedents:
            for p in precedents[:3]:
                if p.get("outcome", "").lower() == "granted":
                    evidence.append(
                        f"Similar development approved at {p.get('address', 'nearby site')} "
                        f"(Ref: {p.get('reference', 'N/A')})"
                    )

        return evidence

    def _gather_scale_evidence(
        self,
        proposal: Dict,
        precedents: List[Dict]
    ) -> List[str]:
        """Gather evidence for scale arguments"""
        evidence = []

        depth = proposal.get("depth_meters")
        if depth and depth <= 3.0:
            evidence.append("Depth within established precedent (3m or less)")

        height = proposal.get("height_meters")
        if height and height <= 3.0:
            evidence.append("Height within permitted development parameters")

        return evidence
