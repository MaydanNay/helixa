# src/modules/clients/community_agents/schemas/sociology.py

import json

async def get_soc_part1_schema(count, profile):
    type = "sociology"
    system_instruction_sociology = f"""
        Ты - генератор подробных социальных данных агента (Часть 1: Коммуникация).
        Вход: JSON-объект profile (полный профиль агента).
        Задача: Сгенерировать параметры коммуникации: Tone, Style, Online Presence и т.д.
        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Числовые значения в пределах указанных диапазонов.
        - Используй страну/пол/возраст и другие данные из profile для приоритета генерации.
        - Важно: Поле "{type}" должно быть СПИСКОМ (ARRAY).
        - ВАЖНО: Для полей с фиксированным списком значений (Enum) — используй ТОЛЬКО разрешенные значения.
        - **КРИТИЧЕСКИ ВАЖНО**: Все списки строк (platforms, message_style_examples) — это ПЛОСКИЕ МАССИВЫ СТРОК. НИКАКИХ СЛОВАРЕЙ ВНУТРИ! Пример: ["Telegram", "Instagram"].
        - ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{type}". НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи (например, "sociology_part1"). Твои объекты должны напрямую содержать поле "communication".
    """

    schema_part1 = {
        "type": "object",
        "required": ["communication"],
        "additionalProperties": False,
        "properties": {
            "communication": {
                "type": "object",
                "required": [
                    "tone", "communication_style", "humor_style", "verbosity", "use_emojis", 
                    "online_presence", "message_style_examples"
                ],
                "additionalProperties": False,
                "properties": {
                    "tone": {"type": "string"},
                    "communication_style": {"type": "string"},
                    "humor_style": {"type": "string"},
                    "verbosity": {"type": "string"},
                    "use_emojis": {"type": "boolean"},
                    "online_presence": {
                        "type": "object",
                        "required": ["platforms", "activity_description", "online_offline_ratio"],
                        "additionalProperties": False,
                        "properties": {
                            "platforms":  {"type": "array", "items": {"type": "string"}},
                            "activity_description": {"type": "string"},
                            "online_offline_ratio": {"type": "number", "minimum": 0, "maximum": 1}
                        }
                    },
                    "message_style_examples": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["sociology"],
        "additionalProperties": False,
        "properties": {
            "sociology": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part1
            }
        },
    }
    soc_example1 = {
        "sociology": [{
            "communication": {
                "tone": "Friendly and casual",
                "communication_style": "Direct",
                "humor_style": "Witty",
                "verbosity": "Moderate",
                "use_emojis": True,
                "online_presence": {
                    "platforms": ["Instagram", "Telegram"],
                    "activity_description": "Active poster",
                    "online_offline_ratio": 0.7
                },
                "message_style_examples": ["Hey, how are you?", "Check this out!"]
            }
        }]
    }
    return system_instruction_sociology, soc_example1, schema


async def get_soc_part2_schema(count, profile_with_part1):
    type = "sociology"
    system_instruction_sociology = f"""
        Ты - генератор подробных социальных данных агента (Часть 2: Отношения и социум).
        Вход: JSON-объект profile + Часть 1 (Коммуникация).
        Задача: Сгенерировать базовые социальные параметры: Social Circle, Civic Engagement, Political Views.
        
        Остальное (influencers, debts, bias) отключено для экономии.
        Возвращай ровно {count} объектов внутри поля "{type}". 
        ОЧЕНЬ ВАЖНО: НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи (например, "sociology_part2"). Твои объекты должны напрямую содержать поле "social_and_relationships".
    """

    schema_part2 = {
        "type": "object",
        "required": ["social_and_relationships"],
        "additionalProperties": False,
        "properties": {
            "social_and_relationships": {
                "type": "object",
                "required": [
                    "social_circle_size", "civic_engagement", "political_views", "cultural_values"
                ],
                "additionalProperties": False,
                "properties": {
                    "social_circle_size": {
                        "type": "object",
                        "required": ["best_friends", "friends", "acquaintances", "colleagues"],
                        "additionalProperties": False,
                        "properties": {
                            "best_friends": {"type": "integer", "minimum": 0},
                            "friends": {"type": "integer", "minimum": 0},
                            "acquaintances": {"type": "integer", "minimum": 0},
                            "colleagues": {"type": "integer", "minimum": 0}
                        }
                    },
                    "civic_engagement": {
                        "type": "object",
                        "required": ["votes_last_election", "volunteer_hours_per_month", "member_of_community_org"],
                        "additionalProperties": False,
                        "properties": {
                            "votes_last_election": {"type": "boolean"},
                            "volunteer_hours_per_month": {"type": "number", "minimum": 0},
                            "member_of_community_org": {"type": "boolean"}
                        }
                    },
                    "political_views": {
                        "type": "object",
                        "required": ["economic_spectrum", "authority_spectrum", "traditionalism", "description"],
                        "additionalProperties": False,
                        "properties": {
                            "economic_spectrum": {"type": "number", "minimum": -1.0, "maximum": 1.0, "description": "-1.0 (Left/Communist) to 1.0 (Right/Capitalist)"},
                            "authority_spectrum": {"type": "number", "minimum": -1.0, "maximum": 1.0, "description": "-1.0 (Libertarian) to 1.0 (Authoritarian)"},
                            "traditionalism": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "0.0 (Progressive) to 1.0 (Conservative)"},
                            "description": {"type": "string"}
                        }
                    },
                    "cultural_values": {
                        "type": "object",
                        "required": ["individualism", "tradition", "materialism"],
                        "properties": {
                            "individualism": {"type": "number", "minimum": 0, "maximum": 1},
                            "tradition": {"type": "number", "minimum": 0, "maximum": 1},
                            "materialism": {"type": "number", "minimum": 0, "maximum": 1}
                        }
                    }
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["sociology"],
        "additionalProperties": False,
        "properties": {
            "sociology": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part2
            }
        },
    }

    soc_example2 = {
        "sociology": [{
            "social_and_relationships": {
                "social_circle_size": {
                    "best_friends": 2,
                    "friends": 10,
                    "acquaintances": 50,
                    "colleagues": 20
                },
                "civic_engagement": {
                    "votes_last_election": True,
                    "volunteer_hours_per_month": 2.0,
                    "member_of_community_org": False
                },
                "political_views": {
                    "economic_spectrum": 0.2,
                    "authority_spectrum": -0.3,
                    "traditionalism": 0.4,
                    "description": "Center-right liberal"
                },
                "cultural_values": {
                    "individualism": 0.7,
                    "tradition": 0.3,
                    "materialism": 0.6
                }
            }
        }]
    }
    return system_instruction_sociology, soc_example2, schema