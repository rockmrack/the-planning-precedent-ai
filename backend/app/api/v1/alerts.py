"""
Alerts and Monitoring API Routes
Manage planning application alerts and monitoring
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.models.user import User
from app.api.v1.auth import require_auth, require_professional
from app.services.monitoring import AlertService, AlertMatcher, MonitoringScheduler
from app.services.monitoring.alert_service import AlertType, AlertPriority

router = APIRouter(prefix="/alerts", tags=["Alerts"])

# Initialize services
alert_service = AlertService()


# Request/Response Models
class AlertCreateRequest(BaseModel):
    """Create a new alert"""
    name: str = Field(..., min_length=1, max_length=255)
    alert_type: AlertType
    value: str = Field(..., min_length=1)
    priority: AlertPriority = AlertPriority.MEDIUM
    notify_email: bool = True
    notify_push: bool = False
    radius_meters: Optional[int] = Field(None, ge=100, le=10000)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Street Alert",
                "alert_type": "address",
                "value": "123 Haverstock Hill, London",
                "priority": "high",
                "notify_email": True
            }
        }


class AlertUpdateRequest(BaseModel):
    """Update an existing alert"""
    name: Optional[str] = None
    value: Optional[str] = None
    priority: Optional[AlertPriority] = None
    notify_email: Optional[bool] = None
    notify_push: Optional[bool] = None
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    """Alert response"""
    id: str
    name: str
    alert_type: str
    value: str
    priority: str
    is_active: bool
    notify_email: bool
    notify_push: bool
    trigger_count: int
    created_at: datetime
    last_triggered: Optional[datetime]


class AlertTriggerResponse(BaseModel):
    """Alert trigger response"""
    id: str
    alert_id: str
    case_reference: str
    match_reason: str
    match_score: float
    triggered_at: datetime
    case_data: dict


class MonitoringStatsResponse(BaseModel):
    """Monitoring service statistics"""
    total_jobs: int
    active_jobs: int
    total_applications_processed: int
    total_alerts_triggered: int
    last_run: Optional[datetime]
    uptime_seconds: int


class JobStatusResponse(BaseModel):
    """Job status response"""
    id: str
    name: str
    frequency: str
    source: str
    is_active: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    run_count: int
    error_count: int


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


# Alert endpoints
@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    request: AlertCreateRequest,
    user: User = Depends(require_auth)
):
    """
    Create a new monitoring alert.

    Alert types:
    - **address**: Monitor a specific address
    - **postcode**: Monitor a postcode area
    - **ward**: Monitor an entire ward
    - **keyword**: Monitor for keywords in descriptions
    - **policy**: Monitor for specific policy references
    - **development_type**: Monitor for types of development
    - **applicant**: Monitor for specific applicants
    - **agent**: Monitor for specific agents/architects
    """
    alert = await alert_service.create_alert(
        user_id=user.id,
        name=request.name,
        alert_type=request.alert_type,
        value=request.value,
        priority=request.priority,
        notify_email=request.notify_email,
        notify_push=request.notify_push,
        radius_meters=request.radius_meters
    )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    active_only: bool = Query(True, description="Only return active alerts"),
    user: User = Depends(require_auth)
):
    """
    Get all alerts for the current user.
    """
    alerts = await alert_service.get_user_alerts(user.id, active_only=active_only)

    return [
        AlertResponse(
            id=alert.id,
            name=alert.name,
            alert_type=alert.alert_type.value,
            value=alert.value,
            priority=alert.priority.value,
            is_active=alert.is_active,
            notify_email=alert.notify_email,
            notify_push=alert.notify_push,
            trigger_count=alert.trigger_count,
            created_at=alert.created_at,
            last_triggered=alert.last_triggered
        )
        for alert in alerts
    ]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    user: User = Depends(require_auth)
):
    """
    Get a specific alert by ID.
    """
    alert = await alert_service.get_alert(alert_id, user.id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    request: AlertUpdateRequest,
    user: User = Depends(require_auth)
):
    """
    Update an existing alert.
    """
    updates = request.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided"
        )

    alert = await alert_service.update_alert(alert_id, user.id, updates)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


@router.delete("/{alert_id}", response_model=MessageResponse)
async def delete_alert(
    alert_id: str,
    user: User = Depends(require_auth)
):
    """
    Delete an alert.
    """
    success = await alert_service.delete_alert(alert_id, user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return MessageResponse(message="Alert deleted successfully")


@router.post("/{alert_id}/pause", response_model=AlertResponse)
async def pause_alert(
    alert_id: str,
    user: User = Depends(require_auth)
):
    """
    Pause an active alert.
    """
    alert = await alert_service.update_alert(
        alert_id, user.id, {"is_active": False}
    )

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


@router.post("/{alert_id}/resume", response_model=AlertResponse)
async def resume_alert(
    alert_id: str,
    user: User = Depends(require_auth)
):
    """
    Resume a paused alert.
    """
    alert = await alert_service.update_alert(
        alert_id, user.id, {"is_active": True}
    )

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


# Trigger endpoints
@router.get("/{alert_id}/triggers", response_model=List[AlertTriggerResponse])
async def get_alert_triggers(
    alert_id: str,
    since: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_auth)
):
    """
    Get triggers for a specific alert.
    """
    triggers = await alert_service.get_alert_triggers(
        user_id=user.id,
        alert_id=alert_id,
        since=since,
        limit=limit
    )

    return [
        AlertTriggerResponse(
            id=t.id,
            alert_id=t.alert_id,
            case_reference=t.case_reference,
            match_reason=t.match_reason,
            match_score=t.match_score,
            triggered_at=t.triggered_at,
            case_data=t.case_data
        )
        for t in triggers
    ]


@router.get("/triggers/all", response_model=List[AlertTriggerResponse])
async def get_all_triggers(
    since: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_auth)
):
    """
    Get all triggers across all user's alerts.
    """
    triggers = await alert_service.get_alert_triggers(
        user_id=user.id,
        since=since,
        limit=limit
    )

    return [
        AlertTriggerResponse(
            id=t.id,
            alert_id=t.alert_id,
            case_reference=t.case_reference,
            match_reason=t.match_reason,
            match_score=t.match_score,
            triggered_at=t.triggered_at,
            case_data=t.case_data
        )
        for t in triggers
    ]


# Monitoring status (admin/professional only)
@router.get("/monitoring/stats", response_model=MonitoringStatsResponse)
async def get_monitoring_stats(
    user: User = Depends(require_professional)
):
    """
    Get monitoring service statistics.
    Requires Professional subscription or higher.
    """
    # Would get from actual scheduler instance
    return MonitoringStatsResponse(
        total_jobs=2,
        active_jobs=2,
        total_applications_processed=0,
        total_alerts_triggered=0,
        last_run=None,
        uptime_seconds=0
    )


@router.get("/monitoring/jobs", response_model=List[JobStatusResponse])
async def get_monitoring_jobs(
    user: User = Depends(require_professional)
):
    """
    Get status of all monitoring jobs.
    Requires Professional subscription or higher.
    """
    # Would get from actual scheduler instance
    return []


# Quick setup endpoints
@router.post("/quick/address", response_model=AlertResponse)
async def quick_address_alert(
    address: str = Query(..., min_length=5),
    radius: int = Query(100, ge=100, le=5000),
    user: User = Depends(require_auth)
):
    """
    Quickly set up an address monitoring alert.
    """
    alert = await alert_service.create_alert(
        user_id=user.id,
        name=f"Alert for {address[:50]}",
        alert_type=AlertType.ADDRESS,
        value=address,
        priority=AlertPriority.HIGH,
        radius_meters=radius
    )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


@router.post("/quick/postcode", response_model=AlertResponse)
async def quick_postcode_alert(
    postcode: str = Query(..., min_length=3, max_length=10),
    user: User = Depends(require_auth)
):
    """
    Quickly set up a postcode area monitoring alert.
    """
    alert = await alert_service.create_alert(
        user_id=user.id,
        name=f"Postcode alert: {postcode.upper()}",
        alert_type=AlertType.POSTCODE,
        value=postcode.upper(),
        priority=AlertPriority.MEDIUM
    )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )


@router.post("/quick/ward", response_model=AlertResponse)
async def quick_ward_alert(
    ward: str = Query(..., min_length=2),
    user: User = Depends(require_auth)
):
    """
    Quickly set up a ward monitoring alert.
    """
    alert = await alert_service.create_alert(
        user_id=user.id,
        name=f"Ward alert: {ward}",
        alert_type=AlertType.WARD,
        value=ward,
        priority=AlertPriority.MEDIUM
    )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        alert_type=alert.alert_type.value,
        value=alert.value,
        priority=alert.priority.value,
        is_active=alert.is_active,
        notify_email=alert.notify_email,
        notify_push=alert.notify_push,
        trigger_count=alert.trigger_count,
        created_at=alert.created_at,
        last_triggered=alert.last_triggered
    )
