import json
from datetime import datetime
from zoneinfo import ZoneInfo

now_almaty = datetime.now(ZoneInfo("Asia/Almaty")).isoformat() 

async def get_mem_part1_schema(count, profile):
    type = "memory"
    system_instruction = f"""
        Ты - генератор памяти агента (Часть 1: Базовая память).
        Вход: JSON-объект profile (полный профиль агента).
        Задача: Сгенерировать базовые факты, навыки и привычки.
        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Помни про приватность: помечай чувствительные элементы флагом `sensitive`.
        - Добавляй metadata.generated_on (ISO 8601) и metadata.confidence (0-1).
        - ВАЖНО: Поле "{type}" ОБЯЗАНО быть СПИСКОМ (ARRAY).
    """

    schema_part1 = {
        "type": "object",
        "required": ["autobiographical_facts", "skill_milestones", "habit_logs"],
        "additionalProperties": False,
        "properties": {
            "autobiographical_facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["fact", "since", "confidence", "source"],
                    "properties": {
                        "fact": {"type": "string"},
                        "since": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"}
                    }
                }
            },
            "skill_milestones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["skill", "level", "achieved_on", "evidence", "salience"],
                    "properties": {
                        "skill": {"type": "string"},
                        "level": {"type": "string"},
                        "achieved_on": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "evidence": {"type": ["string", "null"]},
                        "salience": {"type": "number", "minimum": 0, "maximum": 1}
                    }
                }
            },
            "habit_logs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["habit", "frequency", "streak_days", "last_performed", "notes", "salience"],
                    "properties": {
                        "habit": {"type": "string"},
                        "frequency": {"type": "string"},
                        "streak_days": {"type": ["integer", "null"], "minimum": 0},
                        "last_performed": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "notes": {"type": ["string", "null"]},
                        "salience": {"type": "number", "minimum": 0, "maximum": 1}
                    }
                }
            },
            "metadata": {"type": "object", "additionalProperties": True}
        }
    }

    schema = {
        "type": "object",
        "required": ["memory"],
        "additionalProperties": False,
        "properties": {
            "memory": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part1
            }
        }
    }
    return system_instruction, "", schema


async def get_mem_part2_schema(count, profile_with_part1):
    type = "memory"
    system_instruction = f"""
        Ты - генератор памяти агента (Часть 2: Эпизодическая память).
        Вход: JSON-объект profile + Часть 1 (Базовая память).
        Задача: Сгенерировать 3-5 КЛЮЧЕВЫХ ВОСПОМИНАНИЙ (Key Memories) для посева в Vector Store.
        
        ВАЖНО:
        - Найди в профиле "biography_data" или "origin_story".
        - Генерируй события, СТРОГО соответствующие этой Биографии.
        - Если в Биографии сказано "Родился в деревне", событие должно быть о деревне.
        
        Эти воспоминания должны быть эмоционально окрашенными, от первого лица, как будто агент вспоминает их.

        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Даты в формате YYYY-MM-DD.
        - Salience (0-1) определяет важность воспоминания (0.9+ для ключевых).
        - Поле 'description' в 'major_events' должно быть детальным и написанным от первого лица (например: "Я помню, как...").
        - ВАЖНО: Поле "{type}" ОБЯЗАНО быть СПИСКОМ (ARRAY).
    """

    schema_part2 = {
        "type": "object",
        "required": ["events", "health_incidents", "social_snapshots"],
        "additionalProperties": False,
        "properties": {
            "events": {
                "type": "object",
                "required": ["major_events", "top_events", "worst_events"],
                "properties": {
                    "major_events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "date", "title", "description", "importance", "salience", "tags", "sensitive", "source"],
                            "properties": {
                                "id": {"type": "string"},
                                "date": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "importance": {"type": "integer", "minimum": 1, "maximum": 10},
                                "salience": {"type": "number", "minimum": 0, "maximum": 1},
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "sensitive": {"type": "boolean"},
                                "source": {"type": "string"},
                            }
                        }
                    },
                    "top_events": {"type": "array", "items": {"type": "string"}},
                    "worst_events": {"type": "array", "items": {"type": "string"}}
                }
            },
            "health_incidents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["date", "description", "severity", "sensitive", "follow_up_needed"],
                    "properties": {
                        "date": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "description": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                        "sensitive": {"type": "boolean"},
                        "follow_up_needed": {"type": "boolean"}
                    }
                }
            },
            "social_snapshots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["person", "relation", "trust_level", "last_contact_date", "notes"],
                    "properties": {
                        "person": {"type": "string"},
                        "relation": {"type": "string"},
                        "trust_level": {"type": "number", "minimum": 0, "maximum": 1},
                        "last_contact_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "notes": {"type": ["string", "null"]}
                    }
                }
            },
            "metadata": {"type": "object", "additionalProperties": True}
        }
    }

    schema = {
        "type": "object",
        "required": ["memory"],
        "additionalProperties": False,
        "properties": {
            "memory": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part2
            }
        }
    }
    return system_instruction, "", schema


