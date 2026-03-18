import json

async def get_behavioral_main_schema(count, profile_context):
    type = "behavioral_main"
    system_instruction = f"""
        Ты - генератор основных поведенческих паттернов.
        Вход: Full Profile.
        Задача: Сгенерировать поведенческие паттерны.
        Возвращай ровно {count} объектов внутри поля "{type}".
    """

    schema = {
        "type": "object",
        "required": [],  # Все поля опциональны — LLM часто пропускает некоторые
        "additionalProperties": True,  # Разрешаем дополнительные поля от LLM
        "properties": {
            # Основные поля (желательные, но не обязательные)
            "typical_response_style": {"type": "string"},  # Убрали enum — LLM часто пишет свободный текст
            "engagement_times": {
                "type": "array",
                "items": {"type": "object", "properties": {"from": {"type": "string"}, "to": {"type": "string"}}}
            },
            "response_latency_seconds_median": {"type": ["integer", "number"]},
            "engagement_rate": {"type": "number"},
            "drivers_of_decision": {"type": "array", "items": {"type": "string"}},
            "external_factors": {"type": "array", "items": {"type": "string"}},
            "persuasion_triggers": {"type": "array", "items": {"type": "string"}},
            "ongoing_needs": {"type": ["string", "array"]},  # LLM иногда возвращает массив
            "decision_time_days": {"type": ["integer", "number"]},
            "brand_loyalty": {"type": "string"},
            "trust_level": {"type": ["number", "string"]},
            "tech_savviness": {"type": "string"},
            "responsiveness": {"type": "string"},
            "peak_contact_hours": {"type": "array", "items": {"type": ["integer", "string"]}},
            # MiroFish Harvest: Social Media Physicality
            "social_media_activity": {
                "type": "object",
                "properties": {
                    "posts_per_hour": {"type": "number", "description": "Average frequency of original posts."},
                    "comments_per_hour": {"type": "number", "description": "Average frequency of comments/replies."},
                    "influence_weight": {"type": "number", "description": "How much this agent's actions sway others (0.1-5.0)."},
                    "stance_bias": {"type": "string", "enum": ["supportive", "opposing", "neutral", "observer"]}
                }
            },
            # Дополнительные поля, которые LLM может вернуть
            "pattern_name": {"type": "string"},
            "description": {"type": "string"},
            "key_traits": {"type": "array", "items": {"type": "string"}},
            "typical_behaviors": {"type": "array", "items": {"type": "string"}},
            # "motivations": REMOVED (Redundant with core_psychology)
            "potential_challenges": {"type": "array", "items": {"type": "string"}}
        }
    }

    wrapper_schema = {
        "type": "object",
        "required": [type],
        "properties": {
            type: {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema
            }
        }
    }
    
    return system_instruction, {}, wrapper_schema
