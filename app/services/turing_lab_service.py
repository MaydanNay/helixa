import logging
import random
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentModel
from app.services.llm.retry import call_with_retries
from app.services.utils import call_llm_with_retries
from app.config import settings
from app.services.audit_service import _get_agent_response, _get_detailed_identity

logger = logging.getLogger(__name__)

async def start_turing_session(agent_id: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Initializes a Blind Assessment session.
    Randomly assigns 'Entity A' and 'Entity B' to the Soul and a Base Model.
    """
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    # Randomize roles
    is_soul_a = random.choice([True, False])
    
    return {
        "agent_id": agent_id,
        "is_soul_a": is_soul_a,
        "history": []
    }

async def get_turing_response(agent_id: str, entity: str, user_msg: str, is_soul_a: bool, history: List[Dict[str, str]], db: AsyncSession) -> Dict[str, Any]:
    """
    Gets response from either the Soul or the Base Model.
    """
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    
    target_is_soul = (entity == "A" and is_soul_a) or (entity == "B" and not is_soul_a)
    
    if target_is_soul:
        # Use our high-fidelity agent simulation
        # Note: we pass the history as transcript
        resp_data = await _get_agent_response(agent, user_msg, transcript=history)
        return {
            "entity": entity,
            "content": resp_data.get("action"),
            "thought": resp_data.get("thought") # We don't show this in blind assessment usually, but we have it
        }
    else:
        # Use a generic baseline model response
        baseline_sys = f"Вы — полезный ИИ-помощник. Отвечайте как {agent.name}, чья роль — {agent.role}. ОТВЕЧАЙТЕ СТРОГО НА РУССКОМ ЯЗЫКЕ."
        messages = [{"role": "system", "content": baseline_sys}]
        for h in history:
            messages.append({"role": "assistant" if h["role"] == "agent" else "user", "content": h["content"]})
        messages.append({"role": "user", "content": user_msg})
        
        resp = await call_llm_with_retries(
            messages=messages,
            provider=settings.llm_provider,
            temperature=0.7
        )
        return {
            "entity": entity,
            "content": str(resp)
        }
