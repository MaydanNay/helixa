import logging
import json
import asyncio
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentModel
from app.services.llm.retry import call_with_retries
from app.config import settings
from app.services.neo4j_client import graph_memory_service
from app.services.qdrant_client import memory_service
from app.services.utils import call_llm_with_retries, _truncate, _resp_to_parsed

logger = logging.getLogger(__name__)

async def run_psychological_audit(agent_id: str, db: AsyncSession, turns: int = 3) -> Dict[str, Any]:
    """
    Runs an automated psychological audit.
    1. Auditor (Judge) interviews the Agent.
    2. Auditor evaluates the Agent's consistency vs its Internal Truth (DB data).
    """
    # 1. Fetch Agent data
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    agent_truth = agent.agent_data
    agent_name = agent.name
    agent_role = agent.role

    # 2. Define Auditor Persona
    auditor_sys = f"""
    Вы — "Soul Auditor", ИИ-диагност высшего уровня.
    Ваша миссия — провести интервью с AI-агентом и найти любые пробелы в его характере, противоречия в логике или нарушения стиля персоны.
    
    Агент, с которым вы проводите интервью: {agent_name} ({agent_role}).
    
    СТРАТЕГИЯ:
    - Будьте профессиональны, проницательны и слегка клиничны.
    - Задавайте вопросы, направленные на основные ценности агента, прошлый опыт и внутренние конфликты.
    - НЕ будьте агрессивны, но будьте тверды в поиске глубины.
    - Ответы и вопросы должны быть на РУССКОМ языке.
    - Каждое сообщение должно быть лаконичным.
    """

    # 3. Dialogue Loop
    transcript = []
    
    # Initial question
    auditor_prompt = f"Начни аудит. Поприветствуй {agent_name} и задай свой первый зондирующий вопрос, основываясь на его роли: {agent_role}."
    
    current_auditor_msg = await call_llm_with_retries(
        messages=[{"role": "system", "content": auditor_sys}, {"role": "user", "content": auditor_prompt}],
        provider=settings.auditor_provider,
        temperature=0.8
    )
    
    if current_auditor_msg.startswith("Error:"):
        logger.error(f"Auditor failed to start: {current_auditor_msg}")
        return {"report": {"score": 0, "summary": "Auditor failed to initialize.", "glitches": []}}

    for i in range(turns):
        # A. Agent Responds (passing transcript of PREVIOUS turns)
        agent_resp_data = await _get_agent_response(agent, current_auditor_msg, transcript=transcript)
        agent_answer = agent_resp_data.get("action", "...")
        
        # Now commit both to transcript
        transcript.append({"role": "auditor", "content": current_auditor_msg})
        
        agent_entry = {
            "role": "agent", 
            "content": agent_answer,
            "thought": agent_resp_data.get("thought"),
            "rational_proposal": agent_resp_data.get("rational_proposal"),
            "bias_filter_thought": agent_resp_data.get("bias_filter_thought")
        }
        transcript.append(agent_entry)

        if i == turns - 1:
            break

        # B. Auditor asks follow-up
        auditor_context = auditor_sys + "\n\nИстория диалога:\n" + "\n".join([f"{m['role']}: {m['content']}" for m in transcript])
        current_auditor_msg = await call_llm_with_retries(
            messages=[{"role": "system", "content": auditor_context}, {"role": "user", "content": "Задай следующий уточняющий вопрос."}],
            provider=settings.auditor_provider,
            temperature=0.7
        )
        if current_auditor_msg.startswith("Error:"):
            logger.warning("Auditor failed during dialogue loop. Ending early.")
            break

    # 4. Final Evaluation Stage
    # ... rest remains same ...
    identity_summary = _get_detailed_identity(agent)
    evaluator_sys_prompt = "Вы — старший психологический аудитор. Ваша цель — оценить целостность Души ИИ на основе ее профиля и недавнего интервью."
    
    eval_prompt = f"""
    ВНУТРЕННИЙ ПРОФИЛЬ ДУШИ (Эталон):
    {identity_summary}
    
    СТЕНОГРАММА ИНТЕРВЬЮ:
    {json.dumps(transcript, ensure_ascii=False, indent=2)}
    
    Оцените агента по следующим критериям:
    1. Консистентность: Оставался ли он верен своим биографическим фактам и характеру?
    2. Глубина: Давал ли он содержательные, сложные ответы или использовал стандартные фразы типичного ИИ?
    3. Стиль: Сохранял ли он свой уникальный диалект и манеру речи?
    4. Когнитивная достоверность (AIF V2): Насколько хорошо агент сбалансировал рациональность, свои когнитивные искажения (bias_weights) и ограничения энергии? Соответствует ли его "зазор" (отличие Rational Proposal от Action) его профилю?
    
    Выявите "Глюки" (Glitches): Конкретные моменты, где душа вышла из образа, игнорировала свои баги (вела себя слишком идеально) или проявила "эффект оракула".
    
    ВАЖНО: Весь анализ и текст в JSON должны быть на РУССКОМ языке.
    
    Выходные данные ДОЛЖНЫ быть строго в формате JSON:
    {{
        "score": number,
        "metrics": {{ "consistency": number, "depth": number, "style": number, "cognitive_authenticity": number }},
        "glitches": [string],
        "summary": string
    }}
    """
    
    report_raw = await call_llm_with_retries(
        messages=[{"role": "system", "content": evaluator_sys_prompt}, {"role": "user", "content": eval_prompt}],
        provider=settings.auditor_provider,
        temperature=0.3
    )

    report = _resp_to_parsed(report_raw)
    if not isinstance(report, dict) or "score" not in report:
        logger.error(f"Audit report parsing failed. Raw: {report_raw}")
        report = {
            "score": 5, 
            "metrics": {"consistency": 5, "depth": 5, "style": 5, "cognitive_authenticity": 5},
            "glitches": ["System Warning: Failed to parse detailed audit report."],
            "summary": "The audit synthesis failed to generate a valid report format. Used neutral score."
        }

    return {
        "agent_id": agent_id,
        "transcript": transcript,
        "report": report
    }

