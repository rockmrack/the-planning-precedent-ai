"""
User Management API Routes
Handles user profile, teams, and settings
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.models.user import (
    User, UserUpdate, UserRole, SubscriptionTier,
    Team, TeamCreate, TeamMember, TeamInvite,
    Project, ProjectCreate, SavedCase, NotificationPreferences,
    TIER_LIMITS
)
from app.api.v1.auth import require_auth, require_admin, require_professional

router = APIRouter(prefix="/users", tags=["Users"])


# Response Models
class UserProfileResponse(BaseModel):
    """Full user profile response"""
    id: str
    email: str
    full_name: str
    company: Optional[str]
    job_title: Optional[str]
    phone: Optional[str]
    role: str
    subscription_tier: str
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    team_id: Optional[str]
    usage: dict
    limits: dict


class UsageResponse(BaseModel):
    """Usage statistics response"""
    searches_this_month: int
    analyses_this_month: int
    exports_this_month: int
    searches_limit: int
    analyses_limit: int
    exports_limit: int
    saved_cases_count: int
    saved_cases_limit: int


class TeamResponse(BaseModel):
    """Team information response"""
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    subscription_tier: str
    member_count: int
    created_at: datetime


class TeamMemberResponse(BaseModel):
    """Team member response"""
    user_id: str
    email: str
    full_name: str
    role: str
    joined_at: datetime


class ProjectResponse(BaseModel):
    """Project response"""
    id: str
    name: str
    description: Optional[str]
    site_address: Optional[str]
    client_name: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    saved_case_count: int
    analysis_count: int


class InviteRequest(BaseModel):
    """Team invite request"""
    email: EmailStr
    role: str = "member"


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


# Profile endpoints
@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(user: User = Depends(require_auth)):
    """
    Get current user's full profile including usage and limits.
    """
    limits = TIER_LIMITS.get(user.subscription_tier)

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        job_title=user.job_title,
        phone=user.phone,
        role=user.role.value,
        subscription_tier=user.subscription_tier.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login,
        team_id=user.team_id,
        usage={
            "searches_this_month": user.searches_this_month,
            "analyses_this_month": user.analyses_this_month,
            "exports_this_month": user.exports_this_month
        },
        limits={
            "searches_per_month": limits.searches_per_month if limits else 0,
            "analyses_per_month": limits.analyses_per_month if limits else 0,
            "exports_per_month": limits.exports_per_month if limits else 0,
            "saved_cases": limits.saved_cases if limits else 0,
            "team_members": limits.team_members if limits else 0,
            "api_access": limits.api_access if limits else False,
            "priority_support": limits.priority_support if limits else False,
            "custom_branding": limits.custom_branding if limits else False
        }
    )


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(
    updates: UserUpdate,
    user: User = Depends(require_auth)
):
    """
    Update current user's profile.

    Only provided fields will be updated.
    """
    # TODO: Implement actual database update
    # For now, return updated user with changes
    updated_user = user.model_copy(update=updates.model_dump(exclude_unset=True))

    limits = TIER_LIMITS.get(updated_user.subscription_tier)

    return UserProfileResponse(
        id=updated_user.id,
        email=updated_user.email,
        full_name=updated_user.full_name,
        company=updated_user.company,
        job_title=updated_user.job_title,
        phone=updated_user.phone,
        role=updated_user.role.value,
        subscription_tier=updated_user.subscription_tier.value,
        is_verified=updated_user.is_verified,
        created_at=updated_user.created_at,
        last_login=updated_user.last_login,
        team_id=updated_user.team_id,
        usage={
            "searches_this_month": updated_user.searches_this_month,
            "analyses_this_month": updated_user.analyses_this_month,
            "exports_this_month": updated_user.exports_this_month
        },
        limits={
            "searches_per_month": limits.searches_per_month if limits else 0,
            "analyses_per_month": limits.analyses_per_month if limits else 0,
            "exports_per_month": limits.exports_per_month if limits else 0,
            "saved_cases": limits.saved_cases if limits else 0,
            "team_members": limits.team_members if limits else 0,
            "api_access": limits.api_access if limits else False,
            "priority_support": limits.priority_support if limits else False,
            "custom_branding": limits.custom_branding if limits else False
        }
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user: User = Depends(require_auth)):
    """
    Get current usage statistics and limits.
    """
    limits = TIER_LIMITS.get(user.subscription_tier)

    return UsageResponse(
        searches_this_month=user.searches_this_month,
        analyses_this_month=user.analyses_this_month,
        exports_this_month=user.exports_this_month,
        searches_limit=limits.searches_per_month if limits else 0,
        analyses_limit=limits.analyses_per_month if limits else 0,
        exports_limit=limits.exports_per_month if limits else 0,
        saved_cases_count=0,  # TODO: Get from database
        saved_cases_limit=limits.saved_cases if limits else 0
    )


# Team endpoints
@router.post("/team", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    user: User = Depends(require_professional)
):
    """
    Create a new team. Requires Professional or higher subscription.
    """
    limits = TIER_LIMITS.get(user.subscription_tier)
    if not limits or limits.team_members <= 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your subscription does not support team features"
        )

    # TODO: Create team in database
    team = Team(
        id="team_" + user.id[:8],
        name=team_data.name,
        description=team_data.description,
        owner_id=user.id,
        subscription_tier=user.subscription_tier,
        created_at=datetime.utcnow(),
        member_count=1,
        is_active=True
    )

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        owner_id=team.owner_id,
        subscription_tier=team.subscription_tier.value,
        member_count=team.member_count,
        created_at=team.created_at
    )


@router.get("/team", response_model=TeamResponse)
async def get_team(user: User = Depends(require_auth)):
    """
    Get current user's team information.
    """
    if not user.team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of any team"
        )

    # TODO: Get team from database
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Team not found"
    )


@router.get("/team/members", response_model=List[TeamMemberResponse])
async def get_team_members(user: User = Depends(require_auth)):
    """
    Get all members of current user's team.
    """
    if not user.team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of any team"
        )

    # TODO: Get team members from database
    return []


@router.post("/team/invite", response_model=MessageResponse)
async def invite_team_member(
    invite: InviteRequest,
    user: User = Depends(require_professional)
):
    """
    Invite a new member to the team.
    """
    if not user.team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must create or join a team first"
        )

    # Check team member limits
    limits = TIER_LIMITS.get(user.subscription_tier)
    # TODO: Check current member count against limit

    # TODO: Send invitation email
    return MessageResponse(message=f"Invitation sent to {invite.email}")


@router.delete("/team/members/{member_id}", response_model=MessageResponse)
async def remove_team_member(
    member_id: str,
    user: User = Depends(require_professional)
):
    """
    Remove a member from the team. Owner only.
    """
    # TODO: Verify user is team owner
    # TODO: Remove member from database
    return MessageResponse(message="Member removed from team")


# Project endpoints
@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    user: User = Depends(require_auth)
):
    """
    List all projects for current user.
    """
    # TODO: Get projects from database
    return []


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    user: User = Depends(require_auth)
):
    """
    Create a new project for organizing cases and analyses.
    """
    project = Project(
        id="proj_" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        name=project_data.name,
        description=project_data.description,
        site_address=project_data.site_address,
        client_name=project_data.client_name,
        user_id=user.id,
        team_id=user.team_id,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        saved_case_ids=[],
        analysis_ids=[],
        notes=None
    )

    # TODO: Save to database

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        site_address=project.site_address,
        client_name=project.client_name,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        saved_case_count=len(project.saved_case_ids),
        analysis_count=len(project.analysis_ids)
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User = Depends(require_auth)
):
    """
    Get a specific project by ID.
    """
    # TODO: Get project from database and verify ownership
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Project not found"
    )


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    updates: ProjectCreate,
    user: User = Depends(require_auth)
):
    """
    Update a project.
    """
    # TODO: Update project in database
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Project not found"
    )


@router.delete("/projects/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: str,
    user: User = Depends(require_auth)
):
    """
    Delete a project. This does not delete saved cases or analyses.
    """
    # TODO: Delete project from database
    return MessageResponse(message="Project deleted")


# Saved cases endpoints
@router.get("/saved-cases", response_model=List[SavedCase])
async def list_saved_cases(
    project_id: Optional[str] = None,
    favorite_only: bool = False,
    user: User = Depends(require_auth)
):
    """
    List all saved cases for current user.
    """
    # TODO: Get saved cases from database
    return []


@router.post("/saved-cases", response_model=SavedCase, status_code=status.HTTP_201_CREATED)
async def save_case(
    case_reference: str,
    project_id: Optional[str] = None,
    notes: Optional[str] = None,
    tags: List[str] = [],
    user: User = Depends(require_auth)
):
    """
    Save a case for later reference.
    """
    # Check saved case limits
    limits = TIER_LIMITS.get(user.subscription_tier)
    # TODO: Check current saved case count against limit

    saved_case = SavedCase(
        id="saved_" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        user_id=user.id,
        project_id=project_id,
        case_reference=case_reference,
        notes=notes,
        tags=tags,
        saved_at=datetime.utcnow(),
        is_favorite=False
    )

    # TODO: Save to database

    return saved_case


@router.delete("/saved-cases/{case_id}", response_model=MessageResponse)
async def unsave_case(
    case_id: str,
    user: User = Depends(require_auth)
):
    """
    Remove a case from saved cases.
    """
    # TODO: Delete from database
    return MessageResponse(message="Case removed from saved")


@router.patch("/saved-cases/{case_id}/favorite", response_model=SavedCase)
async def toggle_favorite(
    case_id: str,
    user: User = Depends(require_auth)
):
    """
    Toggle favorite status on a saved case.
    """
    # TODO: Update in database
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Saved case not found"
    )


# Notification preferences
@router.get("/notification-preferences", response_model=NotificationPreferences)
async def get_notification_preferences(user: User = Depends(require_auth)):
    """
    Get current notification preferences.
    """
    # TODO: Get from database
    return NotificationPreferences()


@router.patch("/notification-preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    user: User = Depends(require_auth)
):
    """
    Update notification preferences.
    """
    # TODO: Save to database
    return preferences


# Admin endpoints
@router.get("/admin/all", response_model=List[UserProfileResponse])
async def list_all_users(
    page: int = 1,
    page_size: int = 20,
    admin: User = Depends(require_admin)
):
    """
    List all users. Admin only.
    """
    # TODO: Get all users from database with pagination
    return []


@router.patch("/admin/{user_id}/role", response_model=MessageResponse)
async def update_user_role(
    user_id: str,
    role: UserRole,
    admin: User = Depends(require_admin)
):
    """
    Update a user's role. Admin only.
    """
    # TODO: Update user role in database
    return MessageResponse(message=f"User role updated to {role.value}")


@router.patch("/admin/{user_id}/subscription", response_model=MessageResponse)
async def update_user_subscription(
    user_id: str,
    tier: SubscriptionTier,
    admin: User = Depends(require_admin)
):
    """
    Update a user's subscription tier. Admin only.
    """
    # TODO: Update subscription in database
    return MessageResponse(message=f"Subscription updated to {tier.value}")


@router.delete("/admin/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: str,
    admin: User = Depends(require_admin)
):
    """
    Deactivate a user account. Admin only.
    """
    # TODO: Set is_active = False in database
    return MessageResponse(message="User account deactivated")
