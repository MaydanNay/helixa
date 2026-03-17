# src/modules/clients/community_agents/schemas/relationships.py

def get_relationship_context_schema(count):
    type_name = "relationship_context"
    system_instruction = f"""
    Ты - биограф социальных связей. Твоя задача - описать детали отношений между двумя людьми.
    Контекст: [Agent A] знает [Agent B]. Тип связи: {{relation_type}}.
    
    Опиши:
    - **Opinion Matrix (0.0 - 1.0):** trust, romantic_interest, professional_respect, jealousy, fear, envy.
    - **Общая история:** Где познакомились, что пережили. Создай 1-3 события (history_events).
    - **Темы:** О чем они обычно говорят.
    
    ВАЖНО: history_events - это события, о которых ДРУГИЕ агенты могут узнать (сплетни).
    Если is_secret=true, только они двое знают об этом.
    
    Верни JSON объект с полем "{type_name}".
    """

    schema_item = {
        "type": "object",
        "required": ["trust_level", "romantic_interest", "professional_respect", "jealousy", "fear", "envy", "shared_history_summary", "history_events", "common_topics"],
        "additionalProperties": False,
        "properties": {
            "trust_level": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "How much Agent A trusts Agent B. 0.0=Enemy, 1.0=Ride or die."
            },
            "romantic_interest": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0.0=Platonic, 1.0=Madly in love."
            },
            "professional_respect": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0.0=Thinks they are incompetent, 1.0=Admires skills."
            },
            "jealousy": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0.0=No jealousy, 1.0=Consumed by jealousy."
            },
            "fear": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0.0=No fear, 1.0=Terrified of this person."
            },
            "envy": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0.0=No envy, 1.0=Wants what they have."
            },
            "shared_history_summary": {
                "type": "string",
                "description": "1-2 sentences describing how they met or a significant shared event."
            },
            "history_events": {
                "type": "array",
                "description": "List of shared events that can be queried by other agents (gossip fabric).",
                "items": {
                    "type": "object",
                    "required": ["date", "event", "emotional_impact", "is_secret"],
                    "properties": {
                        "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "event": {"type": "string", "description": "What happened between them."},
                        "emotional_impact": {"type": "string", "enum": ["positive", "negative", "neutral", "traumatic", "euphoric"]},
                        "is_secret": {"type": "boolean", "description": "If true, only they know about it."}
                    }
                }
            },
            "common_topics": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 5,
                "description": "Topics they often discuss (e.g. 'Fishing', 'Politics', 'Ex-girlfriends')."
            }
        }
    }

    schema = {
        "type": "object",
        "required": [type_name],
        "additionalProperties": False,
        "properties": {
            type_name: {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_item
            }
        }
    }

    example = {
        type_name: [
            {
                "trust_level": 0.9,
                "romantic_interest": 0.1,
                "professional_respect": 0.5,
                "jealousy": 0.2,
                "fear": 0.0,
                "envy": 0.3,
                "shared_history_summary": "They served in the army together in 2018 and saved each other from trouble.",
                "history_events": [
                    {"date": "2018-06-15", "event": "Survived ambush together", "emotional_impact": "traumatic", "is_secret": False},
                    {"date": "2019-01-01", "event": "Got drunk and confessed secrets", "emotional_impact": "positive", "is_secret": True}
                ],
                "common_topics": ["Military days", "Cars", "Survival tech"]
            }
        ]
    }

    return system_instruction, example, schema
