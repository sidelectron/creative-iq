"""Brand and member routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.models.db import Brand, BrandMember, User
from shared.models.enums import BrandRole
from shared.models.schemas import (
    BrandCreate,
    BrandListItem,
    BrandMemberCreate,
    BrandMemberInfo,
    BrandMemberResponse,
    BrandResponse,
    BrandUpdate,
    PaginatedResponse,
)
from shared.utils.db import get_db
from services.api.app.dependencies import get_current_active_user, require_brand_role

router = APIRouter(prefix="/brands", tags=["brands"])


async def _brand_to_response(db: AsyncSession, brand: Brand) -> BrandResponse:
    await db.refresh(brand, ["members"])
    members_out: list[BrandMemberInfo] = []
    for m in brand.members:
        await db.refresh(m, ["user"])
        members_out.append(
            BrandMemberInfo(
                user_id=m.user_id,
                email=m.user.email,
                full_name=m.user.full_name,
                role=BrandRole(m.role),
            )
        )
    return BrandResponse(
        id=brand.id,
        name=brand.name,
        industry=brand.industry,
        description=brand.description,
        website_url=brand.website_url,
        guidelines_gcs_path=brand.guidelines_gcs_path,
        success_metrics=list(brand.success_metrics or []),
        settings=dict(brand.settings or {}),
        created_by=brand.created_by,
        created_at=brand.created_at,
        updated_at=brand.updated_at,
        deleted_at=brand.deleted_at,
        member_count=len(brand.members),
        members=members_out,
    )


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    body: BrandCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    metrics = body.success_metrics if body.success_metrics is not None else ["ctr"]
    brand = Brand(
        name=body.name,
        industry=body.industry,
        description=body.description,
        website_url=body.website_url,
        success_metrics=metrics,
        created_by=user.id,
    )
    db.add(brand)
    await db.flush()
    member = BrandMember(brand_id=brand.id, user_id=user.id, role=BrandRole.OWNER.value)
    db.add(member)
    await db.commit()
    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.members).selectinload(BrandMember.user))
        .where(Brand.id == brand.id)
    )
    brand = result.scalar_one()
    return await _brand_to_response(db, brand)


@router.get("", response_model=PaginatedResponse[BrandListItem])
async def list_brands(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[BrandListItem]:
    base = (
        select(Brand, BrandMember)
        .join(BrandMember, BrandMember.brand_id == Brand.id)
        .where(
            BrandMember.user_id == user.id,
            Brand.deleted_at.is_(None),
        )
    )
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(Brand)
            .join(BrandMember, BrandMember.brand_id == Brand.id)
            .where(BrandMember.user_id == user.id, Brand.deleted_at.is_(None))
        )
        or 0
    )
    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Brand.created_at.desc()).offset(offset).limit(page_size)
    )
    rows = result.all()
    items = [
        BrandListItem(
            id=b.id,
            name=b.name,
            industry=b.industry,
            created_at=b.created_at,
            role=BrandRole(m.role),
        )
        for b, m in rows
    ]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.members).selectinload(BrandMember.user))
        .where(Brand.id == brand_id, Brand.deleted_at.is_(None))
    )
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return await _brand_to_response(db, brand)


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: uuid.UUID,
    body: BrandUpdate,
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    if body.name is not None:
        brand.name = body.name
    if body.industry is not None:
        brand.industry = body.industry
    if body.description is not None:
        brand.description = body.description
    if body.website_url is not None:
        brand.website_url = body.website_url
    if body.success_metrics is not None:
        brand.success_metrics = body.success_metrics
    if body.settings is not None:
        brand.settings = body.settings
    await db.commit()
    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.members).selectinload(BrandMember.user))
        .where(Brand.id == brand_id)
    )
    brand = result.scalar_one()
    return await _brand_to_response(db, brand)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    brand_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    brand = result.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    brand.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/{brand_id}/members", response_model=BrandMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    brand_id: uuid.UUID,
    body: BrandMemberCreate,
    _: BrandMember = Depends(require_brand_role(BrandRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> BrandMemberResponse:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    u_result = await db.execute(select(User).where(User.email == str(body.email).lower()))
    invited = u_result.scalar_one_or_none()
    if invited is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered user exists with that email address",
        )
    member = BrandMember(brand_id=brand_id, user_id=invited.id, role=body.role.value)
    db.add(member)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this brand",
        )
    await db.refresh(member, ["user"])
    return BrandMemberResponse(
        user_id=invited.id,
        email=invited.email,
        full_name=invited.full_name,
        role=BrandRole(member.role),
    )
