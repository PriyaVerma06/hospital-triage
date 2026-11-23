"""
Authentication and Role-Based Access Control (RBAC) module for hospital triage system.
Provides password hashing via bcrypt, JWT token generation/validation via PyJWT,
FastAPI dependencies for user authentication and role enforcement, and WebSocket auth helpers.
"""

from datetime import datetime, timedelta, timezone
import os
from typing import List, Optional, Union
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import User, UserRole

# Secret key configuration: defaults to development key if TRIAGE_SECRET_KEY is not set
SECRET_KEY = os.getenv(
    "TRIAGE_SECRET_KEY",
    "dev-secret-key-hospital-triage-change-in-production-only-very-secure",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt directly."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    user: User,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate an HS256-signed JWT access token containing user identity and role claims.
    Payload claims: sub (user id), username, role, doctor_id, exp.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": role_val,
        "doctor_id": user.doctor_id,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: decodes Bearer token, fetches user from database,
    and returns authenticated User model.
    Raises 401 on invalid/expired token or inactive account.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: Union[UserRole, str]):
    """
    Dependency factory to enforce role-based permissions.
    Returns 403 Forbidden with a descriptive message if current user's role is not allowed.
    """
    allowed_roles = {r.value if hasattr(r, "value") else str(r) for r in roles}

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{user_role}' is not authorized for this resource",
            )
        return current_user

    return role_dependency


def decode_token_for_ws(token: str) -> Optional[dict]:
    """
    Validate and decode a JWT token for WebSocket authentication.
    Returns user claims dict (id, username, role, doctor_id) if token is valid, else None.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        role = payload.get("role")
        username = payload.get("username")
        if not user_id_str or not role or not username:
            return None
        return {
            "id": int(user_id_str),
            "username": username,
            "role": role,
            "doctor_id": payload.get("doctor_id"),
        }
    except Exception:
        return None
