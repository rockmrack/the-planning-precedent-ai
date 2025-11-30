"""
Alert Service
Manages user alerts and monitors for new planning applications
"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types of monitoring alerts"""
    ADDRESS = "address"  # Specific address monitoring
    POSTCODE = "postcode"  # Postcode area monitoring
    WARD = "ward"  # Ward-level monitoring
    KEYWORD = "keyword"  # Keyword in description
    POLICY = "policy"  # Specific policy references
    DEVELOPMENT_TYPE = "development_type"  # Type of development
    APPLICANT = "applicant"  # Applicant name
    AGENT = "agent"  # Agent/architect name


class AlertPriority(str, Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Alert:
    """A monitoring alert configuration"""
    id: str
    user_id: str
    name: str
    alert_type: AlertType
    value: str  # The value to match (address, keyword, etc.)
    is_active: bool = True
    priority: AlertPriority = AlertPriority.MEDIUM
    notify_email: bool = True
    notify_push: bool = False
    radius_meters: Optional[int] = None  # For address alerts
    include_similar: bool = False  # Include similar matches
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class AlertTrigger:
    """When an alert is triggered"""
    id: str
    alert_id: str
    case_reference: str
    match_reason: str
    match_score: float  # 0-1 confidence of match
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    case_data: dict = field(default_factory=dict)
    was_notified: bool = False


@dataclass
class PlanningApplication:
    """Represents a new planning application"""
    reference: str
    address: str
    postcode: str
    ward: str
    description: str
    applicant: Optional[str] = None
    agent: Optional[str] = None
    development_type: Optional[str] = None
    policies: List[str] = field(default_factory=list)
    received_date: Optional[datetime] = None
    decision_date: Optional[datetime] = None
    outcome: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AlertMatcher:
    """Matches planning applications against user alerts"""

    def __init__(self):
        # Postcode regex for UK postcodes
        self.postcode_pattern = re.compile(
            r'^([A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})$',
            re.IGNORECASE
        )

    def match_alert(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """
        Check if an application matches an alert
        Returns (match_score, reason) or None
        """
        if not alert.is_active:
            return None

        match_type = alert.alert_type

        if match_type == AlertType.ADDRESS:
            return self._match_address(alert, application)
        elif match_type == AlertType.POSTCODE:
            return self._match_postcode(alert, application)
        elif match_type == AlertType.WARD:
            return self._match_ward(alert, application)
        elif match_type == AlertType.KEYWORD:
            return self._match_keyword(alert, application)
        elif match_type == AlertType.POLICY:
            return self._match_policy(alert, application)
        elif match_type == AlertType.DEVELOPMENT_TYPE:
            return self._match_development_type(alert, application)
        elif match_type == AlertType.APPLICANT:
            return self._match_applicant(alert, application)
        elif match_type == AlertType.AGENT:
            return self._match_agent(alert, application)

        return None

    def _match_address(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by address"""
        alert_address = alert.value.lower().strip()
        app_address = application.address.lower().strip()

        # Exact match
        if alert_address == app_address:
            return (1.0, f"Exact address match: {application.address}")

        # Partial match - check if alert address is in application address
        if alert_address in app_address:
            return (0.9, f"Address contains: {alert.value}")

        # Check key components
        alert_parts = set(alert_address.split())
        app_parts = set(app_address.split())
        common = alert_parts & app_parts

        if len(common) >= 3:  # At least 3 common words
            score = len(common) / max(len(alert_parts), len(app_parts))
            if score > 0.5:
                return (score, f"Similar address: {application.address}")

        return None

    def _match_postcode(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by postcode"""
        alert_postcode = alert.value.upper().replace(" ", "")
        app_postcode = application.postcode.upper().replace(" ", "")

        # Exact match
        if alert_postcode == app_postcode:
            return (1.0, f"Postcode match: {application.postcode}")

        # Outcode match (first part of postcode)
        alert_outcode = alert_postcode[:3] if len(alert_postcode) >= 3 else alert_postcode
        app_outcode = app_postcode[:3] if len(app_postcode) >= 3 else app_postcode

        if alert_outcode == app_outcode:
            return (0.8, f"Postcode area match: {app_outcode}")

        return None

    def _match_ward(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by ward"""
        alert_ward = alert.value.lower().strip()
        app_ward = application.ward.lower().strip()

        if alert_ward == app_ward:
            return (1.0, f"Ward match: {application.ward}")

        if alert_ward in app_ward or app_ward in alert_ward:
            return (0.8, f"Ward partial match: {application.ward}")

        return None

    def _match_keyword(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by keyword in description"""
        keywords = [k.strip().lower() for k in alert.value.split(",")]
        description = application.description.lower()

        matches = []
        for keyword in keywords:
            if keyword in description:
                matches.append(keyword)

        if matches:
            score = len(matches) / len(keywords)
            return (score, f"Keyword matches: {', '.join(matches)}")

        return None

    def _match_policy(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by policy reference"""
        alert_policies = [p.strip().upper() for p in alert.value.split(",")]
        app_policies = [p.upper() for p in application.policies]

        matches = set(alert_policies) & set(app_policies)

        if matches:
            score = len(matches) / len(alert_policies)
            return (score, f"Policy matches: {', '.join(matches)}")

        return None

    def _match_development_type(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by development type"""
        if not application.development_type:
            return None

        alert_type = alert.value.lower().strip()
        app_type = application.development_type.lower().strip()

        if alert_type == app_type:
            return (1.0, f"Development type match: {application.development_type}")

        if alert_type in app_type:
            return (0.8, f"Development type contains: {alert.value}")

        return None

    def _match_applicant(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by applicant name"""
        if not application.applicant:
            return None

        alert_name = alert.value.lower().strip()
        app_name = application.applicant.lower().strip()

        if alert_name == app_name:
            return (1.0, f"Applicant match: {application.applicant}")

        if alert_name in app_name or app_name in alert_name:
            return (0.8, f"Applicant similar: {application.applicant}")

        return None

    def _match_agent(
        self,
        alert: Alert,
        application: PlanningApplication
    ) -> Optional[Tuple[float, str]]:
        """Match by agent/architect name"""
        if not application.agent:
            return None

        alert_name = alert.value.lower().strip()
        app_name = application.agent.lower().strip()

        if alert_name == app_name:
            return (1.0, f"Agent match: {application.agent}")

        if alert_name in app_name or app_name in alert_name:
            return (0.8, f"Agent similar: {application.agent}")

        return None


class AlertService:
    """Manages user alerts"""

    def __init__(self, supabase_client=None, ws_manager=None):
        self.supabase = supabase_client
        self.ws_manager = ws_manager
        self.matcher = AlertMatcher()

        # In-memory cache of active alerts by user
        self._user_alerts: Dict[str, List[Alert]] = {}
        self._all_alerts: List[Alert] = []

    async def create_alert(
        self,
        user_id: str,
        name: str,
        alert_type: AlertType,
        value: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        notify_email: bool = True,
        notify_push: bool = False,
        radius_meters: Optional[int] = None,
        metadata: dict = None
    ) -> Alert:
        """Create a new alert"""
        alert = Alert(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            alert_type=alert_type,
            value=value,
            priority=priority,
            notify_email=notify_email,
            notify_push=notify_push,
            radius_meters=radius_meters,
            metadata=metadata or {}
        )

        # Save to database
        if self.supabase:
            self.supabase.table("monitoring_alerts").insert({
                "id": alert.id,
                "user_id": alert.user_id,
                "name": alert.name,
                "alert_type": alert.alert_type.value,
                "value": alert.value,
                "is_active": alert.is_active,
                "priority": alert.priority.value,
                "notify_email": alert.notify_email,
                "notify_push": alert.notify_push,
                "radius_meters": alert.radius_meters,
                "metadata": alert.metadata,
                "created_at": alert.created_at.isoformat()
            }).execute()

        # Add to cache
        if user_id not in self._user_alerts:
            self._user_alerts[user_id] = []
        self._user_alerts[user_id].append(alert)
        self._all_alerts.append(alert)

        logger.info(f"Created alert {alert.id} for user {user_id}")
        return alert

    async def update_alert(
        self,
        alert_id: str,
        user_id: str,
        updates: dict
    ) -> Optional[Alert]:
        """Update an existing alert"""
        # Find the alert
        alert = await self.get_alert(alert_id, user_id)
        if not alert:
            return None

        # Apply updates
        for key, value in updates.items():
            if hasattr(alert, key):
                setattr(alert, key, value)

        # Save to database
        if self.supabase:
            self.supabase.table("monitoring_alerts").update(updates).eq(
                "id", alert_id
            ).eq("user_id", user_id).execute()

        logger.info(f"Updated alert {alert_id}")
        return alert

    async def delete_alert(self, alert_id: str, user_id: str) -> bool:
        """Delete an alert"""
        if self.supabase:
            self.supabase.table("monitoring_alerts").delete().eq(
                "id", alert_id
            ).eq("user_id", user_id).execute()

        # Remove from cache
        if user_id in self._user_alerts:
            self._user_alerts[user_id] = [
                a for a in self._user_alerts[user_id] if a.id != alert_id
            ]
        self._all_alerts = [a for a in self._all_alerts if a.id != alert_id]

        logger.info(f"Deleted alert {alert_id}")
        return True

    async def get_alert(self, alert_id: str, user_id: str) -> Optional[Alert]:
        """Get a specific alert"""
        # Check cache first
        if user_id in self._user_alerts:
            for alert in self._user_alerts[user_id]:
                if alert.id == alert_id:
                    return alert

        # Try database
        if self.supabase:
            result = self.supabase.table("monitoring_alerts").select("*").eq(
                "id", alert_id
            ).eq("user_id", user_id).execute()

            if result.data:
                return self._dict_to_alert(result.data[0])

        return None

    async def get_user_alerts(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Alert]:
        """Get all alerts for a user"""
        if self.supabase:
            query = self.supabase.table("monitoring_alerts").select("*").eq(
                "user_id", user_id
            )
            if active_only:
                query = query.eq("is_active", True)

            result = query.execute()

            if result.data:
                return [self._dict_to_alert(d) for d in result.data]

        # Fallback to cache
        alerts = self._user_alerts.get(user_id, [])
        if active_only:
            alerts = [a for a in alerts if a.is_active]
        return alerts

    async def process_new_applications(
        self,
        applications: List[PlanningApplication]
    ) -> List[AlertTrigger]:
        """Process new applications and trigger matching alerts"""
        triggers = []

        for app in applications:
            for alert in self._all_alerts:
                if not alert.is_active:
                    continue

                match_result = self.matcher.match_alert(alert, app)

                if match_result:
                    score, reason = match_result

                    trigger = AlertTrigger(
                        id=str(uuid4()),
                        alert_id=alert.id,
                        case_reference=app.reference,
                        match_reason=reason,
                        match_score=score,
                        case_data={
                            "address": app.address,
                            "postcode": app.postcode,
                            "ward": app.ward,
                            "description": app.description[:500],
                            "development_type": app.development_type
                        }
                    )

                    triggers.append(trigger)

                    # Update alert
                    alert.last_triggered = datetime.utcnow()
                    alert.trigger_count += 1

                    # Save trigger
                    await self._save_trigger(trigger)

                    # Send notifications
                    await self._notify_user(alert, trigger)

        logger.info(f"Processed {len(applications)} applications, {len(triggers)} triggers")
        return triggers

    async def get_alert_triggers(
        self,
        user_id: str,
        alert_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[AlertTrigger]:
        """Get alert triggers for a user"""
        if not self.supabase:
            return []

        # Get user's alert IDs
        alerts = await self.get_user_alerts(user_id, active_only=False)
        alert_ids = [a.id for a in alerts]

        if alert_id:
            if alert_id not in alert_ids:
                return []
            alert_ids = [alert_id]

        # Query triggers
        query = self.supabase.table("alert_triggers").select("*").in_(
            "alert_id", alert_ids
        ).order("triggered_at", desc=True).limit(limit)

        if since:
            query = query.gte("triggered_at", since.isoformat())

        result = query.execute()

        if result.data:
            return [self._dict_to_trigger(d) for d in result.data]

        return []

    async def _save_trigger(self, trigger: AlertTrigger) -> None:
        """Save an alert trigger to database"""
        if self.supabase:
            self.supabase.table("alert_triggers").insert({
                "id": trigger.id,
                "alert_id": trigger.alert_id,
                "case_reference": trigger.case_reference,
                "match_reason": trigger.match_reason,
                "match_score": trigger.match_score,
                "case_data": trigger.case_data,
                "triggered_at": trigger.triggered_at.isoformat()
            }).execute()

            # Update alert last_triggered
            self.supabase.table("monitoring_alerts").update({
                "last_triggered": trigger.triggered_at.isoformat(),
                "trigger_count": self.supabase.rpc(
                    "increment_trigger_count",
                    {"alert_id_input": trigger.alert_id}
                )
            }).eq("id", trigger.alert_id).execute()

    async def _notify_user(self, alert: Alert, trigger: AlertTrigger) -> None:
        """Send notification for alert trigger"""
        # WebSocket notification
        if self.ws_manager:
            await self.ws_manager.send_alert(
                user_id=alert.user_id,
                alert_id=alert.id,
                case_reference=trigger.case_reference,
                match_reason=trigger.match_reason
            )

        # Email notification (would be implemented separately)
        if alert.notify_email:
            logger.info(
                f"Would send email to user {alert.user_id} for "
                f"alert {alert.name}: {trigger.case_reference}"
            )

        # Push notification
        if alert.notify_push:
            logger.info(
                f"Would send push to user {alert.user_id} for "
                f"alert {alert.name}: {trigger.case_reference}"
            )

    def _dict_to_alert(self, data: dict) -> Alert:
        """Convert database dict to Alert object"""
        return Alert(
            id=data["id"],
            user_id=data["user_id"],
            name=data["name"],
            alert_type=AlertType(data["alert_type"]),
            value=data["value"],
            is_active=data.get("is_active", True),
            priority=AlertPriority(data.get("priority", "medium")),
            notify_email=data.get("notify_email", True),
            notify_push=data.get("notify_push", False),
            radius_meters=data.get("radius_meters"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            last_triggered=datetime.fromisoformat(data["last_triggered"]) if data.get("last_triggered") else None,
            trigger_count=data.get("trigger_count", 0),
            metadata=data.get("metadata", {})
        )

    def _dict_to_trigger(self, data: dict) -> AlertTrigger:
        """Convert database dict to AlertTrigger object"""
        return AlertTrigger(
            id=data["id"],
            alert_id=data["alert_id"],
            case_reference=data["case_reference"],
            match_reason=data["match_reason"],
            match_score=data.get("match_score", 1.0),
            triggered_at=datetime.fromisoformat(data["triggered_at"]) if data.get("triggered_at") else datetime.utcnow(),
            case_data=data.get("case_data", {}),
            was_notified=data.get("was_notified", False)
        )