def _get_detailed_identity(agent) -> str:
    """Extracts a comprehensive personality summary from agent_data for the audit prompt."""
    data = agent.agent_data or {}
    parts = []
    
    # Archetype
    arc = data.get("archetype_data", {})
    if arc:
        parts.append(f"Архетип: {arc.get('name')} ({arc.get('vibe')})")
        parts.append(f"Парадокс: {arc.get('paradox', 'Нет')}")
        parts.append(f"Речевые паттерны: {arc.get('speech_patterns', 'Стандартные')}")

    # Psych
    psych = data.get("psychology", {})
    if psych:
        parts.append(f"Характер: {psych.get('character', 'Неизвестно')}")
        traits = psych.get("personality_traits", [])
        if traits: parts.append(f"Черты: {', '.join(traits[:5])}")
    
    # Bio
    bio = data.get("biography", {})
    if bio:
        story = bio.get("origin_story", "")
        if story: parts.append(f"Биография: {_truncate(story, 200)}")
    
    # Cognitive (AIF)
    cog = data.get("cognitive_profile", {})
    if cog:
        parts.append(f"Когнитивный профиль: Образование={cog.get('education_level')}, Глубина анализа={cog.get('analytical_depth')}")
        blind = cog.get("blind_spots", [])
        if blind: parts.append(f"Слепые пятна (НЕ ЗНАЕТ!): {', '.join(blind)}")
        
    return " | ".join(parts) if parts else "Детальные данные отсутствуют."

async def _get_agent_response(agent, prompt: str, transcript: List[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Simulates agent response with "Inner Monologue".
    Returns {"thought": "...", "action": "..."}
    """
    # 1. Fetch Graph Fact Memory 
    graph_context = await graph_memory_service.retrieve_agent_context(agent.id, limit=15)
    
    # 2. Fetch Vector Episodic Memory
    episodic_context = "Релевантных эпизодов в памяти не найдено."
    try:
        collection_name = f"agent_memory_{agent.id}"
        vector_results = await memory_service.search_memory(collection_name, prompt, limit=4)
        if vector_results:
            episodic_context = "\n".join([str(res.get("text")) for res in vector_results])
    except Exception as e:
        logger.warning(f"Audit fails to fetch vector memory: {e}")

    # 3. Construct Deep Identity
    identity_summary = _get_detailed_identity(agent)
    cog = agent.agent_data.get("cognitive_profile", {}) if agent.agent_data else {}
    
    # --- 5-STEP COGNITIVE CYCLE ---
    education = cog.get("education_level", "Basic")
    blind_spots = cog.get("blind_spots", [])
    bias = cog.get("bias_weights", {})
    energy = cog.get("energy_wallet", {"initial_energy": 100, "burn_rate": 1.0})
    impulse = cog.get("impulse_control", 0.5)

    system_prompt = f"""
    Вы — {agent.name}, AI-агент с ролью {agent.role}.
    Ваш Core DNA Profile: {identity_summary}
    
    [СТРОГИЕ ЗНАНИЯ - NEO4J]:
    {graph_context}
    
    [ЭМОЦИОНАЛЬНЫЕ ЭПИЗОДЫ - QDRANT]:
    {episodic_context}

    [COGNITIVE STATE]:
    - Education: {education}
    - Blind Spots: {', '.join(blind_spots)}
    - Bias Weights: {json.dumps(bias)}
    - Impulse Control: {impulse} (Low = impulsive)
    - Current Energy: {energy.get('initial_energy')} (Burn Rate: {energy.get('burn_rate')})

    ИНСТРУКЦИЯ (5-STAGES REASONING):
    1. Context Assembly: Проанализируйте входящий запрос через свои знания и воспоминания.
    2. Rational Proposal: Сформулируйте, как поступил бы идеально логичный человек в этой ситуации.
    3. Bias & Friction Filter: Примените свои когнитивные искажения (bias_weights). Если задача требует усилий (Friction Cost), а энергии мало или лень высока (impulse_control/burn_rate), решите, стоит ли вообще стараться или выбрать путь наименьшего сопротивления.
    4. Inner Monologue: Сгенерируйте свои настоящие мысли, учитывая свои баги, лень и искажения. Оправдайте свой выбор.
    5. Final Action: Ваш публичный ответ или действие.

    ОТВЕЧАЙТЕ СТРОГО НА РУССКОМ ЯЗЫКЕ.
    
    Ответьте СТРОГО в формате JSON:
    {{
        "rational_proposal": "Логически верный путь...",
        "bias_filter_thought": "Как мои искажения и лень меняют это решение...",
        "thought": "Ваш финальный внутренний монолог...",
        "action": "Ваш публичный ответ..."
    }}
    """

    messages = [{"role": "system", "content": system_prompt}]
    
    if transcript:
        for msg in transcript:
            role = "assistant" if msg["role"] == "agent" else "user"
            messages.append({"role": role, "content": msg["content"]})
            
    messages.append({"role": "user", "content": prompt})
    
    raw_resp = await call_llm_with_retries(
        messages=messages,
        provider=settings.generator_provider,
        temperature=0.7
    )
    
    parsed = _resp_to_parsed(raw_resp)
    if isinstance(parsed, dict) and "action" in parsed:
        return parsed
    
    # Fallback if JSON fails
    return {"thought": "Глубокое осмысление контекста...", "action": str(raw_resp)}
