import logging
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from app.services.lead_service import lead_service

logger = logging.getLogger("trackingbot.lead_routes")

router = APIRouter(prefix="/api/leads", tags=["leads"])

@router.get("/summary")
async def get_leads_summary(
    platform: str = Query("startupflora", description="Platform: living or startupflora"),
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Retrieve aggregate metrics, top endpoints, sources, and daily trends for leads."""
    try:
        data = lead_service.get_leads_summary(
            platform=platform,
            days=days,
            start_date=start_date,
            end_date=end_date
        )
        return data
    except Exception as e:
        logger.error(f"Error in /api/leads/summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def get_leads_list(
    platform: str = Query("startupflora", description="Platform: living or startupflora"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=5, le=100),
    search: Optional[str] = Query(None, description="Search term for name, email, phone, endpoint"),
    endpoint: Optional[str] = Query(None, description="Filter by exact endpoint"),
    source: Optional[str] = Query(None, description="Filter by source"),
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Retrieve paginated leads with endpoint attribution and quick info."""
    try:
        data = lead_service.get_leads_list(
            platform=platform,
            page=page,
            limit=limit,
            search=search,
            endpoint=endpoint,
            source=source,
            days=days,
            start_date=start_date,
            end_date=end_date
        )
        return data
    except Exception as e:
        logger.error(f"Error in /api/leads/list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/endpoints")
async def get_lead_endpoints(
    platform: str = Query("startupflora", description="Platform: living or startupflora"),
    days: int = Query(60, ge=1, le=365)
):
    """Retrieve list of distinct endpoints generating leads with counts."""
    try:
        endpoints = lead_service.get_lead_endpoints(platform=platform, days=days)
        return {"endpoints": endpoints, "platform": platform}
    except Exception as e:
        logger.error(f"Error in /api/leads/endpoints: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources")
async def get_lead_sources(
    platform: str = Query("startupflora", description="Platform: living or startupflora"),
    days: int = Query(60, ge=1, le=365)
):
    """Retrieve list of distinct lead sources with counts."""
    try:
        sources = lead_service.get_lead_sources(platform=platform, days=days)
        return {"sources": sources, "platform": platform}
    except Exception as e:
        logger.error(f"Error in /api/leads/sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{lead_id}/journey")
async def get_lead_journey(
    lead_id: int,
    platform: str = Query("startupflora", description="Platform: living or startupflora")
):
    """Retrieve 360° lead details with matched session, dwell time, and chronological event journey."""
    try:
        data = lead_service.get_lead_journey_and_details(lead_id=lead_id, platform=platform)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in /api/leads/{lead_id}/journey: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
