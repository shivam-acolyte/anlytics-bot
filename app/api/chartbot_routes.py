from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.chart_bot_service import chart_bot_service

router = APIRouter(prefix="/api/chartbot", tags=["chartbot"])

class ChartRequest(BaseModel):
    prompt: str
    site: Optional[str] = None
    days: Optional[int] = 30
    platform: Optional[str] = "living"

@router.post("/generate")
async def generate_chart(req: ChartRequest):
    chart_config = chart_bot_service.generate_chart(
        req.prompt, 
        site=req.site, 
        days=req.days or 30,
        platform=req.platform or "living"
    )
    return chart_config
