"""
Application Generator API Routes
Generate planning application documents
"""

from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr

from app.models.user import User
from app.api.v1.auth import require_auth
from app.services.generator import (
    ApplicationGenerator, ApplicationData,
    DesignStatementGenerator, DocumentTemplates
)
from app.services.generator.application_generator import (
    ApplicationType, DocumentType, Applicant,
    SiteDetails, ProposalDetails
)
from app.services.generator.document_templates import TemplateCategory

router = APIRouter(prefix="/generator", tags=["Generator"])

# Initialize services
generator = ApplicationGenerator()
statement_gen = DesignStatementGenerator()
templates = DocumentTemplates()


# Request/Response Models
class ApplicantRequest(BaseModel):
    """Applicant details"""
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None


class SiteRequest(BaseModel):
    """Site details"""
    address: str = Field(..., min_length=5)
    postcode: str = Field(..., min_length=5)
    ward: Optional[str] = None
    conservation_area: Optional[str] = None
    listed_building: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ProposalRequest(BaseModel):
    """Proposal details"""
    description: str = Field(..., min_length=20)
    development_type: str
    existing_floor_area_sqm: Optional[float] = None
    proposed_floor_area_sqm: Optional[float] = None
    height_meters: Optional[float] = None
    depth_meters: Optional[float] = None
    width_meters: Optional[float] = None
    materials: List[str] = []
    design_features: List[str] = []


class GenerateRequest(BaseModel):
    """Full application generation request"""
    application_type: ApplicationType
    applicant: ApplicantRequest
    site: SiteRequest
    proposal: ProposalRequest
    agent: Optional[ApplicantRequest] = None
    precedent_cases: List[Dict] = []
    policy_references: List[str] = []

    class Config:
        json_schema_extra = {
            "example": {
                "application_type": "householder",
                "applicant": {
                    "name": "John Smith",
                    "email": "john@example.com"
                },
                "site": {
                    "address": "123 Haverstock Hill, London",
                    "postcode": "NW3 4QG",
                    "ward": "Belsize",
                    "conservation_area": "Belsize Conservation Area"
                },
                "proposal": {
                    "description": "Single storey rear extension to provide additional living space",
                    "development_type": "Householder",
                    "depth_meters": 3.0,
                    "height_meters": 3.0,
                    "materials": ["London stock brick", "Zinc roof", "Timber windows"]
                }
            }
        }


class DocumentResponse(BaseModel):
    """Generated document response"""
    document_type: str
    title: str
    content: str
    format: str
    word_count: int


class GenerateResponse(BaseModel):
    """Generation response"""
    success: bool
    reference_id: str
    documents: List[DocumentResponse]
    fee: int
    required_documents: List[str]


class TemplateResponse(BaseModel):
    """Template info response"""
    id: str
    name: str
    category: str
    description: str
    sections: List[Dict]
    variables: List[str]


class FeeCalculationResponse(BaseModel):
    """Fee calculation response"""
    application_type: str
    base_fee: int
    additional_fee: int
    total_fee: int
    notes: str


class DesignJustificationResponse(BaseModel):
    """Design justification section"""
    principle: str
    explanation: str
    evidence: List[str]


class PolicyArgumentResponse(BaseModel):
    """Policy argument response"""
    policy_name: str
    policy_reference: str
    argument: str
    supporting_points: List[str]


# Generation endpoints
@router.post("/application", response_model=GenerateResponse)
async def generate_application(
    request: GenerateRequest,
    user: User = Depends(require_auth)
):
    """
    Generate a complete planning application package.

    Returns all required documents for submission including:
    - Covering letter
    - Design and Access Statement
    - Heritage Statement (if applicable)
    - Application form data
    """
    # Convert request to ApplicationData
    data = ApplicationData(
        application_type=request.application_type,
        applicant=Applicant(
            name=request.applicant.name,
            email=request.applicant.email,
            phone=request.applicant.phone,
            address=request.applicant.address
        ),
        site=SiteDetails(
            address=request.site.address,
            postcode=request.site.postcode,
            ward=request.site.ward,
            conservation_area=request.site.conservation_area,
            listed_building=request.site.listed_building,
            latitude=request.site.latitude,
            longitude=request.site.longitude
        ),
        proposal=ProposalDetails(
            description=request.proposal.description,
            development_type=request.proposal.development_type,
            existing_floor_area_sqm=request.proposal.existing_floor_area_sqm,
            proposed_floor_area_sqm=request.proposal.proposed_floor_area_sqm,
            height_meters=request.proposal.height_meters,
            depth_meters=request.proposal.depth_meters,
            width_meters=request.proposal.width_meters,
            materials=request.proposal.materials,
            design_features=request.proposal.design_features
        ),
        agent=Applicant(
            name=request.agent.name,
            email=request.agent.email,
            phone=request.agent.phone,
            address=request.agent.address
        ) if request.agent else None,
        precedent_cases=request.precedent_cases,
        policy_references=request.policy_references
    )

    # Generate documents
    documents = await generator.generate_application(data)

    # Get required documents list
    required_docs = generator.get_required_documents(
        request.application_type,
        data.site
    )

    # Calculate fee
    fee = generator.calculate_fee(
        request.application_type,
        request.proposal.proposed_floor_area_sqm
    )

    # Generate reference
    ref_id = f"GEN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    return GenerateResponse(
        success=True,
        reference_id=ref_id,
        documents=[
            DocumentResponse(
                document_type=doc.document_type.value,
                title=doc.title,
                content=doc.content,
                format=doc.format,
                word_count=len(doc.content.split())
            )
            for doc in documents
        ],
        fee=fee,
        required_documents=required_docs
    )


