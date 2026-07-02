"""JWT authentication and the mapping from app user -> Postgres role.

Each user is associated with a Postgres role that has SELECT grants only on the
tables they may see. The API authenticates the JWT, resolves the role, and (in
the DB layer) issues ``SET ROLE`` so row-level security policies apply — no
shared admin connection, no data leakage between tenants.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from bizlens.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, pg_role: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {"sub": subject, "role": pg_role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
    """Resolve the authenticated user + their Postgres role from the JWT."""
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
    return {"username": payload.get("sub"), "pg_role": payload.get("role")}
