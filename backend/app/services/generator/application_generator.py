"""
Application Generator
Generates complete planning application documents
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ApplicationType(str, Enum):
    """Types of planning applications"""
    HOUSEHOLDER = "householder"  # Most common - extensions, alterations
    FULL = "full"  # Full planning permission
    OUTLINE = "outline"  # Outline with reserved matters
    LISTED_BUILDING = "listed_building"
    CONSERVATION_AREA = "conservation_area"
    PRIOR_APPROVAL = "prior_approval"  # Permitted development checks
    LAWFUL_DEVELOPMENT = "lawful_development"  # Certificate of lawfulness
    TREE_WORKS = "tree_works"


class DocumentType(str, Enum):
    """Types of application documents"""
    APPLICATION_FORM = "application_form"
    DESIGN_STATEMENT = "design_statement"
    PLANNING_STATEMENT = "planning_statement"
    HERITAGE_STATEMENT = "heritage_statement"
    TREE_REPORT = "tree_report"
    COVERING_LETTER = "covering_letter"
    CIL_FORM = "cil_form"  # Community Infrastructure Levy


@dataclass
class Applicant:
    """Applicant details"""
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    is_agent: bool = False


@dataclass
class SiteDetails:
    """Site information"""
    address: str
    postcode: str
    ward: Optional[str] = None
    conservation_area: Optional[str] = None
    listed_building: Optional[str] = None
    article_4_direction: bool = False
    tree_preservation_order: bool = False
    flood_zone: Optional[str] = None
    # Grid reference
    easting: Optional[int] = None
    northing: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class ProposalDetails:
    """Details of the proposed development"""
    description: str
    development_type: str
    # Dimensions
    existing_floor_area_sqm: Optional[float] = None
    proposed_floor_area_sqm: Optional[float] = None
    height_meters: Optional[float] = None
    depth_meters: Optional[float] = None
    width_meters: Optional[float] = None
    # Specifics
    materials: List[str] = field(default_factory=list)
    design_features: List[str] = field(default_factory=list)
    landscaping_changes: Optional[str] = None
    parking_changes: Optional[str] = None
    # Justification
    need_for_development: Optional[str] = None
    design_rationale: Optional[str] = None


@dataclass
class ApplicationData:
    """Complete application data"""
    application_type: ApplicationType
    applicant: Applicant
    site: SiteDetails
    proposal: ProposalDetails
    # Agent (if different from applicant)
    agent: Optional[Applicant] = None
    # Supporting evidence
    precedent_cases: List[Dict] = field(default_factory=list)
    policy_references: List[str] = field(default_factory=list)
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    reference_id: Optional[str] = None


@dataclass
class GeneratedDocument:
    """A generated application document"""
    document_type: DocumentType
    title: str
    content: str
    format: str = "markdown"  # markdown, html, pdf
    metadata: Dict[str, Any] = field(default_factory=dict)


class ApplicationGenerator:
    """Generates planning application documents"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

        # Camden-specific policies
        self.camden_policies = {
            "extensions": ["D1", "D2", "A1", "A2"],
            "basement": ["D1", "D2", "A3", "A6"],
            "loft": ["D1", "D2", "A1"],
            "conservation": ["D1", "D2", "D5", "A1"],
            "listed_building": ["D1", "D5", "A1"]
        }

        # Standard application fees (2024)
        self.fees = {
            ApplicationType.HOUSEHOLDER: 258,
            ApplicationType.FULL: 528,
            ApplicationType.LISTED_BUILDING: 0,
            ApplicationType.CONSERVATION_AREA: 0,
            ApplicationType.PRIOR_APPROVAL: 120,
            ApplicationType.LAWFUL_DEVELOPMENT: 129
        }

    async def generate_application(
        self,
        data: ApplicationData
    ) -> List[GeneratedDocument]:
        """Generate all required documents for an application"""
        documents = []

        # Always generate covering letter
        covering_letter = await self._generate_covering_letter(data)
        documents.append(covering_letter)

        # Generate design & access statement
        design_statement = await self._generate_design_statement(data)
        documents.append(design_statement)

        # Add heritage statement if in conservation area
        if data.site.conservation_area:
            heritage = await self._generate_heritage_statement(data)
            documents.append(heritage)

        # Add planning statement for full applications
        if data.application_type in [ApplicationType.FULL, ApplicationType.OUTLINE]:
            planning = await self._generate_planning_statement(data)
            documents.append(planning)

        # Generate application form data
        form_data = self._generate_form_data(data)
        documents.append(form_data)

        return documents

    async def _generate_covering_letter(
        self,
        data: ApplicationData
    ) -> GeneratedDocument:
        """Generate covering letter"""
        fee = self.fees.get(data.application_type, 0)

        content = f"""# Planning Application Covering Letter

**Date:** {datetime.now().strftime('%d %B %Y')}

**To:** Planning Services
London Borough of Camden
5 Pancras Square
London N1C 4AG

**Reference:** {data.reference_id or 'TBC'}

## Application for {data.application_type.value.replace('_', ' ').title()}

**Site Address:** {data.site.address}, {data.site.postcode}

Dear Planning Officer,

Please find enclosed a {data.application_type.value.replace('_', ' ')} planning application for the following development:

> {data.proposal.description}

### Enclosed Documents

The following documents are submitted in support of this application:

1. Completed application form
2. Site location plan (scale 1:1250 or 1:2500)
3. Block plan (scale 1:500 or 1:200)
4. Existing and proposed floor plans
5. Existing and proposed elevations
6. Design and Access Statement
{"7. Heritage Statement" if data.site.conservation_area else ""}

### Application Fee

The prescribed fee of **£{fee}** is {"enclosed" if fee > 0 else "not applicable"}.

### Site Context

{f"The site is located within the **{data.site.conservation_area}**." if data.site.conservation_area else ""}
{f"The property is a **Grade {data.site.listed_building} Listed Building**." if data.site.listed_building else ""}
The site is within **{data.site.ward or 'Camden'}** ward.

### Proposal Summary

{data.proposal.description}

{f"**Floor Area:** The proposal will add approximately {data.proposal.proposed_floor_area_sqm - data.proposal.existing_floor_area_sqm:.1f} sqm." if data.proposal.proposed_floor_area_sqm and data.proposal.existing_floor_area_sqm else ""}

### Planning Justification

This application is supported by careful analysis of relevant planning policies and local precedents:

- **Camden Local Plan 2017:** Policies {', '.join(data.policy_references[:4]) if data.policy_references else 'D1, D2, A1'}
- **London Plan 2021:** Design and housing policies
- **NPPF 2023:** Paragraphs 126-136 (Design)

{"The enclosed Design and Access Statement and Heritage Statement provide detailed justification for the proposal." if data.site.conservation_area else "The enclosed Design and Access Statement provides detailed justification for the proposal."}

{"### Precedent Cases" if data.precedent_cases else ""}
{"We have identified " + str(len(data.precedent_cases)) + " relevant precedent cases demonstrating that similar proposals have been approved in the area." if data.precedent_cases else ""}

### Pre-Application Advice

[Include reference to any pre-application advice received, or state that no formal advice was sought]

### Conclusion

We trust that the enclosed documents demonstrate that this proposal accords with development plan policies and would represent an acceptable form of development. We respectfully request that planning permission be granted.

Should you require any further information, please do not hesitate to contact us.

Yours faithfully,

**{data.agent.name if data.agent else data.applicant.name}**
{f"Agent for {data.applicant.name}" if data.agent else "Applicant"}
{data.agent.email if data.agent else data.applicant.email}
{data.agent.phone if data.agent and data.agent.phone else data.applicant.phone or ''}
"""

        return GeneratedDocument(
            document_type=DocumentType.COVERING_LETTER,
            title="Covering Letter",
            content=content
        )

    async def _generate_design_statement(
        self,
        data: ApplicationData
    ) -> GeneratedDocument:
        """Generate design and access statement"""
        content = f"""# Design and Access Statement

**Site:** {data.site.address}, {data.site.postcode}
**Application Type:** {data.application_type.value.replace('_', ' ').title()}
**Date:** {datetime.now().strftime('%B %Y')}

---

## 1. Introduction

This Design and Access Statement has been prepared in support of a planning application for:

> {data.proposal.description}

The statement sets out the design rationale and demonstrates how the proposal responds to its context while meeting relevant planning policies.

## 2. Site Analysis

### 2.1 Site Location
The application site is located at **{data.site.address}**, within the **{data.site.ward or 'Camden'}** ward of the London Borough of Camden.

{f"**Conservation Area:** The site lies within the {data.site.conservation_area}." if data.site.conservation_area else ""}
{f"**Listed Building:** The property is Grade {data.site.listed_building} listed." if data.site.listed_building else ""}

### 2.2 Existing Building
[Description of the existing building - type, age, architectural style, condition]

### 2.3 Site Context
[Description of surrounding properties, street character, prevailing architectural styles]

## 3. Design Rationale

### 3.1 Proposal Overview
{data.proposal.description}

{f"**Design Features:**" if data.proposal.design_features else ""}
{chr(10).join(f"- {feature}" for feature in data.proposal.design_features) if data.proposal.design_features else ""}

### 3.2 Design Principles

The design has been developed with the following principles:

1. **Respect for Context:** The proposal respects the character and appearance of the host building and surrounding area.

2. **Subordination:** {f"At {data.proposal.height_meters}m in height, the extension remains subordinate to the main building." if data.proposal.height_meters else "The proposal is subordinate to the main building."}

3. **Material Quality:** {f"High-quality materials including {', '.join(data.proposal.materials[:3])}." if data.proposal.materials else "High-quality materials complementing the existing building."}

4. **Amenity Protection:** The design protects neighbouring amenity in terms of daylight, sunlight, and privacy.

### 3.3 Scale and Massing

{f"**Dimensions:** The proposal measures approximately {data.proposal.depth_meters}m deep x {data.proposal.width_meters}m wide x {data.proposal.height_meters}m high." if data.proposal.depth_meters else "The proposal is appropriately scaled for the site."}

The scale has been informed by analysis of the host building and surrounding context.

### 3.4 Appearance

The external appearance has been designed to:
- Complement the existing building
- Respect the character of the street scene
{f"- Preserve the significance of the {data.site.conservation_area}" if data.site.conservation_area else ""}

## 4. Policy Compliance

### 4.1 Camden Local Plan 2017

The proposal accords with the following policies:

**Policy D1 - Design:**
The proposal demonstrates high-quality design that respects context and protects amenity.

**Policy D2 - Heritage:**
{f"The proposal preserves the character and appearance of the {data.site.conservation_area}." if data.site.conservation_area else "Heritage considerations have been appropriately addressed."}

**Policy A1 - Managing the Impact of Development:**
The proposal will not result in unacceptable harm to neighbouring amenity.

### 4.2 London Plan 2021

The design responds positively to Policy D3 (Optimising site capacity through the design-led approach) and Policy D4 (Delivering good design).

### 4.3 NPPF 2023

The proposal accords with Section 12 (Achieving well-designed places), in particular paragraphs 126-136.

## 5. Access

### 5.1 Pedestrian Access
Existing pedestrian access arrangements will be maintained.

### 5.2 Vehicular Access
{data.proposal.parking_changes or "No changes to existing vehicular access or parking arrangements."}

### 5.3 Inclusive Access
The proposal has been designed to ensure accessibility for all users where practicable.

## 6. Precedent Analysis

{"The following approved precedents demonstrate that similar proposals have been considered acceptable:" if data.precedent_cases else ""}

{chr(10).join(f"- **{case.get('reference')}** ({case.get('address', 'Camden')}): {case.get('description', 'Similar development approved')}" for case in data.precedent_cases[:5]) if data.precedent_cases else ""}

## 7. Conclusion

This Design and Access Statement demonstrates that the proposed development:

1. Responds positively to the character and appearance of the site and surrounding area
2. Is of high-quality design using appropriate materials
3. Protects neighbouring amenity
4. Accords with relevant development plan policies
{f"5. Preserves the character and appearance of the {data.site.conservation_area}" if data.site.conservation_area else ""}

We respectfully request that planning permission be granted.

---

*Prepared by: {data.agent.name if data.agent else data.applicant.name}*
*Date: {datetime.now().strftime('%d %B %Y')}*
"""

        return GeneratedDocument(
            document_type=DocumentType.DESIGN_STATEMENT,
            title="Design and Access Statement",
            content=content
        )

    async def _generate_heritage_statement(
        self,
        data: ApplicationData
    ) -> GeneratedDocument:
        """Generate heritage impact assessment"""
        content = f"""# Heritage Statement

**Site:** {data.site.address}, {data.site.postcode}
**Date:** {datetime.now().strftime('%B %Y')}

---

## 1. Introduction

This Heritage Statement has been prepared to accompany a planning application for works at the above property, which is located within the **{data.site.conservation_area}**.

{f"The property is also a **Grade {data.site.listed_building} Listed Building**." if data.site.listed_building else ""}

## 2. Statutory and Policy Framework

### 2.1 Statutory Requirements

**Planning (Listed Buildings and Conservation Areas) Act 1990:**
- Section 66: Duty to have special regard to preserving listed buildings
- Section 72: Duty to preserve or enhance the character of conservation areas

**NPPF 2023:**
- Paragraph 197: When considering designated heritage assets
- Paragraph 199: Great weight to conservation
- Paragraph 200: Any harm requires clear justification

### 2.2 Development Plan Policies

**Camden Local Plan Policy D2 (Heritage):**
The Council will preserve Camden's rich and diverse heritage assets.

## 3. Heritage Significance

### 3.1 Conservation Area Character

The {data.site.conservation_area} is characterised by:
[Description of the conservation area's special interest and character]

### 3.2 Subject Property

The application property contributes to the conservation area through:
[Description of the building's heritage significance]

## 4. Impact Assessment

### 4.1 Proposed Development

{data.proposal.description}

### 4.2 Impact on Heritage Significance

The proposal has been designed to:

1. **Preserve** the architectural and historic interest of the host building
2. **Respect** the character and appearance of the conservation area
3. **Minimise** visual impact through appropriate design and materials
{f"4. **Protect** the special interest of the listed building" if data.site.listed_building else ""}

### 4.3 Design Mitigation

The following measures ensure heritage preservation:

- Use of sympathetic materials: {', '.join(data.proposal.materials[:3]) if data.proposal.materials else 'Traditional materials matching existing'}
- Subordinate scale and massing
- Retention of historic features
- Reversible interventions where possible

## 5. Policy Compliance

The proposal accords with:

- **Camden Local Plan Policy D2:** The design preserves the heritage significance
- **London Plan Policy HC1:** Heritage assets are conserved and enhanced
- **NPPF Paragraphs 197-208:** The proposal causes no harm to significance

## 6. Conclusion

This Heritage Statement demonstrates that the proposal:

1. Has been developed with full understanding of heritage significance
2. Preserves the character and appearance of the conservation area
3. Causes no harm to designated heritage assets
4. Complies with statutory duties and policy requirements

The proposal therefore satisfies the heritage policy tests and should be considered acceptable.

---

*Prepared by: {data.agent.name if data.agent else data.applicant.name}*
*Date: {datetime.now().strftime('%d %B %Y')}*
"""

        return GeneratedDocument(
            document_type=DocumentType.HERITAGE_STATEMENT,
            title="Heritage Statement",
            content=content
        )

    async def _generate_planning_statement(
        self,
        data: ApplicationData
    ) -> GeneratedDocument:
        """Generate full planning statement"""
        content = f"""# Planning Statement

**Site:** {data.site.address}, {data.site.postcode}
**Application Type:** {data.application_type.value.replace('_', ' ').title()}
**Date:** {datetime.now().strftime('%B %Y')}

---

## Executive Summary

This Planning Statement supports an application for planning permission at the above site for:

> {data.proposal.description}

The statement demonstrates that the proposal accords with the Development Plan and should be approved.

## 1. Site and Surroundings

### Location and Context
[Detailed description of site location, surrounding uses, transport links]

### Planning History
[Relevant planning history of the site]

## 2. Proposed Development

{data.proposal.description}

{f"The development will provide {data.proposal.proposed_floor_area_sqm:.0f} sqm of floor space." if data.proposal.proposed_floor_area_sqm else ""}

## 3. Planning Policy Framework

### National Policy
- NPPF 2023

### Regional Policy
- London Plan 2021

### Local Policy
- Camden Local Plan 2017
- Relevant SPDs and guidance

## 4. Planning Assessment

[Detailed policy-by-policy assessment]

## 5. Conclusion

The proposal accords with the Development Plan and should be approved.

---

*Prepared by: {data.agent.name if data.agent else data.applicant.name}*
"""

        return GeneratedDocument(
            document_type=DocumentType.PLANNING_STATEMENT,
            title="Planning Statement",
            content=content
        )

    def _generate_form_data(self, data: ApplicationData) -> GeneratedDocument:
        """Generate application form data as structured JSON"""
        form_data = {
            "application_type": data.application_type.value,
            "site": {
                "address": data.site.address,
                "postcode": data.site.postcode,
                "ward": data.site.ward,
                "easting": data.site.easting,
                "northing": data.site.northing
            },
            "applicant": {
                "name": data.applicant.name,
                "email": data.applicant.email,
                "phone": data.applicant.phone,
                "address": data.applicant.address
            },
            "agent": {
                "name": data.agent.name if data.agent else None,
                "email": data.agent.email if data.agent else None
            } if data.agent else None,
            "proposal": {
                "description": data.proposal.description,
                "existing_use": "Residential",
                "proposed_use": "Residential",
                "existing_floor_area": data.proposal.existing_floor_area_sqm,
                "proposed_floor_area": data.proposal.proposed_floor_area_sqm
            },
            "fee": self.fees.get(data.application_type, 0),
            "declarations": {
                "ownership_certificate": "A",
                "agricultural_holding": False
            }
        }

        import json
        content = json.dumps(form_data, indent=2)

        return GeneratedDocument(
            document_type=DocumentType.APPLICATION_FORM,
            title="Application Form Data",
            content=content,
            format="json"
        )

    def get_required_documents(
        self,
        application_type: ApplicationType,
        site: SiteDetails
    ) -> List[str]:
        """Get list of required documents for application type"""
        base_docs = [
            "Application form",
            "Site location plan (1:1250 or 1:2500)",
            "Block plan (1:500 or 1:200)",
            "Existing and proposed floor plans",
            "Existing and proposed elevations",
            "Design and Access Statement"
        ]

        if site.conservation_area:
            base_docs.append("Heritage Statement")

        if site.listed_building:
            base_docs.extend([
                "Listed Building Heritage Statement",
                "Photographs of existing building"
            ])

        if application_type == ApplicationType.FULL:
            base_docs.extend([
                "Planning Statement",
                "CIL Form"
            ])

        if site.tree_preservation_order:
            base_docs.append("Arboricultural Impact Assessment")

        return base_docs

    def calculate_fee(
        self,
        application_type: ApplicationType,
        floor_area_sqm: float = None
    ) -> int:
        """Calculate application fee"""
        base_fee = self.fees.get(application_type, 0)

        # Additional fees for larger applications
        if application_type == ApplicationType.FULL and floor_area_sqm:
            if floor_area_sqm > 40:
                # Additional fee per 75sqm over 40sqm
                additional_units = (floor_area_sqm - 40) / 75
                base_fee += int(additional_units * 528)

        return base_fee
