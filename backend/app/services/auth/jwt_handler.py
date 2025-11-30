"""
JWT Token Handler
Secure token generation and validation for authentication
"""

from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import secrets

from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class TokenPayload:
    """Decoded JWT payload"""
    user_id: str
    email: str
    role: str
    team_id: Optional[str] = None
    scopes: list = None
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # JWT ID for token revocation

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: str = ""


class JWTHandler:
    """Handles JWT token operations"""

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7

    def create_access_token(
        self,
        user_id: str,
        email: str,
        role: str,
        team_id: Optional[str] = None,
        scopes: list = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a new access token"""
        if scopes is None:
            scopes = []

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode = {
            "sub": user_id,
            "email": email,
            "role": role,
            "team_id": team_id,
            "scopes": scopes,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16),
            "type": "access"
        }

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a new refresh token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16),
            "type": "refresh"
        }

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_token_pair(
        self,
        user_id: str,
        email: str,
        role: str,
        team_id: Optional[str] = None,
        scopes: list = None
    ) -> TokenResponse:
        """Create both access and refresh tokens"""
        access_token = self.create_access_token(
            user_id=user_id,
            email=email,
            role=role,
            team_id=team_id,
            scopes=scopes
        )

        refresh_token = self.create_refresh_token(user_id=user_id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60,
            scope=" ".join(scopes) if scopes else ""
        )

    def decode_token(self, token: str) -> Optional[TokenPayload]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            return TokenPayload(
                user_id=payload.get("sub"),
                email=payload.get("email", ""),
                role=payload.get("role", ""),
                team_id=payload.get("team_id"),
                scopes=payload.get("scopes", []),
                exp=datetime.fromtimestamp(payload.get("exp", 0)),
                iat=datetime.fromtimestamp(payload.get("iat", 0)),
                jti=payload.get("jti")
            )
        except JWTError:
            return None

    def verify_token(self, token: str, expected_type: str = "access") -> Optional[TokenPayload]:
        """Verify token and check type"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("type") != expected_type:
                return None

            return TokenPayload(
                user_id=payload.get("sub"),
                email=payload.get("email", ""),
                role=payload.get("role", ""),
                team_id=payload.get("team_id"),
                scopes=payload.get("scopes", []),
                exp=datetime.fromtimestamp(payload.get("exp", 0)),
                iat=datetime.fromtimestamp(payload.get("iat", 0)),
                jti=payload.get("jti")
            )
        except JWTError:
            return None

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def create_email_verification_token(self, email: str) -> str:
        """Create token for email verification"""
        expire = datetime.utcnow() + timedelta(hours=24)
        to_encode = {
            "email": email,
            "exp": expire,
            "type": "email_verification"
        }
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_email_token(self, token: str) -> Optional[str]:
        """Verify email verification token and return email"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "email_verification":
                return None
            return payload.get("email")
        except JWTError:
            return None

    def create_password_reset_token(self, user_id: str) -> str:
        """Create token for password reset"""
        expire = datetime.utcnow() + timedelta(hours=1)
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "type": "password_reset",
            "jti": secrets.token_urlsafe(16)
        }
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_password_reset_token(self, token: str) -> Optional[str]:
        """Verify password reset token and return user_id"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "password_reset":
                return None
            return payload.get("sub")
        except JWTError:
            return None
