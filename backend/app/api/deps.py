from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.security import AuthError, decode_access_token, parse_bearer_token
from app.db.base import get_db
from app.models import User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = parse_bearer_token(authorization)
    payload = decode_access_token(token)
    subject = payload.get("sub")
    if not subject:
        raise AuthError("Token missing subject")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise AuthError("Token subject invalid") from exc

    user = db.get(User, user_id)
    if user is None:
        raise AuthError("User not found")
    return user
