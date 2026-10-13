from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.services.ai_chat_service import ai_chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    platform: Optional[str] = "living"

@router.post("/message")
async def chat_message(req: ChatRequest):
    result = ai_chat_service.process_message(req.message, req.history, platform=req.platform or "living")
    return result

@router.get("/suggestions")
async def get_suggestions():
    return {
        "suggestions": [
            "Which time period has the lowest user traffic?",
            "What are our peak active hours?",
            "Show multi-website traffic distribution",
            "What are the top 5 visited pages?",
            "Break down conversion events (pageviews vs clicks)",
            "Compare Sunday vs Wednesday user activity"
        ]
    }
