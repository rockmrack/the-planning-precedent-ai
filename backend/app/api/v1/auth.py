"""
Authentication API Routes
Handles user registration, login, and token management
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from app.services.auth import AuthService, JWTHandler
from app.models.user import User, UserCreate, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

# Services
auth_service = AuthService()
jwt_handler = JWTHandler()


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    accepted_terms: bool = Field(..., description="Must accept terms of service")


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset"""
    token: str
    new_password: str = Field(..., min_length=8)


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


class UserResponse(BaseModel):
    """User data response"""
    id: str
    email: str
    full_name: str
    company: Optional[str]
    job_title: Optional[str]
    role: str
    subscription_tier: str
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


# Dependency: Get current user
async def get_current_user(
    authorization: Optional[str] = Header(None)
) -> Optional[User]:
    """Get current authenticated user from token"""
    if not authorization:
        return None

    # Extract token from Bearer header
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    return await auth_service.get_current_user(token)


async def require_auth(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authenticated user"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def require_admin(
    user: User = Depends(require_auth)
) -> User:
    """Require admin user"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def require_professional(
    user: User = Depends(require_auth)
) -> User:
    """Require professional or admin user"""
    if user.role not in [UserRole.ADMIN, UserRole.PROFESSIONAL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional access required"
        )
    return user


# Routes
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register a new user account.

    Returns the created user data (without sensitive fields).
    """
    user_create = UserCreate(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        company=request.company,
        job_title=request.job_title,
        phone=request.phone,
        accepted_terms=request.accepted_terms
    )

    user, error = await auth_service.register_user(user_create)

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        job_title=user.job_title,
        role=user.role.value,
        subscription_tier=user.subscription_tier.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.post("/token", response_model=TokenResponse)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token endpoint.

    Use this endpoint for standard OAuth2 password flow.
    """
    tokens, error = await auth_service.authenticate(
        email=form_data.username,  # OAuth2 uses 'username' field
        password=form_data.password
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"}
        )

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.

    Returns access and refresh tokens.
    """
    tokens, error = await auth_service.authenticate(
        email=request.email,
        password=request.password
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """
    Refresh access token using refresh token.

    Use this when the access token expires.
    """
    tokens, error = await auth_service.refresh_tokens(request.refresh_token)

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(require_auth)):
    """
    Get current authenticated user's information.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        job_title=user.job_title,
        role=user.role.value,
        subscription_tier=user.subscription_tier.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(token: str):
    """
    Verify email address using verification token.

    Token is sent to user's email after registration.
    """
    success, message = await auth_service.verify_email(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return MessageResponse(message=message)


@router.post("/request-password-reset", response_model=MessageResponse)
async def request_password_reset(request: PasswordResetRequest):
    """
    Request a password reset email.

    If the email exists, a reset link will be sent.
    """
    _, message = await auth_service.request_password_reset(request.email)
    return MessageResponse(message=message)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: PasswordResetConfirm):
    """
    Reset password using reset token.

    Token is received via email.
    """
    success, message = await auth_service.reset_password(
        token=request.token,
        new_password=request.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return MessageResponse(message=message)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: PasswordChangeRequest,
    user: User = Depends(require_auth)
):
    """
    Change password for authenticated user.

    Requires current password for verification.
    """
    success, message = await auth_service.change_password(
        user_id=user.id,
        current_password=request.current_password,
        new_password=request.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return MessageResponse(message=message)


@router.post("/logout", response_model=MessageResponse)
async def logout(user: User = Depends(require_auth)):
    """
    Logout current user.

    Note: JWT tokens are stateless. Client should discard tokens.
    For full token invalidation, implement a token blacklist.
    """
    # In a production system, you would add the token to a blacklist
    # For now, we just return success
    return MessageResponse(message="Logged out successfully")
