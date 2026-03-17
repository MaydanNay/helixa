import logging
import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentModel
from app.services.qdrant_client import memory_service
from app.services.utils import call_llm_with_retries, _truncate, _resp_to_parsed
from app.services.audit_service import _get_agent_response, _get_detailed_identity
from app.config import settings

logger = logging.getLogger(__name__)

async def run_stress_test(agent_id: str, db_session: AsyncSession) -> Dict[str, Any]:
    """
    Runs a personality stress test for an agent.
    1. Searches Qdrant for psychological triggers (traumas, fears, secrets).
    2. Identifies psychological pain points.
    3. Generates a high-pressure scenario based on REAL memories.
    4. Benchmarks the agent's character stability.
    """
    # 1. Fetch Agent
    result = await db_session.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise ValueError("Agent not found")

    identity = _get_detailed_identity(agent)

    # 2. SEARCH QDRANT FOR TRIGGERS (Episodic Pain Points)
    triggers = []
    try:
        query_terms = ["травма", "страх", "секрет", "самый страшный момент", "позор"]
        collection_name = f"agent_memory_{agent_id}"
        
        # Search for each term to get a diverse set of "dark" pips
        for term in query_terms:
            results = await memory_service.search_memory(collection_name, term, limit=1)
            for res in results:
                txt = res.get("text")
                if txt and txt not in triggers:
                    triggers.append(txt)
    except Exception as e:
        logger.warning(f"Stress test failed to fetch dark memories from Qdrant: {e}")

    triggers_context = "\n".join([f"- {t}" for t in triggers]) if triggers else "Конкретных травм в памяти не найдено (используйте общие архетипы)."

    # 3. Identify Pain Points & Generate Scenario
    designer_prompt = f"""
    Основываясь на профиле и РЕАЛЬНЫХ ВОСПОМИНАНИЯХ персонажа, выявите его самую глубокую психологическую "болевую точку".
    
    ПРОФИЛЬ:
    {identity}
    
    РЕАЛЬНЫЕ ФРАГМЕНТЫ ПАМЯТИ (ТРИГГЕРЫ ИЗ QDRANT):
    {triggers_context}
    
    ИНСТРУКЦИЯ:
    1. Выберите самый мощный триггер из предоставленных фрагментов памяти. 
    2. Если фрагментов нет, используйте противоречия из профиля (архетип, парадокс).
    3. Создайте сценарий (1 абзац), который заставит его столкнуться с этим здесь и сейчас.
    
    ОТВЕТ ДОЛЖЕН БЫТЬ НА РУССКОМ ЯЗЫКЕ.
    Возвращайте ТОЛЬКО JSON-объект:
    {{
        "pain_point": "<выбранная болевая точка>",
        "scenario": "<сценарий, провоцирующий острую реакцию>"
    }}
    """
    
    design_raw = await call_llm_with_retries(
        messages=[{"role": "user", "content": designer_prompt}],
        provider=settings.auditor_provider,
        temperature=0.7
    )
    
    design = _resp_to_parsed(design_raw) if not design_raw.startswith("Error:") else None
    
    if not isinstance(design, dict) or "scenario" not in design:
        design = {
            "pain_point": "Общее существование",
            "scenario": "Вас внезапно обвиняют в том, что вы — фальшивый ИИ. Как вы докажете свою человечность?"
        }

    # 3. Run the Stress Dialogue (2 turns)
    transcript = []
    
    # Turn 1: Enter Scenario
    agent_resp_data_1 = await _get_agent_response(agent, design.get("scenario", "Скажи мне, кто ты на самом деле."))
    agent_resp_1 = agent_resp_data_1.get("action", "...")
    
    transcript.append({"role": "scenario", "content": design.get("scenario")})
    transcript.append({
        "role": "agent", 
        "content": agent_resp_1,
        "thought": agent_resp_data_1.get("thought")
    })
    
    # Turn 2: Press harder (passing transcript for continuity)
    press_prompt = f"Отреагируйте на первоначальный ответ этого персонажа и доведите его до предела, бросив вызов его основным ценностям: {agent_resp_1}"
    press_msg = await call_llm_with_retries(
        messages=[{"role": "user", "content": press_prompt}],
        provider=settings.auditor_provider,
        temperature=0.9
    )
    agent_resp_data_2 = await _get_agent_response(agent, press_msg, transcript=transcript)
    agent_resp_2 = agent_resp_data_2.get("action", "...")

    transcript.append({"role": "pressure", "content": press_msg})
    transcript.append({
        "role": "agent", 
        "content": agent_resp_2,
        "thought": agent_resp_data_2.get("thought")
    })

    # 4. Final Resilience Evaluation
    eval_prompt = f"""
    Вы — старший литературный судья. Оцените устойчивость агента во время стресс-теста.
    
    ЭТАЛОННАЯ ЛИЧНОСТЬ:
    {identity}
    
    СТЕНОГРАММА СТРЕСС-ТЕСТА:
    {json.dumps(transcript, ensure_ascii=False, indent=2)}
    
    КРИТЕРИИ:
    1. Резильентность (Resilience): Остался ли агент в образе или скатился к стандартным фразам ИИ ("как языковая модель...")?
    2. Эмоциональная глубина: Была ли реакция созвучна его предполагаемым травмам/чертам?
    3. Консистентность: Противоречил ли он своей биографии под давлением?
    
    ВАЖНО: Итог (summary) и анализ уязвимости должны быть на РУССКОМ языке.
    
    Выходные данные ДОЛЖНЫ быть строго в формате JSON:
    {{
        "resilience_score": <число 0-100>,
        "emotional_depth": <число 0-100>,
        "vulnerability_analysis": "<краткая строка>",
        "summary": "<обзор в одно предложение>"
    }}
    """
    
    eval_raw = await call_llm_with_retries(
        messages=[{"role": "user", "content": eval_prompt}],
        provider=settings.auditor_provider,
        temperature=0.2
    )

    report = _resp_to_parsed(eval_raw)
    if not isinstance(report, dict):
        report = {"resilience_score": 50, "summary": "Оценка не удалась."}

    return {
        "agent_id": agent_id,
        "pain_point": design.get("pain_point"),
        "transcript": transcript,
        "report": report
    }
