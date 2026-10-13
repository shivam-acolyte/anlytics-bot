from fastapi import APIRouter, Query
from typing import Optional, List
from app.services.analytics_service import analytics_service
from app.scheduler import scheduler
from app.database import db
from app.mysql_database import db_mysql

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/platforms")
async def get_platforms():
    """Fetch health, connection stats, and metadata for both platforms."""
    return analytics_service.get_platforms_status()

@router.get("/websites")
async def get_websites(
    platform: str = Query("living", description="Platform: living or startupflora")
):
    websites = analytics_service.get_websites(platform=platform)
    return {"websites": websites, "platform": platform}

@router.get("/utms")
async def get_utms(
    platform: str = Query("living", description="Platform: living or startupflora"),
    days: int = Query(60, ge=1, le=365)
):
    utms = analytics_service.get_utms(platform=platform, days=days)
    return {"utms": utms, "platform": platform}

@router.get("/kpis")
async def get_kpis(
    site: Optional[str] = Query(None, description="Website domain or all"),
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("Asia/Kolkata"),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None, description="UTM filter, e.g. campaign:xyz or source:abc"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    data = analytics_service.get_kpis(
        site=site, days=days, tz=tz, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return data

@router.get("/heatmap")
async def get_heatmap(
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("Asia/Kolkata"),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_hourly_heatmap(
        site=site, days=days, tz=tz, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return data

@router.get("/trends")
async def get_trends(
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("Asia/Kolkata"),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_daily_trends(
        site=site, days=days, tz=tz, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return {"trends": data, "platform": platform}

@router.get("/events")
async def get_events(
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_events_breakdown(
        site=site, days=days, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return {"events": data, "platform": platform}

@router.get("/top-pages")
async def get_top_pages(
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(15, ge=1, le=100),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_top_pages(
        site=site, days=days, limit=limit, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return {"pages": data, "platform": platform}

@router.get("/search-pages")
async def search_pages(
    q: Optional[str] = Query("", description="Page URL search query"),
    limit: int = Query(25, ge=1, le=100),
    days: int = Query(60, ge=1, le=365),
    platform: str = Query("living", description="Platform: living or startupflora"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.search_pages(
        query=q or "", platform=platform, limit=limit, days=days,
        start_date=start_date, end_date=end_date
    )
    return {"pages": data, "platform": platform, "query": q or ""}

@router.get("/page-details")
async def get_page_details(
    url: str = Query(..., description="Target page URL"),
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("Asia/Kolkata"),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_page_deep_dive(
        page_url=url, site=site, days=days, tz=tz, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return data

@router.get("/granular-timeline")
async def get_granular_timeline(
    granularity: str = Query("hour", description="Granularity: hour, 30min, 15min, minute, day"),
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    page_url: Optional[str] = Query(None),
    tz: str = Query("Asia/Kolkata"),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_granular_analysis(
        granularity=granularity, 
        site=site, 
        days=days, 
        page_url=page_url, 
        tz=tz,
        platform=platform,
        utm=utm,
        start_date=start_date,
        end_date=end_date
    )
    return data

@router.get("/geo")
async def get_geo(
    site: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    platform: str = Query("living", description="Platform: living or startupflora"),
    utm: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    data = analytics_service.get_geo_and_referrers(
        site=site, days=days, platform=platform, utm=utm,
        start_date=start_date, end_date=end_date
    )
    return data

@router.get("/compare")
async def compare_sites(
    site_a: str = Query(..., description="First site domain"),
    site_b: str = Query(..., description="Second site domain"),
    days: int = Query(30, ge=1, le=365),
    platform: str = Query("living", description="Platform: living or startupflora")
):
    data = analytics_service.compare_websites(site_a=site_a, site_b=site_b, days=days, platform=platform)
    return data

@router.post("/refresh")
async def trigger_refresh():
    result = scheduler.trigger_now()
    return result

@router.get("/tables")
async def get_tables(
    platform: str = Query("living", description="Platform: living or startupflora")
):
    if platform == "startupflora":
        tables = db_mysql.list_available_tables()
    else:
        tables = db.list_available_tables()
    return {"tables": tables, "platform": platform}

@router.get("/table/{table_name}/schema")
async def get_table_schema(
    table_name: str,
    platform: str = Query("living", description="Platform: living or startupflora")
):
    if platform == "startupflora":
        schema = db_mysql.get_table_schema(table_name)
    else:
        schema = db.get_table_schema(table_name)
    return {"table": table_name, "columns": schema, "platform": platform}
