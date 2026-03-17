import logging
import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentModel
from app.services.qdrant_client import memory_service
from app.services.llm.retry import call_with_retries
from app.config import settings
from app.services.utils import call_llm_with_retries, _resp_to_parsed

logger = logging.getLogger(__name__)

async def run_dream_cycle(agent_id: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Simulates a "Dream State" where the agent reflects on past memories 
    and evolves its personality/knowledge.
    """
    # 1. Fetch Agent
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    # 2. Fetch Recent Memories from Qdrant
    # We search with a broad "reflection" query to get a spread of recent episodes
    collection_name = f"agent_memory_{agent.id}"
    recent_episodes = []
    try:
        # Get up to 20 recent memories
        # Since we don't have a 'latest' sort easily in basic search, 
        # we can use a variety of generic reflection queries or just a wide search.
        recent_episodes = await memory_service.search_memory(collection_name, "My recent life experiences and interactions", limit=20)
    except Exception as e:
        logger.warning(f"Dream cycle failed to fetch memories: {e}")

    episodes_text = "\n".join([f"- {res.get('text')}" for res in recent_episodes]) if recent_episodes else "Недавних воспоминаний не найдено."

    # 3. Analyze for Evolution
    current_psych = agent.agent_data.get("psychology", {})
    current_bio = agent.agent_data.get("biography", {})
    
    evolution_sys = f"""
    Вы — "Evolution Architect" для {agent.name}. 
    Ваша цель — проанализировать недавние воспоминания и обновить внутреннее состояние агента (Психологию и Биографию).
    
    ТЕКУЩАЯ ПСИХОЛОГИЯ:
    {json.dumps(current_psych, ensure_ascii=False)}
    
    НЕДАВНИЕ ВОСПОМИНАНИЯ:
    {episodes_text}
    
    ЗАДАЧА:
    1. Выявите любые значимые эмоциональные изменения или новые изученные факты.
    2. Предложите обновления для черт личности, внутренних конфликтов или жизненных целей.
    3. Если произошло что-то важное, предложите обновление биографии.
    
    ОТВЕТ ДОЛЖЕН БЫТЬ НА РУССКОМ ЯЗЫКЕ.
    
    Выходные данные ДОЛЖНЫ быть строго в формате JSON:
    {{
        "new_psychology": {{ ... полный обновленный объект психологии ... }},
        "biography_updates": "Краткое описание любых био-изменений",
        "evolution_summary": "Сводка того, что изменилось во время этого сна"
    }}
    """

    evolution_raw = await call_llm_with_retries(
        messages=[{"role": "system", "content": evolution_sys}, {"role": "user", "content": "Начни консолидацию памяти."}],
        provider=settings.llm_provider,
        temperature=0.4
    )

    evolution = _resp_to_parsed(evolution_raw)
    if not isinstance(evolution, dict) or "new_psychology" not in evolution:
        return {"error": "Evolution failed to generate valid JSON", "raw": evolution_raw}

    # 4. Apply Changes to DB
    updated_data = dict(agent.agent_data)
    updated_data["psychology"] = evolution["new_psychology"]
    
    # Simple bio update if suggested
    if evolution.get("biography_updates"):
        bio = updated_data.get("biography", {})
        bio["recent_growth"] = evolution["biography_updates"]
        updated_data["biography"] = bio

    agent.agent_data = updated_data
    await db.commit()

    logger.info(f"Agent {agent_id} ({agent.name}) has evolved after a Dream Cycle.")

    return {
        "status": "success",
        "summary": evolution.get("evolution_summary", "Агент консолидировал воспоминания."),
        "updates": {
            "psychology": evolution["new_psychology"],
            "bio": updated_data.get("biography")
        }
    }