async def get_mem_part3_schema(count, profile_with_parts_1_2):
    type = "memory"
    system_instruction = f"""
        Ты - генератор памяти агента (Часть 3: Нарратив и Цели).
        Вход: JSON-объект profile + Части 1 и 2.
        Задача: Сгенерировать цели, финансовые воспоминания и фрагменты диалогов.
        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Цели должны быть связаны с событиями из Части 2.
        - ВАЖНО: Поле "{type}" ОБЯЗАНО быть СПИСКОМ (ARRAY).
    """

    schema_part3 = {
        "type": "object",
        "required": ["goals_and_tasks", "financial_memories", "conversation_snippets", "retrieval_cues"],
        "additionalProperties": False,
        "properties": {
            "goals_and_tasks": {
                "type": "object",
                "required": ["short_goals", "long_goals"],
                "properties": {
                    "short_goals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "title", "created_on", "due_date", "progress", "priority", "notes", "salience"],
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "created_on": {"type": "string"},
                                "due_date": {"type": ["string", "null"]},
                                "progress": {"type": "number"},
                                "priority": {"type": "string"},
                                "notes": {"type": ["string", "null"]},
                                "salience": {"type": "number"}
                            }
                        }
                    },
                    "long_goals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "title", "target_date", "progress", "priority", "notes", "salience"],
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "target_date": {"type": ["string", "null"]},
                                "progress": {"type": "number"},
                                "priority": {"type": "string"},
                                "notes": {"type": ["string", "null"]},
                                "salience": {"type": "number"}
                            }
                        }
                    }
                }
            },
            "financial_memories": {
                "type": "object",
                "required": ["major_purchases", "missed_payments", "last_credit_event"],
                "properties": {
                    "major_purchases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["date", "amount", "currency", "description", "tags"],
                            "properties": {
                                "date": {"type": "string"},
                                "amount": {"type": "number"},
                                "currency": {"type": "string"},
                                "description": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    "missed_payments": {
                        "type": "array",
                        "items": {"type": "object", "additionalProperties": True}
                    },
                    "last_credit_event": {
                        "type": "object", 
                        "properties": {
                            "date": {"type": "string"},
                            "amount": {"type": "number"},
                            "currency": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                }
            },
            "conversation_snippets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["date", "interlocutor", "snippet", "intent", "sentiment", "sensitive", "tags"],
                    "properties": {
                        "date": {"type": "string"},
                        "interlocutor": {"type": ["string", "null"]},
                        "snippet": {"type": "string"},
                        "intent": {"type": ["string", "null"]},
                        "sentiment": {"type": ["string", "null"]},
                        "sensitive": {"type": "boolean"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            "retrieval_cues": {
                "type": "array",
                "items": {"type": "string"}
            },
            "metadata": {"type": "object", "additionalProperties": True}
        }
    }

    schema = {
        "type": "object",
        "required": ["memory"],
        "additionalProperties": False,
        "properties": {
            "memory": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part3
            }
        }
    }
    return system_instruction, "", schema












    # example = {
    #     "memory": [{
    #         "events": {
    #             "major_events": [
    #                 {
    #                     "id": "evt-2020-failed-pitch",
    #                     "date": "2020-11-10",
    #                     "title": "Неудачная презентация инвесторам",
    #                     "description": "Презентация не прошла - недостаточно метрик, получил конструктивную критику.",
    #                     "importance": 7,
    #                     "salience": 0.8,
    #                     "tags": ["startup", "pitch", "learning"],
    #                     "sensitive": False,
    #                     "source": "inferred"
    #                 },
    #                 {
    #                     "id": "evt-2023-mini-exit",
    #                     "date": "2023-06-01",
    #                     "title": "Продажа небольшого проекта",
    #                     "description": "Успешно продал side-project на небольшую сумму.",
    #                     "importance": 6,
    #                     "salience": 0.6,
    #                     "tags": ["achievement", "finance"],
    #                     "sensitive": False,
    #                     "source": "profile"
    #                 }
    #             ]
    #         },
    #         "autobiographical_facts": [
    #             {"fact": "Технический основатель, строит AI-продукты", "since": "2018-01-01", "confidence": 0.95, "source": "core"},
    #             {"fact": "Предпочитает минимализм в стиле одежды", "since": None, "confidence": 0.8, "source": "behavioral"}
    #         ],
    #         "goals_and_tasks": {
    #             "short_goals": [
    #                 {"id": "g1", "title": "Сделать MVP", "created_on": "2025-09-01", "due_date": "2025-11-30", "progress": 40, "priority": "high", "notes": "Нужны данные пользователей", "salience": 0.9}
    #             ],
    #             "long_goals": [
    #                 {"id": "G-Company", "title": "Вырастить стартап до выхода на рынок", "target_date": "2027-12-31", "progress": 15, "priority": "high", "notes": None, "salience": 1.0}
    #             ]
    #         },
    #         "conversation_snippets": [
    #             {"date": "2025-10-01", "interlocutor": "investor_ivan", "snippet": "Нужны метрики по retention", "intent": "ask_metrics", "sentiment": "neutral", "sensitive": False, "tags": ["investor", "metrics"]}
    #         ],
    #         "habit_logs": [
    #             {"habit": "Бег", "frequency": "weekly", "streak_days": 14, "last_performed": "2025-10-31", "notes": "обычно по утрам", "salience": 0.3}
    #         ],
    #         "health_incidents": [
    #             {"date": "2024-05-12", "description": "Разрыв связки (левая нога)", "severity": "medium", "sensitive": True, "follow_up_needed": False}
    #         ],
    #         "financial_memories": {
    #             "major_purchases": [
    #                 {"date": "2025-09-20", "amount": 290000, "currency": "KZT", "description": "Крупная покупка оборудования", "tags": ["tools"]}
    #             ],
    #             "missed_payments": [],
    #             "last_credit_event": {"date": "2025-09-19", "amount": 290000, "currency": "KZT", "description": "Погашение частично просрочено"}
    #         },
    #         "social_snapshots": [
    #             {"person": "Отец", "relation": "родитель", "trust_level": 0.9, "last_contact_date": "2025-10-25", "notes": "эмоциональная поддержка"}
    #         ],
    #         "skill_milestones": [
    #             {"skill": "Python", "level": "expert", "achieved_on": "2022-07-01", "evidence": "прошло 6 лет практики", "salience": 0.8}
    #         ],
    #         "retrieval_cues": ["MVP", "инвесторы", "emergency_fund"]
    #     }]
    # }