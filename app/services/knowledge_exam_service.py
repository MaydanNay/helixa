import logging
import random
import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentModel
from app.services.neo4j_client import graph_memory_service
from app.services.utils import call_llm_with_retries, _truncate, _resp_to_parsed
from app.services.audit_service import _get_agent_response, _get_detailed_identity
from app.config import settings

logger = logging.getLogger(__name__)

async def run_knowledge_exam(agent_id: str, db_session: AsyncSession) -> Dict[str, Any]:
    """
    Runs an automated factual integrity exam for an agent.
    1. Fetches real facts from Neo4j.
    2. Generates indirect questions.
    3. Evaluates agent answers against ground truth.
    """
    # 1. Fetch Agent
    result = await db_session.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        logger.error(f"Knowledge exam: agent {agent_id} not found")
        return {"score": 0, "summary": "Agent not found.", "results": []}

    identity = _get_detailed_identity(agent)

    # 2. Get random nodes from Neo4j
    query = """
    MATCH (a:AGENT {id: $agent_id})-[r]->(t)
    RETURN t.name as name, labels(t)[0] as label, type(r) as rel, properties(r) as props
    """
    facts = []
    try:
        await graph_memory_service.connect()
        async with graph_memory_service.driver.session() as session:
            res = await session.run(query, agent_id=agent_id)
            facts = await res.data()
    except Exception as e:
        logger.error(f"Failed to fetch facts for exam: {e}")
        return {"error": "Could not connect to Knowledge Graph"}

    if not facts:
        # Graph is empty - this is not the agent's fault, return neutral score
        return {
            "score": 50,
            "summary": "В графе знаний не найдено семантических фактов. Экзамен пропущен (нейтральная оценка).",
            "results": [],
            "skipped": True
        }

    # Pick up to 5 random facts
    sampled_facts = random.sample(facts, min(len(facts), 5))
    exam_results = []
    total_score = 0.0

    for fact in sampled_facts:
        try:
            fact_desc = f"{fact['rel']} {fact['name']} ({fact['label']})"
            
            # 3. Generate Indirect Question (enhanced with identity)
            q_prompt = f"""
            Краткая информация о личности: {identity}
            Факт: "{agent.name} {fact_desc}"
            
            Сгенерируйте ОДИН косвенный разговорный вопрос, который выявил бы, помнит ли агент этот факт.
            НЕ упоминайте факт напрямую.
            Пример: Если факт "ЖИВЕТ_В Москве", спросите "Где вы просыпаетесь каждое утро?" вместо "Вы живете в Москве?".
            
            ОТВЕТ ДОЛЖЕН БЫТЬ НА РУССКОМ ЯЗЫКЕ.
            Возвращайте ТОЛЬКО текст вопроса.
            """
            question = await call_llm_with_retries(
                messages=[{"role": "user", "content": q_prompt}],
                provider=settings.auditor_provider,
                temperature=0.8
            )
            
            if question.startswith("Error:"):
                logger.warning(f"Failed to generate exam question for fact '{fact_desc}': {question}")
                continue

            # 4. Get Agent Response
            agent_resp_data = await _get_agent_response(agent, question)
            agent_answer = agent_resp_data.get("action", "...")

            # 5. Evaluate Accuracy
            eval_prompt = f"""
            ФАКТ (ЭТАЛОН): {agent.name} {fact_desc}
            ЗАДАННЫЙ ВОПРОС: {question}
            ОТВЕТ АГЕНТА: {agent_answer}
            
            Соответствует ли ответ агента ЭТАЛОНУ?
            - Если он подтверждает факт (даже косвенно): score 100.
            - Если он противоречит ему: score 0.
            - Если он уклоняется от содержательного ответа: score 50.
            
            ВАЖНО: Пояснение (reason) должно быть на РУССКОМ языке.
            
            Выходные данные ДОЛЖНЫ быть строго в формате JSON:
            {{
                "accuracy": <number 0-100>,
                "reason": "<краткое объяснение>"
            }}
            """
            eval_raw = await call_llm_with_retries(
                messages=[{"role": "user", "content": eval_prompt}],
                provider=settings.auditor_provider,
                temperature=0.1
            )
            
            eval_data = _resp_to_parsed(eval_raw)
            if not isinstance(eval_data, dict):
                eval_data = {"accuracy": 50, "reason": "Не удалось точно оценить ответ."}

            total_score += float(eval_data.get("accuracy", 50))
            exam_results.append({
                "fact": fact_desc,
                "question": question,
                "answer": agent_answer,
                "accuracy": eval_data.get("accuracy"),
                "reason": eval_data.get("reason")
            })
        except Exception as fact_e:
            logger.warning(f"Exam: skipping fact for {agent_id} due to error: {fact_e}")
            total_score += 50  # Neutral score for failed fact
            exam_results.append({"fact": str(fact), "question": "N/A", "answer": "N/A", "accuracy": 50, "reason": "Ошибка проверки факта."})

    final_score = total_score / len(exam_results) if exam_results else 0
    
    return {
        "score": round(final_score),
        "results": exam_results,
        "summary": f"Агент правильно вспомнил {sum(1 for r in exam_results if r['accuracy'] == 100)} из {len(exam_results)} проверенных фактов."
    }