@router.post("/design-statement")
async def generate_design_statement(
    proposal: ProposalRequest,
    site: SiteRequest,
    precedents: List[Dict] = [],
    user: User = Depends(require_auth)
):
    """
    Generate design justifications for a proposal.

    Returns structured arguments covering design principles.
    """
    justifications = await statement_gen.generate_design_justification(
        proposal=proposal.model_dump(),
        site=site.model_dump(),
        precedents=precedents
    )

    return {
        "justifications": [
            DesignJustificationResponse(
                principle=j.principle,
                explanation=j.explanation,
                evidence=j.evidence
            )
            for j in justifications
        ]
    }


@router.post("/policy-arguments")
async def generate_policy_arguments(
    proposal: ProposalRequest,
    site: SiteRequest,
    policies: List[str] = ["D1", "D2", "A1"],
    user: User = Depends(require_auth)
):
    """
    Generate policy-based arguments for a proposal.
    """
    arguments = await statement_gen.generate_policy_arguments(
        proposal=proposal.model_dump(),
        site=site.model_dump(),
        policies=policies
    )

    return {
        "arguments": [
            PolicyArgumentResponse(
                policy_name=a.policy_name,
                policy_reference=a.policy_reference,
                argument=a.argument,
                supporting_points=a.supporting_points
            )
            for a in arguments
        ]
    }


@router.post("/neighbour-impact")
async def generate_neighbour_impact(
    proposal: ProposalRequest,
    user: User = Depends(require_auth)
):
    """
    Generate neighbour impact assessment.
    """
    assessments = await statement_gen.generate_neighbour_impact(
        proposal=proposal.model_dump()
    )

    return {
        "assessments": [
            {
                "impact_type": a.impact_type,
                "assessment": a.assessment,
                "mitigation": a.mitigation,
                "conclusion": a.conclusion
            }
            for a in assessments
        ]
    }


# Fee calculation
@router.post("/calculate-fee", response_model=FeeCalculationResponse)
async def calculate_fee(
    application_type: ApplicationType,
    floor_area_sqm: Optional[float] = None
):
    """
    Calculate the planning application fee.

    Based on current fee regulations (2024).
    """
    base_fee = generator.fees.get(application_type, 0)
    additional_fee = 0

    if application_type == ApplicationType.FULL and floor_area_sqm:
        if floor_area_sqm > 40:
            additional_units = (floor_area_sqm - 40) / 75
            additional_fee = int(additional_units * 528)

    notes = ""
    if application_type == ApplicationType.LISTED_BUILDING:
        notes = "No fee for listed building consent"
    elif application_type == ApplicationType.CONSERVATION_AREA:
        notes = "No fee for conservation area consent"

    return FeeCalculationResponse(
        application_type=application_type.value,
        base_fee=base_fee,
        additional_fee=additional_fee,
        total_fee=base_fee + additional_fee,
        notes=notes
    )


@router.get("/required-documents")
async def get_required_documents(
    application_type: ApplicationType,
    conservation_area: bool = False,
    listed_building: bool = False,
    tree_preservation_order: bool = False
):
    """
    Get list of required documents for an application type.
    """
    site = SiteDetails(
        address="",
        postcode="",
        conservation_area="Conservation Area" if conservation_area else None,
        listed_building="II" if listed_building else None,
        tree_preservation_order=tree_preservation_order
    )

    docs = generator.get_required_documents(application_type, site)

    return {
        "application_type": application_type.value,
        "required_documents": docs,
        "total_count": len(docs)
    }


# Template endpoints
@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[TemplateCategory] = None
):
    """
    List available document templates.
    """
    template_list = templates.list_templates(category)

    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            category=t.category.value,
            description=t.description,
            sections=t.sections,
            variables=t.variables
        )
        for t in template_list
    ]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """
    Get a specific template by ID.
    """
    template = templates.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category.value,
        description=template.description,
        sections=template.sections,
        variables=template.variables
    )


@router.get("/templates/{template_id}/prompts")
async def get_template_prompts(template_id: str):
    """
    Get writing prompts for each section of a template.
    """
    template = templates.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    prompts = templates.get_section_prompts(template_id)
    word_counts = templates.get_word_counts(template_id)

    return {
        "template_id": template_id,
        "sections": [
            {
                "id": section["id"],
                "title": section["title"],
                "required": section["required"],
                "prompt": prompts.get(section["id"], ""),
                "recommended_words": word_counts.get(section["id"], 200)
            }
            for section in template.sections
        ]
    }


@router.post("/templates/{template_id}/render")
async def render_template(
    template_id: str,
    variables: Dict[str, str],
    section_content: Dict[str, str] = {}
):
    """
    Render a template with provided content.
    """
    content = templates.render_template(
        template_id,
        variables,
        section_content
    )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    return {
        "template_id": template_id,
        "rendered_content": content,
        "word_count": len(content.split())
    }
