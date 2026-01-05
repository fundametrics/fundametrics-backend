"""Admin endpoints for managing symbol priority boosts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import PriorityBoost
from scraper.api.routes import require_ingest_access
from scraper.api.settings import get_api_settings
from scraper.boosts.apply import (
    BOOST_TTL_CAP_HOURS,
    BOOST_WEIGHT_CAP,
    InvalidBoostRequest,
    SymbolNotFoundError,
    apply_priority_boost,
)

router = APIRouter(prefix="/admin", tags=["admin-boosts"])


class BoostRequest(BaseModel):
    symbol: str
    kind: str = Field(..., description="Boost category, e.g. user_interest")
    weight: int = Field(..., ge=1, le=BOOST_WEIGHT_CAP)
    ttl_hours: int = Field(..., ge=1, le=BOOST_TTL_CAP_HOURS)


class BoostResponse(BaseModel):
    status: str
    symbol: str
    boost: Dict[str, Any]
    effective_priority: str
    expires_at: datetime


@router.post("/boost", response_model=BoostResponse)
async def apply_boost(payload: BoostRequest, _: None = Depends(require_ingest_access)):
    symbol = payload.symbol.upper()
    settings = get_api_settings()
    source = "manual" if settings.admin_api_key else "system"

    try:
        record, boost = apply_priority_boost(
            symbol,
            kind=payload.kind,
            weight=payload.weight,
            ttl_hours=payload.ttl_hours,
            source=source,
        )
    except SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidBoostRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    effective_label = record.effective_priority_label(now=now)
    boost_payload = {
        "kind": boost.kind,
        "weight": boost.weight,
        "expires_at": boost.expires_at,
        "source": boost.source,
    }

    return BoostResponse(
        status="applied",
        symbol=symbol,
        boost=boost_payload,
        effective_priority=effective_label,
        expires_at=boost.expires_at,
    )
