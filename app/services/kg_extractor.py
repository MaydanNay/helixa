import json
import logging
from typing import Dict, Any, Optional

from app.services.llm.retry import call_with_retries
from app.config import settings

logger = logging.getLogger(__name__)

KG_EXTRACTION_PROMPT = """
Ты — эксперт по извлечению информации в виде Графа Знаний (Knowledge Graph).
Твоя задача: проанализировать переданный текст (биографию или событие) и извлечь из него сущности и их отношения, чтобы наполнить базу данных симуляции мира.

Разрешенные типы узлов (nodes):
- AGENT (Люди, разумные существа)
- LOCATION (Города, здания, конкретные места)
- ORGANIZATION (Гильдии, компании, фракции)
- ITEM (Уникальные предметы, артефакты)
- GOAL (Цели, смыслы жизни)
- TRAIT (Черты характера, психологические особенности)
- VALUE (Моральные ценности, убеждения)
- EVENT (Ключевые события жизни, воспоминания)
- SKILL (Умения, профессиональные навыки, магические способности)
- FEAR (Страхи, фобии, триггеры)
- TITLE (Титулы, звания, социальный статус)

Разрешенные типы связей (edges):
- LIVES_IN (AGENT -> LOCATION)
- WORKS_AT (AGENT -> LOCATION / ORGANIZATION)
- KNOWS (AGENT -> AGENT)
- LIKES / DISLIKES / HATES (AGENT -> AGENT / ORGANIZATION)
- OWNS (AGENT -> ITEM)
- BELONGS_TO (AGENT -> ORGANIZATION)
- HAS_LIFE_GOAL (AGENT -> GOAL)
- HAS_TRAIT (AGENT -> TRAIT)
- CORE_VALUE (AGENT -> VALUE)
- PARTICIPATED_IN (AGENT -> EVENT)
- TRAUMATIZED_BY (AGENT -> EVENT / FEAR)
- MASTERS (AGENT -> SKILL)
- HAS_FEAR (AGENT -> FEAR)
- HAS_TITLE (AGENT -> TITLE)
- PARTNER_OF / CHILD_OF / PARENT_OF (AGENT -> AGENT)
- OWES_DEBT_TO (AGENT -> AGENT / ORGANIZATION)
- FEARS / TRUSTS (AGENT -> AGENT / ORGANIZATION)

Ответ должен быть строго в формате JSON, без маркдауна, содержащий два списка: "nodes" и "edges".
Пример правильного ответа:
{
  "nodes": [
    {"id": "Иван_Кузнец", "name": "Иван", "type": "AGENT"},
    {"id": "Город_Ветров", "name": "Город Ветров", "type": "LOCATION"},
    {"id": "Анна_Вор", "name": "Анна", "type": "AGENT"},
    {"id": "Гильдия_Воров", "name": "Гильдия Воров", "type": "ORGANIZATION"}
  ],
  "edges": [
    {"source": "Иван_Кузнец", "target": "Город_Ветров", "type": "LIVES_IN", "properties": {"description": "живет и работает"}},
    {"source": "Иван_Кузнец", "target": "Гильдия_Воров", "type": "HATES", "properties": {"reason": "убили брата"}},
    {"source": "Анна_Вор", "target": "Гильдия_Воров", "type": "BELONGS_TO", "properties": {"role": "член гильдии"}}
  ]
}

Важно:
1. Используй уникальные идентификаторы ('id') для узлов (без пробелов, например Имя_Фамилия или Имя_Роль), чтобы избежать слияния разных людей с одинаковым именем.
2. Поле 'name' - это удобочитаемое имя сущности для UI.
"""

KG_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["AGENT", "LOCATION", "ORGANIZATION", "ITEM", "GOAL", "TRAIT", "VALUE", "EVENT", "SKILL", "FEAR", "TITLE"]
                    }
                },
                "required": ["id", "name", "type"]
            }
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["LIVES_IN", "WORKS_AT", "KNOWS", "LIKES", "DISLIKES", "HATES", "OWNS", "BELONGS_TO", "HAS_LIFE_GOAL", "HAS_TRAIT", "CORE_VALUE", "PARTICIPATED_IN", "TRAUMATIZED_BY", "MASTERS", "HAS_FEAR", "HAS_TITLE", "PARTNER_OF", "CHILD_OF", "PARENT_OF", "OWES_DEBT_TO", "FEARS", "TRUSTS"]
                    },
                    "properties": {"type": "object"}
                },
                "required": ["source", "target", "type"]
            }
        }
    },
    "required": ["nodes", "edges"]
}

async def extract_knowledge_graph(text: str, agent_id: str = None, agent_name: str = None, provider: str = settings.generator_provider) -> Dict[str, Any]:
    """
    Takes arbitrary text (e.g. backstory) and returns a structured JSON representing
    the nodes and edges to be inserted into Neo4j.
    """
    logger.info("Extracting Knowledge Graph from text...")
    
    system_prompt = KG_EXTRACTION_PROMPT
    if agent_id and agent_name:
        system_prompt += f"\n\nСВЕРХВАЖНО: Главный герой этого текста — '{agent_name}'. Везде (и в узлах, и в связях), где речь идет об этом герое, ты ОБЯЗАН использовать ID '{agent_id}' вместо его имени. Для остальных персонажей используй их имена как ID."

    user_prompt = f"Текст для анализа:\n{text}\n\nПожалуйста, извлеки граф в формате JSON."
    
    try:
        from app.services.utils import _resp_to_parsed, extract_stage
        resp = await call_with_retries(
            sys_inst=system_prompt,
            u_prompt=user_prompt,
            w_schema=KG_SCHEMA,
            wrapper_name="knowledge_graph",
            attempts=3,
            timeout=120,
            provider=provider
        )
        # Ensure we get a dict with nodes/edges
        parsed_obj = _resp_to_parsed(resp)
        kg_data = extract_stage(parsed_obj, "knowledge_graph")
        
        if isinstance(kg_data, dict) and "nodes" in kg_data and "edges" in kg_data:
            return kg_data
        
        logger.warning(f"KG Extractor produced invalid structure for agent {agent_id}. Raw: {str(resp)[:1000]}")
        return {"nodes": [], "edges": []}
    except Exception as e:
        logger.error(f"Failed to extract knowledge graph: {e}")
        return {"nodes": [], "edges": []}
