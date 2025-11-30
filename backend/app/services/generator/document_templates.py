"""
Document Templates
Pre-defined templates for common planning documents
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class TemplateCategory(str, Enum):
    """Template categories"""
    HOUSEHOLDER = "householder"
    COMMERCIAL = "commercial"
    LISTED_BUILDING = "listed_building"
    CONSERVATION = "conservation"
    APPEAL = "appeal"


@dataclass
class DocumentTemplate:
    """A document template"""
    id: str
    name: str
    category: TemplateCategory
    description: str
    sections: List[Dict]
    variables: List[str]
    example_content: Optional[str] = None


class DocumentTemplates:
    """Manages document templates"""

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, DocumentTemplate]:
        """Load all templates"""
        return {
            "rear_extension": DocumentTemplate(
                id="rear_extension",
                name="Rear Extension Design Statement",
                category=TemplateCategory.HOUSEHOLDER,
                description="Design statement for single/double storey rear extensions",
                sections=[
                    {"id": "intro", "title": "Introduction", "required": True},
                    {"id": "site", "title": "Site Analysis", "required": True},
                    {"id": "proposal", "title": "The Proposal", "required": True},
                    {"id": "design", "title": "Design Rationale", "required": True},
                    {"id": "materials", "title": "Materials", "required": True},
                    {"id": "impact", "title": "Neighbour Impact", "required": True},
                    {"id": "policy", "title": "Policy Compliance", "required": True},
                    {"id": "conclusion", "title": "Conclusion", "required": True}
                ],
                variables=[
                    "site_address", "postcode", "ward", "extension_depth",
                    "extension_height", "materials", "conservation_area"
                ]
            ),

            "basement_extension": DocumentTemplate(
                id="basement_extension",
                name="Basement Extension Statement",
                category=TemplateCategory.HOUSEHOLDER,
                description="Design and impact statement for basement developments",
                sections=[
                    {"id": "intro", "title": "Introduction", "required": True},
                    {"id": "site", "title": "Site Analysis", "required": True},
                    {"id": "basement", "title": "Basement Proposal", "required": True},
                    {"id": "lightwell", "title": "Lightwell Design", "required": True},
                    {"id": "garden", "title": "Garden Retention", "required": True},
                    {"id": "structural", "title": "Structural Approach", "required": True},
                    {"id": "drainage", "title": "Drainage Strategy", "required": True},
                    {"id": "construction", "title": "Construction Management", "required": True},
                    {"id": "policy", "title": "Policy Compliance", "required": True}
                ],
                variables=[
                    "site_address", "basement_depth", "basement_extent",
                    "lightwell_dimensions", "garden_retention_percentage"
                ]
            ),

            "loft_conversion": DocumentTemplate(
                id="loft_conversion",
                name="Loft Conversion Statement",
                category=TemplateCategory.HOUSEHOLDER,
                description="Design statement for loft conversions and dormers",
                sections=[
                    {"id": "intro", "title": "Introduction", "required": True},
                    {"id": "site", "title": "Site and Street Context", "required": True},
                    {"id": "proposal", "title": "The Proposal", "required": True},
                    {"id": "dormer", "title": "Dormer Design", "required": True},
                    {"id": "roofscape", "title": "Roofscape Analysis", "required": True},
                    {"id": "materials", "title": "Materials", "required": True},
                    {"id": "policy", "title": "Policy Compliance", "required": True}
                ],
                variables=[
                    "site_address", "dormer_width", "dormer_type",
                    "roof_materials", "window_type"
                ]
            ),

            "heritage_statement": DocumentTemplate(
                id="heritage_statement",
                name="Heritage Impact Assessment",
                category=TemplateCategory.CONSERVATION,
                description="Heritage statement for conservation areas and listed buildings",
                sections=[
                    {"id": "intro", "title": "Introduction", "required": True},
                    {"id": "statutory", "title": "Statutory Framework", "required": True},
                    {"id": "history", "title": "Historical Development", "required": True},
                    {"id": "significance", "title": "Heritage Significance", "required": True},
                    {"id": "impact", "title": "Impact Assessment", "required": True},
                    {"id": "justification", "title": "Justification", "required": True},
                    {"id": "conclusion", "title": "Conclusion", "required": True}
                ],
                variables=[
                    "site_address", "conservation_area", "listed_grade",
                    "designation_date", "special_interest"
                ]
            ),

            "appeal_statement": DocumentTemplate(
                id="appeal_statement",
                name="Appeal Statement",
                category=TemplateCategory.APPEAL,
                description="Statement in support of planning appeal",
                sections=[
                    {"id": "intro", "title": "Introduction", "required": True},
                    {"id": "background", "title": "Application Background", "required": True},
                    {"id": "refusal", "title": "Reason for Refusal", "required": True},
                    {"id": "grounds", "title": "Grounds of Appeal", "required": True},
                    {"id": "precedents", "title": "Relevant Precedents", "required": True},
                    {"id": "inspector", "title": "Appeal Decisions", "required": True},
                    {"id": "conclusion", "title": "Conclusion", "required": True}
                ],
                variables=[
                    "site_address", "application_reference", "refusal_date",
                    "refusal_reasons", "appeal_type"
                ]
            ),

            "covering_letter": DocumentTemplate(
                id="covering_letter",
                name="Application Covering Letter",
                category=TemplateCategory.HOUSEHOLDER,
                description="Standard covering letter for planning applications",
                sections=[
                    {"id": "addressee", "title": "Addressee", "required": True},
                    {"id": "subject", "title": "Subject", "required": True},
                    {"id": "application", "title": "Application Details", "required": True},
                    {"id": "documents", "title": "Enclosed Documents", "required": True},
                    {"id": "fee", "title": "Fee", "required": True},
                    {"id": "summary", "title": "Proposal Summary", "required": True},
                    {"id": "closing", "title": "Closing", "required": True}
                ],
                variables=[
                    "site_address", "application_type", "proposal_description",
                    "fee_amount", "applicant_name", "agent_name"
                ]
            )
        }

    def get_template(self, template_id: str) -> Optional[DocumentTemplate]:
        """Get a specific template"""
        return self.templates.get(template_id)

    def list_templates(
        self,
        category: TemplateCategory = None
    ) -> List[DocumentTemplate]:
        """List available templates"""
        templates = list(self.templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        return templates

    def render_template(
        self,
        template_id: str,
        variables: Dict[str, str],
        section_content: Dict[str, str] = None
    ) -> Optional[str]:
        """Render a template with provided content"""
        template = self.get_template(template_id)
        if not template:
            return None

        section_content = section_content or {}

        # Build document
        lines = []
        lines.append(f"# {template.name}")
        lines.append("")
        lines.append(f"**Site:** {variables.get('site_address', '[Address]')}")
        lines.append(f"**Date:** [Date]")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, section in enumerate(template.sections, 1):
            lines.append(f"## {i}. {section['title']}")
            lines.append("")

            content = section_content.get(section['id'])
            if content:
                lines.append(content)
            else:
                lines.append(f"[{section['title']} content]")

            lines.append("")

        return "\n".join(lines)

    def get_section_prompts(self, template_id: str) -> Dict[str, str]:
        """Get writing prompts for each section"""
        prompts = {
            "intro": "Introduce the application, identifying the site and proposal briefly.",
            "site": "Describe the site location, existing building, and surrounding context.",
            "proposal": "Describe the proposed development in detail.",
            "design": "Explain the design approach and how it responds to context.",
            "materials": "Specify proposed materials and justify their selection.",
            "impact": "Assess impact on neighbouring amenity (daylight, privacy, outlook).",
            "policy": "Demonstrate compliance with relevant planning policies.",
            "conclusion": "Summarise why the proposal should be approved.",
            "significance": "Explain the heritage significance of the asset.",
            "justification": "Justify any impact on heritage significance.",
            "refusal": "Set out the Council's reasons for refusal.",
            "grounds": "Present the grounds on which the appeal is made.",
            "precedents": "Present relevant precedent cases that support the proposal."
        }
        return prompts

    def get_word_counts(self, template_id: str) -> Dict[str, int]:
        """Get recommended word counts for each section"""
        counts = {
            "intro": 150,
            "site": 300,
            "proposal": 400,
            "design": 500,
            "materials": 200,
            "impact": 400,
            "policy": 600,
            "conclusion": 200,
            "significance": 500,
            "justification": 400,
            "refusal": 300,
            "grounds": 800,
            "precedents": 500
        }
        return counts
