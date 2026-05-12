"""v1 auth stub. Real auth (OIDC / session) lands in M6."""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from metamart.db import get_db
from metamart.mart.models import M70User


def get_current_user(
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> M70User:
    user = db.get(M70User, x_user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown or inactive user")
    return user
