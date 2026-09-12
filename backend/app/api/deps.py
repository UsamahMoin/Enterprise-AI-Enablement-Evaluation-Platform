"""Shared FastAPI dependencies: authentication and role gates."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.enums import SystemRole
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    stmt = (
        select(User)
        .options(selectinload(User.department))
        .where(User.id == payload["sub"], User.is_active.is_(True))
    )
    user = (await db.execute(stmt)).scalars().first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_roles(*roles: SystemRole):
    """Dependency factory gating a route on the caller's system role."""

    allowed = {str(role) for role in roles}

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.system_role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of: {', '.join(sorted(allowed))}",
            )
        return user

    return _guard


require_admin = require_roles(SystemRole.ADMIN)
require_manager = require_roles(SystemRole.ADMIN, SystemRole.MANAGER)
