"""
User and Authentication Models
Multi-tenant support with team collaboration features
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, EmailStr


class UserRole(str, Enum):
    """User roles in the system"""
    ADMIN = "admin"
    PROFESSIONAL = "professional"  # Architects, planners
    HOMEOWNER = "homeowner"
    VIEWER = "viewer"


class SubscriptionTier(str, Enum):
    """Subscription tiers"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionLimits(BaseModel):
    """Limits for each subscription tier"""
    searches_per_month: int
    analyses_per_month: int
    exports_per_month: int
    saved_cases: int
    team_members: int
    api_access: bool
    priority_support: bool
    custom_branding: bool


TIER_LIMITS = {
    SubscriptionTier.FREE: SubscriptionLimits(
        searches_per_month=10,
        analyses_per_month=3,
        exports_per_month=1,
        saved_cases=10,
        team_members=1,
        api_access=False,
        priority_support=False,
        custom_branding=False
    ),
    SubscriptionTier.STARTER: SubscriptionLimits(
        searches_per_month=100,
        analyses_per_month=25,
        exports_per_month=10,
        saved_cases=100,
        team_members=1,
        api_access=False,
        priority_support=False,
        custom_branding=False
    ),
    SubscriptionTier.PROFESSIONAL: SubscriptionLimits(
        searches_per_month=500,
        analyses_per_month=100,
        exports_per_month=50,
        saved_cases=500,
        team_members=5,
        api_access=True,
        priority_support=True,
        custom_branding=False
    ),
    SubscriptionTier.ENTERPRISE: SubscriptionLimits(
        searches_per_month=999999,
        analyses_per_month=999999,
        exports_per_month=999999,
        saved_cases=999999,
        team_members=999999,
        api_access=True,
        priority_support=True,
        custom_branding=True
    ),
}


# User Models
class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: str
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    """User registration model"""
    password: str = Field(..., min_length=8)
    accepted_terms: bool = Field(..., description="Must accept terms of service")


class UserUpdate(BaseModel):
    """User update model"""
    full_name: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    notification_preferences: Optional[dict] = None


class User(UserBase):
    """Full user model"""
    id: str
    role: UserRole = UserRole.HOMEOWNER
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None
    team_id: Optional[str] = None

    # Usage tracking
    searches_this_month: int = 0
    analyses_this_month: int = 0
    exports_this_month: int = 0

    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with password hash"""
    hashed_password: str


# Team Models
class TeamBase(BaseModel):
    """Base team model"""
    name: str
    description: Optional[str] = None


class TeamCreate(TeamBase):
    """Team creation model"""
    pass


class Team(TeamBase):
    """Full team model"""
    id: str
    owner_id: str
    subscription_tier: SubscriptionTier
    created_at: datetime
    member_count: int = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class TeamMember(BaseModel):
    """Team membership"""
    user_id: str
    team_id: str
    role: str = "member"  # owner, admin, member, viewer
    joined_at: datetime
    invited_by: Optional[str] = None


class TeamInvite(BaseModel):
    """Team invitation"""
    id: str
    team_id: str
    email: EmailStr
    role: str = "member"
    invited_by: str
    created_at: datetime
    expires_at: datetime
    accepted: bool = False


# Project Models
class ProjectBase(BaseModel):
    """Base project model - for organizing cases and analyses"""
    name: str
    description: Optional[str] = None
    site_address: Optional[str] = None
    client_name: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Project creation"""
    pass


class Project(ProjectBase):
    """Full project model"""
    id: str
    user_id: str
    team_id: Optional[str] = None
    status: str = "active"  # active, archived, completed
    created_at: datetime
    updated_at: datetime

    # Associated data
    saved_case_ids: List[str] = []
    analysis_ids: List[str] = []
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# Saved Case Model
class SavedCase(BaseModel):
    """A case saved by a user"""
    id: str
    user_id: str
    project_id: Optional[str] = None
    case_reference: str
    notes: Optional[str] = None
    tags: List[str] = []
    saved_at: datetime
    is_favorite: bool = False


# Search History Model
class SearchHistory(BaseModel):
    """User's search history"""
    id: str
    user_id: str
    query: str
    filters: Optional[dict] = None
    results_count: int
    searched_at: datetime


# Analysis History Model
class AnalysisHistory(BaseModel):
    """User's analysis history"""
    id: str
    user_id: str
    project_id: Optional[str] = None
    query: str
    result_summary: str
    precedent_count: int
    confidence_score: float
    created_at: datetime
    is_exported: bool = False


# Notification Models
class NotificationType(str, Enum):
    """Types of notifications"""
    NEW_DECISION = "new_decision"
    SIMILAR_CASE = "similar_case"
    APPEAL_DEADLINE = "appeal_deadline"
    SUBSCRIPTION = "subscription"
    TEAM_INVITE = "team_invite"
    SYSTEM = "system"


class Notification(BaseModel):
    """User notification"""
    id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    data: Optional[dict] = None
    is_read: bool = False
    created_at: datetime


class NotificationPreferences(BaseModel):
    """User notification preferences"""
    email_new_decisions: bool = True
    email_similar_cases: bool = True
    email_appeal_deadlines: bool = True
    email_weekly_digest: bool = True
    push_enabled: bool = False


# Alert/Monitoring Models
class MonitoringAlert(BaseModel):
    """Alert for monitoring specific addresses or wards"""
    id: str
    user_id: str
    name: str
    alert_type: str  # address, postcode, ward, keyword
    value: str  # The address/postcode/ward/keyword to monitor
    is_active: bool = True
    created_at: datetime
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


class AlertTrigger(BaseModel):
    """When an alert is triggered"""
    alert_id: str
    case_reference: str
    triggered_at: datetime
    match_reason: str


# API Key Model
class APIKey(BaseModel):
    """API key for programmatic access"""
    id: str
    user_id: str
    name: str
    key_prefix: str  # First 8 chars for identification
    hashed_key: str
    scopes: List[str] = ["read"]  # read, write, admin
    is_active: bool = True
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None


# Audit Log
class AuditLog(BaseModel):
    """Audit log for compliance"""
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime


# Token Models
class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """Data extracted from JWT"""
    user_id: str
    email: str
    role: UserRole
    scopes: List[str] = []
