import logging
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentModel
from app.config import settings
from app.services.utils import call_llm_with_retries, _resp_to_parsed

logger = logging.getLogger(__name__)

async def run_agent_refinement(agent_id: str, db: AsyncSession, ci_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes CI failures and applies a "patch" to the agent's DNA (Psychology/Biography)
    to fix inconsistencies and depth issues without full regeneration.
    """
    # 1. Fetch Agent
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    current_data = agent.agent_data or {}
    
    # 2. Prepare Refinement Prompt
    # We feed the LLM the current personality and the "Glitches" found during audit
    glitches = ci_report.get("audit", {}).get("report", {}).get("glitches", [])
    vulnerabilities = ci_report.get("stress", {}).get("report", {}).get("vulnerability_analysis", "")
    audit_summary = ci_report.get("audit", {}).get("report", {}).get("summary", "")
    
    refiner_sys = f"""
    Вы — "Refinement Architect". Ваша задача — "вылечить" ИИ-агента, исправив его внутренние противоречия и увеличив глубину личности.
    
    ТЕКУЩИЕ ДАННЫЕ АГЕНТА:
    - Психология: {json.dumps(current_data.get('psychology'), ensure_ascii=False)}
    - Биография: {json.dumps(current_data.get('biography'), ensure_ascii=False)}
    
    ОТЧЕТ ОБ ОШИБКАХ (CI REPORT):
    - Глюки (Glitches): {glitches}
    - Уязвимости стресс-теста: {vulnerabilities}
    - Резюме аудита: {audit_summary}
    
    ИНСТРУКЦИЯ:
    1. Проанализируйте, какие черты личности или факты биографии приводят к "выходу из роли".
    2. Создайте ОБНОВЛЕННУЮ версию Психологии и/или Биографии. 
    3. Не меняйте всё полностью, исправьте только проблемные места. Добавьте глубины там, где агент кажется поверхностным.
    
    ОТВЕТ ДОЛЖЕН БЫТЬ НА РУССКОМ ЯЗЫКЕ.
    
    Выходные данные ДОЛЖНЫ быть строго в формате JSON:
    {{
        "patch": {{
            "psychology": {{ ... обновленный объект целиком или только изменения ... }},
            "biography": {{ ... обновленный объект целиком или только изменения ... }}
        }},
        "reasoning": "Краткое объяснение, что именно и почему было исправлено."
    }}
    """

    refinement_raw = await call_llm_with_retries(
        messages=[{"role": "system", "content": refiner_sys}, {"role": "user", "content": "Сгенерируй патч для исправления личности агента."}],
        provider=settings.generator_provider,
        temperature=0.3
    )

    # Use _resp_to_parsed to handle markdown wrapping and potential string returns from call_llm_with_retries
    refinement = _resp_to_parsed(refinement_raw)
    
    if not isinstance(refinement, dict) or "patch" not in refinement:
        logger.error(f"Refinement failed to produce valid JSON. Raw output preview: {str(refinement_raw)[:200]}")
        return {"error": "Refinement synthesis failed"}

    # 3. Apply Patch
    patch = refinement["patch"]
    
    def deep_merge(target, source):
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                deep_merge(target[key], value)
            else:
                target[key] = value
        return target

    updated_data = json.loads(json.dumps(current_data)) # Deep copy
    
    if "psychology" in patch and isinstance(patch["psychology"], dict):
        deep_merge(updated_data.setdefault("psychology", {}), patch["psychology"])
            
    if "biography" in patch and isinstance(patch["biography"], dict):
        deep_merge(updated_data.setdefault("biography", {}), patch["biography"])

    # Update database
    agent.agent_data = updated_data
    # Explicitly mark as modified for SQLAlchemy — required for JSONB to detect in-place dict reassignment
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(agent, "agent_data")
    await db.commit()

    logger.info(f"Agent {agent_id} has been refined: {refinement.get('reasoning')}")
    
    return {
        "status": "refined",
        "reasoning": refinement.get("reasoning"),
        "updated_sections": list(patch.keys())
    }
