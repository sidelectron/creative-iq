"""FastAPI dependencies (auth + brand-scoped RBAC)."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.db import Ad, BrandMember, User
from shared.models.enums import BrandRole, brand_role_rank
from shared.utils.db import get_db
from shared.utils.security import JWTError, decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


def require_brand_role(min_role: BrandRole):
    async def _dep(
        brand_id: uuid.UUID,
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> BrandMember:
        result = await db.execute(
            select(BrandMember).where(
                BrandMember.brand_id == brand_id,
                BrandMember.user_id == user.id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this brand",
            )
        role = BrandRole(membership.role)
        if brand_role_rank(role) < brand_role_rank(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this brand",
            )
        return membership

    return _dep


def require_ad_brand_role(min_role: BrandRole):
    async def _dep(
        ad_id: uuid.UUID,
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> Ad:
        result = await db.execute(select(Ad).where(Ad.id == ad_id, Ad.deleted_at.is_(None)))
        ad = result.scalar_one_or_none()
        if ad is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
        m_result = await db.execute(
            select(BrandMember).where(
                BrandMember.brand_id == ad.brand_id,
                BrandMember.user_id == user.id,
            )
        )
        membership = m_result.scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this brand",
            )
        role = BrandRole(membership.role)
        if brand_role_rank(role) < brand_role_rank(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this ad",
            )
        return ad

    return _dep
