"""
Export API endpoints for generating reports
"""

import io
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import structlog

from app.db.supabase_client import SupabaseDB, get_supabase_client
from app.models.planning import ExportRequest, ExportFormat

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_db() -> SupabaseDB:
    return SupabaseDB(get_supabase_client())


@router.post("/export/pdf")
async def export_analysis_pdf(
    request: ExportRequest,
    db: SupabaseDB = Depends(get_db),
):
    """
    Export analysis results as a professional PDF report.

    The report includes:
    - Executive summary
    - Detailed analysis arguments
    - Risk assessment
    - Precedent case summaries
    - Policy references

    Suitable for:
    - Planning application supporting documents
    - Pre-application meeting materials
    - Appeal statements
    """
    try:
        # Generate PDF using WeasyPrint
        pdf_content = await _generate_pdf_report(request, db)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"planning_analysis_{timestamp}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            }
        )

    except Exception as e:
        logger.error("pdf_export_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/export/precedents")
async def export_precedents(
    case_references: list[str],
    format: ExportFormat = ExportFormat.PDF,
    db: SupabaseDB = Depends(get_db),
):
    """
    Export a list of precedent cases.

    Generates a document listing selected precedents with:
    - Case details and outcomes
    - Key decision factors
    - Relevant policy references

    Useful for compiling precedent evidence for applications or appeals.
    """
    if len(case_references) > 20:
        raise HTTPException(
            status_code=400,
            detail="Maximum 20 cases per export"
        )

    # Fetch all cases
    cases = []
    for ref in case_references:
        decision = await db.get_decision_by_reference(ref)
        if decision:
            cases.append(decision)

    if not cases:
        raise HTTPException(status_code=404, detail="No valid cases found")

    if format == ExportFormat.PDF:
        content = await _generate_precedent_pdf(cases)
        media_type = "application/pdf"
        ext = "pdf"
    elif format == ExportFormat.HTML:
        content = _generate_precedent_html(cases)
        media_type = "text/html"
        ext = "html"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

    timestamp = datetime.utcnow().strftime("%Y%m%d")
    filename = f"precedent_cases_{timestamp}.{ext}"

    return StreamingResponse(
        io.BytesIO(content if isinstance(content, bytes) else content.encode()),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export/appeal-statement")
async def export_appeal_statement(
    case_reference: str,
    refusal_reasons: str,
    precedent_references: list[str],
    appellant_name: Optional[str] = None,
    site_address: Optional[str] = None,
    db: SupabaseDB = Depends(get_db),
):
    """
    Generate a draft planning appeal statement.

    Creates a professionally formatted appeal document that:
    - Summarises the refused application
    - Addresses each refusal reason
    - Cites relevant precedents
    - Argues for inconsistent decision-making

    Note: This is a draft document and should be reviewed
    by a qualified planning professional before submission.
    """
    # Get the refused case
    refused_case = await db.get_decision_by_reference(case_reference)
    if not refused_case:
        raise HTTPException(status_code=404, detail="Refused case not found")

    # Get precedent cases
    precedents = []
    for ref in precedent_references:
        case = await db.get_decision_by_reference(ref)
        if case:
            precedents.append(case)

    if not precedents:
        raise HTTPException(status_code=404, detail="No valid precedent cases found")

    # Generate appeal statement
    statement = await _generate_appeal_statement(
        refused_case=refused_case,
        refusal_reasons=refusal_reasons,
        precedents=precedents,
        appellant_name=appellant_name,
        site_address=site_address or refused_case.address,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d")
    filename = f"appeal_statement_{case_reference.replace('/', '_')}_{timestamp}.pdf"

    return StreamingResponse(
        io.BytesIO(statement),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


async def _generate_pdf_report(request: ExportRequest, db: SupabaseDB) -> bytes:
    """Generate PDF report from analysis"""
    from weasyprint import HTML
    from jinja2 import Template

    # HTML template for the report
    template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
        }
        .header {
            border-bottom: 3px solid #1a365d;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #1a365d;
            margin: 0;
            font-size: 28px;
        }
        .header .subtitle {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        h2 {
            color: #1a365d;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        h3 {
            color: #2d3748;
            margin-top: 20px;
        }
        .summary-box {
            background: #f7fafc;
            border-left: 4px solid #3182ce;
            padding: 15px 20px;
            margin: 20px 0;
        }
        .risk-high { border-left-color: #e53e3e; }
        .risk-medium { border-left-color: #dd6b20; }
        .risk-low { border-left-color: #38a169; }
        .precedent-card {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }
        .precedent-ref {
            font-weight: bold;
            color: #3182ce;
        }
        .policy-ref {
            background: #edf2f7;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }
        .quote {
            font-style: italic;
            color: #4a5568;
            border-left: 2px solid #cbd5e0;
            padding-left: 15px;
            margin: 10px 0;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            font-size: 12px;
            color: #718096;
        }
        .disclaimer {
            background: #fff5f5;
            border: 1px solid #feb2b2;
            padding: 10px;
            font-size: 11px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Planning Precedent Analysis Report</h1>
        <div class="subtitle">
            Generated: {{ generated_date }}<br>
            {% if site_address %}Site: {{ site_address }}{% endif %}
        </div>
    </div>

    <h2>Executive Summary</h2>
    <div class="summary-box">
        {{ summary | default('Analysis summary not available') }}
    </div>

    <h2>Recommendation</h2>
    <p>{{ recommendation | default('') }}</p>

    <h2>Risk Assessment</h2>
    <div class="summary-box risk-{{ risk_level | lower }}">
        <strong>Approval Likelihood:</strong> {{ risk_level }}<br>
        <strong>Confidence:</strong> {{ confidence }}%
    </div>

    {% if key_risks %}
    <h3>Key Risks</h3>
    <ul>
    {% for risk in key_risks %}
        <li>{{ risk }}</li>
    {% endfor %}
    </ul>
    {% endif %}

    <h2>Supporting Precedents</h2>
    {% for precedent in precedents %}
    <div class="precedent-card">
        <span class="precedent-ref">{{ precedent.reference }}</span><br>
        <strong>{{ precedent.address }}</strong><br>
        Decision: {{ precedent.outcome }} ({{ precedent.date }})<br>
        Similarity: {{ precedent.similarity }}%
    </div>
    {% endfor %}

    <h2>Policy References</h2>
    <p>
    {% for policy in policies %}
        <span class="policy-ref">{{ policy }}</span>
    {% endfor %}
    </p>

    <div class="footer">
        <p>This report was generated by Planning Precedent AI.</p>
        <div class="disclaimer">
            <strong>Disclaimer:</strong> This analysis is provided for informational purposes only
            and does not constitute professional planning advice. Planning decisions depend on
            many factors including site-specific considerations, policy changes, and officer
            discretion. We recommend consulting with a qualified planning professional before
            submitting any application.
        </div>
    </div>
</body>
</html>
    """)

    # Prepare data (in production, this would come from stored analysis)
    html_content = template.render(
        generated_date=datetime.utcnow().strftime("%d %B %Y"),
        site_address=request.site_address,
        summary="Analysis based on planning precedent database.",
        recommendation="Please run a full analysis to generate recommendations.",
        risk_level="Medium",
        confidence=65,
        key_risks=["Design sensitivity in conservation area"],
        precedents=[],
        policies=["Camden Policy D1", "NPPF paragraph 130"],
    )

    # Generate PDF
    pdf = HTML(string=html_content).write_pdf()
    return pdf


async def _generate_precedent_pdf(cases: list) -> bytes:
    """Generate PDF listing precedent cases"""
    from weasyprint import HTML
    from jinja2 import Template

    template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; padding: 40px; }
        h1 { color: #1a365d; }
        .case { border: 1px solid #ddd; padding: 15px; margin: 15px 0; }
        .case-ref { font-weight: bold; color: #3182ce; font-size: 18px; }
        .granted { color: #38a169; }
        .refused { color: #e53e3e; }
    </style>
</head>
<body>
    <h1>Planning Precedent Cases</h1>
    <p>Generated: {{ date }}</p>
    {% for case in cases %}
    <div class="case">
        <div class="case-ref">{{ case.case_reference }}</div>
        <p><strong>Address:</strong> {{ case.address }}</p>
        <p><strong>Decision:</strong> <span class="{{ case.outcome.value | lower }}">{{ case.outcome.value }}</span></p>
        <p><strong>Date:</strong> {{ case.decision_date }}</p>
        <p><strong>Description:</strong> {{ case.description[:300] }}...</p>
    </div>
    {% endfor %}
</body>
</html>
    """)

    html_content = template.render(
        date=datetime.utcnow().strftime("%d %B %Y"),
        cases=cases,
    )

    return HTML(string=html_content).write_pdf()


def _generate_precedent_html(cases: list) -> str:
    """Generate HTML listing precedent cases"""
    html = ["<html><body><h1>Planning Precedent Cases</h1>"]

    for case in cases:
        html.append(f"""
        <div style="border: 1px solid #ddd; padding: 15px; margin: 15px 0;">
            <h3>{case.case_reference}</h3>
            <p><strong>Address:</strong> {case.address}</p>
            <p><strong>Decision:</strong> {case.outcome.value}</p>
            <p><strong>Date:</strong> {case.decision_date}</p>
            <p><strong>Description:</strong> {case.description}</p>
        </div>
        """)

    html.append("</body></html>")
    return "".join(html)


async def _generate_appeal_statement(
    refused_case,
    refusal_reasons: str,
    precedents: list,
    appellant_name: Optional[str],
    site_address: str,
) -> bytes:
    """Generate appeal statement PDF"""
    from weasyprint import HTML
    from jinja2 import Template

    template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: 'Times New Roman', serif;
            line-height: 1.8;
            padding: 50px;
            font-size: 12pt;
        }
        h1 { text-align: center; font-size: 16pt; }
        h2 { font-size: 14pt; margin-top: 30px; }
        .header { text-align: center; margin-bottom: 40px; }
        .section { margin: 20px 0; }
        .precedent { margin: 15px 0; padding: 10px; background: #f5f5f5; }
    </style>
</head>
<body>
    <div class="header">
        <h1>PLANNING APPEAL STATEMENT</h1>
        <p>
            Appeal against refusal of planning permission<br>
            Application Reference: {{ case_ref }}<br>
            Site Address: {{ site_address }}
        </p>
    </div>

    <h2>1. Introduction</h2>
    <p>
        This appeal is submitted against the decision of London Borough of Camden
        to refuse planning permission for the above development.
        {% if appellant %}The appellant is {{ appellant }}.{% endif %}
    </p>

    <h2>2. The Proposal</h2>
    <p>{{ description }}</p>

    <h2>3. Reasons for Refusal</h2>
    <p>The Local Planning Authority refused the application for the following reasons:</p>
    <p>{{ refusal_reasons }}</p>

    <h2>4. Grounds of Appeal</h2>
    <p>
        The appellant contends that the Local Planning Authority's decision was
        unreasonable and inconsistent with their approach to similar developments
        in the area. The following precedents demonstrate that comparable proposals
        have been approved:
    </p>

    {% for p in precedents %}
    <div class="precedent">
        <strong>{{ p.case_reference }}</strong><br>
        Address: {{ p.address }}<br>
        Decision: Granted ({{ p.decision_date }})<br>
        Description: {{ p.description[:200] }}...
    </div>
    {% endfor %}

    <h2>5. Conclusion</h2>
    <p>
        Given the precedents cited above, the Local Planning Authority cannot
        reasonably maintain that the proposed development is unacceptable.
        The appeal should be allowed.
    </p>

    <div style="margin-top: 50px; font-size: 10pt; color: #666;">
        <p><em>
            DRAFT DOCUMENT - This statement has been generated by Planning Precedent AI
            and should be reviewed by a qualified planning professional before submission.
        </em></p>
    </div>
</body>
</html>
    """)

    html_content = template.render(
        case_ref=refused_case.case_reference,
        site_address=site_address,
        appellant=appellant_name,
        description=refused_case.description,
        refusal_reasons=refusal_reasons,
        precedents=precedents,
    )

    return HTML(string=html_content).write_pdf()
