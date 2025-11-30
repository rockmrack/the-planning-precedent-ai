"""
Authentication Service
Handles user authentication, registration, and session management
"""

import logging
from datetime import datetime
from typing import Optional, Tuple
from uuid import uuid4

from app.core.config import settings
from app.models.user import (
    User, UserCreate, UserInDB, UserRole,
    SubscriptionTier, TIER_LIMITS
)
from .jwt_handler import JWTHandler, TokenResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Handles authentication operations"""

    def __init__(self, supabase_client=None):
        self.jwt = JWTHandler()
        self.supabase = supabase_client

    async def register_user(
        self,
        user_data: UserCreate
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Register a new user
        Returns (user, error_message)
        """
        try:
            # Check if terms accepted
            if not user_data.accepted_terms:
                return None, "You must accept the terms of service"

            # Check if email already exists
            existing = await self._get_user_by_email(user_data.email)
            if existing:
                return None, "An account with this email already exists"

            # Hash password
            hashed_password = self.jwt.hash_password(user_data.password)

            # Create user
            user_id = str(uuid4())
            now = datetime.utcnow()

            user_dict = {
                "id": user_id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "company": user_data.company,
                "job_title": user_data.job_title,
                "phone": user_data.phone,
                "hashed_password": hashed_password,
                "role": UserRole.HOMEOWNER.value,
                "subscription_tier": SubscriptionTier.FREE.value,
                "is_active": True,
                "is_verified": False,
                "created_at": now.isoformat(),
                "last_login": None,
                "team_id": None,
                "searches_this_month": 0,
                "analyses_this_month": 0,
                "exports_this_month": 0
            }

            # Save to database
            if self.supabase:
                result = self.supabase.table("users").insert(user_dict).execute()
                if not result.data:
                    return None, "Failed to create user"

            # Create user object (without password)
            user = User(
                id=user_id,
                email=user_data.email,
                full_name=user_data.full_name,
                company=user_data.company,
                job_title=user_data.job_title,
                phone=user_data.phone,
                role=UserRole.HOMEOWNER,
                subscription_tier=SubscriptionTier.FREE,
                is_active=True,
                is_verified=False,
                created_at=now,
                last_login=None,
                team_id=None,
                searches_this_month=0,
                analyses_this_month=0,
                exports_this_month=0
            )

            logger.info(f"User registered: {user.email}")
            return user, None

        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None, f"Registration failed: {str(e)}"

    async def authenticate(
        self,
        email: str,
        password: str
    ) -> Tuple[Optional[TokenResponse], Optional[str]]:
        """
        Authenticate user and return tokens
        Returns (tokens, error_message)
        """
        try:
            # Get user from database
            user = await self._get_user_by_email(email)
            if not user:
                return None, "Invalid email or password"

            # Verify password
            if not self.jwt.verify_password(password, user.hashed_password):
                return None, "Invalid email or password"

            # Check if account is active
            if not user.is_active:
                return None, "Account is deactivated"

            # Update last login
            await self._update_last_login(user.id)

            # Generate tokens
            tokens = self.jwt.create_token_pair(
                user_id=user.id,
                email=user.email,
                role=user.role.value,
                team_id=user.team_id,
                scopes=self._get_user_scopes(user)
            )

            logger.info(f"User authenticated: {email}")
            return tokens, None

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None, "Authentication failed"

    async def refresh_tokens(
        self,
        refresh_token: str
    ) -> Tuple[Optional[TokenResponse], Optional[str]]:
        """
        Refresh access token using refresh token
        Returns (tokens, error_message)
        """
        try:
            # Verify refresh token
            payload = self.jwt.verify_token(refresh_token, expected_type="refresh")
            if not payload:
                return None, "Invalid or expired refresh token"

            # Get user
            user = await self._get_user_by_id(payload.user_id)
            if not user:
                return None, "User not found"

            if not user.is_active:
                return None, "Account is deactivated"

            # Generate new tokens
            tokens = self.jwt.create_token_pair(
                user_id=user.id,
                email=user.email,
                role=user.role.value,
                team_id=user.team_id,
                scopes=self._get_user_scopes(user)
            )

            return tokens, None

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None, "Token refresh failed"

    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from access token"""
        payload = self.jwt.verify_token(token, expected_type="access")
        if not payload:
            return None

        return await self._get_user_by_id(payload.user_id)

    async def verify_email(self, token: str) -> Tuple[bool, str]:
        """Verify user email address"""
        try:
            email = self.jwt.verify_email_token(token)
            if not email:
                return False, "Invalid or expired verification token"

            # Update user verification status
            if self.supabase:
                self.supabase.table("users").update(
                    {"is_verified": True}
                ).eq("email", email).execute()

            return True, "Email verified successfully"

        except Exception as e:
            logger.error(f"Email verification error: {e}")
            return False, "Email verification failed"

    async def request_password_reset(self, email: str) -> Tuple[Optional[str], str]:
        """
        Request password reset
        Returns (reset_token, message)
        """
        try:
            user = await self._get_user_by_email(email)
            if not user:
                # Don't reveal if email exists
                return None, "If an account exists with this email, a reset link will be sent"

            reset_token = self.jwt.create_password_reset_token(user.id)

            # In production, send email with reset link
            # For now, return the token
            logger.info(f"Password reset requested for: {email}")

            return reset_token, "Password reset link sent to your email"

        except Exception as e:
            logger.error(f"Password reset request error: {e}")
            return None, "Password reset request failed"

    async def reset_password(
        self,
        token: str,
        new_password: str
    ) -> Tuple[bool, str]:
        """Reset user password"""
        try:
            user_id = self.jwt.verify_password_reset_token(token)
            if not user_id:
                return False, "Invalid or expired reset token"

            # Hash new password
            hashed_password = self.jwt.hash_password(new_password)

            # Update password
            if self.supabase:
                self.supabase.table("users").update(
                    {"hashed_password": hashed_password}
                ).eq("id", user_id).execute()

            logger.info(f"Password reset for user: {user_id}")
            return True, "Password reset successfully"

        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return False, "Password reset failed"

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> Tuple[bool, str]:
        """Change user password"""
        try:
            user = await self._get_user_by_id(user_id)
            if not user:
                return False, "User not found"

            # Verify current password
            if not self.jwt.verify_password(current_password, user.hashed_password):
                return False, "Current password is incorrect"

            # Hash and update password
            hashed_password = self.jwt.hash_password(new_password)

            if self.supabase:
                self.supabase.table("users").update(
                    {"hashed_password": hashed_password}
                ).eq("id", user_id).execute()

            return True, "Password changed successfully"

        except Exception as e:
            logger.error(f"Password change error: {e}")
            return False, "Password change failed"

    def check_usage_limit(
        self,
        user: User,
        limit_type: str
    ) -> Tuple[bool, int, int]:
        """
        Check if user is within usage limits
        Returns (allowed, current_usage, limit)
        """
        limits = TIER_LIMITS.get(user.subscription_tier)
        if not limits:
            return False, 0, 0

        if limit_type == "searches":
            return (
                user.searches_this_month < limits.searches_per_month,
                user.searches_this_month,
                limits.searches_per_month
            )
        elif limit_type == "analyses":
            return (
                user.analyses_this_month < limits.analyses_per_month,
                user.analyses_this_month,
                limits.analyses_per_month
            )
        elif limit_type == "exports":
            return (
                user.exports_this_month < limits.exports_per_month,
                user.exports_this_month,
                limits.exports_per_month
            )

        return True, 0, 0

    async def increment_usage(self, user_id: str, usage_type: str) -> None:
        """Increment user usage counter"""
        if not self.supabase:
            return

        field_map = {
            "searches": "searches_this_month",
            "analyses": "analyses_this_month",
            "exports": "exports_this_month"
        }

        field = field_map.get(usage_type)
        if not field:
            return

        # Use Supabase RPC for atomic increment
        self.supabase.rpc(
            "increment_usage",
            {"user_id_input": user_id, "field_name": field}
        ).execute()

    def _get_user_scopes(self, user: User) -> list:
        """Get permission scopes for user"""
        scopes = ["read"]

        if user.role in [UserRole.ADMIN, UserRole.PROFESSIONAL]:
            scopes.extend(["write", "export"])

        if user.role == UserRole.ADMIN:
            scopes.append("admin")

        limits = TIER_LIMITS.get(user.subscription_tier)
        if limits and limits.api_access:
            scopes.append("api")

        return scopes

    async def _get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email from database"""
        if not self.supabase:
            # Demo mode - return None
            return None

        try:
            result = self.supabase.table("users").select("*").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                return UserInDB(**result.data[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    async def _get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Get user by ID from database"""
        if not self.supabase:
            return None

        try:
            result = self.supabase.table("users").select("*").eq("id", user_id).execute()
            if result.data and len(result.data) > 0:
                return UserInDB(**result.data[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    async def _update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp"""
        if not self.supabase:
            return

        try:
            self.supabase.table("users").update(
                {"last_login": datetime.utcnow().isoformat()}
            ).eq("id", user_id).execute()
        except Exception as e:
            logger.error(f"Error updating last login: {e}")
