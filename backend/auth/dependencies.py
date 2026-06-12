from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth.utils import decode_token
import redis as redis_client
from config import settings

_redis = redis_client.from_url(settings.REDIS_URL, decode_responses=True)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    # Check if token has been blacklisted (logout)
    try:
        if _redis.exists(f"blacklist:{token}"):
            raise credentials_exception
    except Exception:
        pass  # Redis unavailable — allow request through gracefully

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def require_manufacturer(user: User = Depends(get_current_user)) -> User:
    if user.role != "manufacturer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manufacturer access only",
        )
    if not user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not linked to a manufacturer (entity_id missing)",
        )
    return user


def require_supplier(user: User = Depends(get_current_user)) -> User:
    if user.role != "supplier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier access only",
        )
    if not user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not linked to a supplier (entity_id missing)",
        )
    return user


def require_consumer(user: User = Depends(get_current_user)) -> User:
    if user.role != "consumer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hospital/NGO access only",
        )
    if not user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not linked to a hospital/NGO (entity_id missing)",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access only",
        )
    return user

