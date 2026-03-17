# src/modules/clients/community_agents/schemas/experience.py

import json

async def get_experience_schema(count, profile):
    type = "experience"
    system_instruction_experience = f"""
        Ты - генератор подробных данных об опыте агента.
        Вход: JSON-объект profile (полный профиль агента), который нужно проанализировать.
        Задача: на основе profile сгенерировать ТОЛЬКО JSON-объект(ы) соответствующие схеме {type}.
        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Числовые значения в пределах указанных диапазонов.
        - Используй страну/пол/возраст и другие данные из profile для приоритета генерации {type}.
        - Поддерживай согласованность данных
        - ВАЖНО: Для полей с фиксированным списком значений (Enum) — используй ТОЛЬКО разрешенные значения.
        - **КРИТИЧЕСКИ ВАЖНО**: Все списки строк (expertise, hard_skills, soft_skills, tools_used_by) — это ПЛОСКИЕ МАССИВЫ СТРОК. НИКАКИХ СЛОВАРЕЙ ВНУТРИ! Пример: ["skill1", "skill2"].
        - **КРИТИЧЕСКИ ВАЖНО**: Все списки объектов (languages, skills, certifications, occupation_history) — это СТРОГИЕ МАССИВЫ ОБЪЕКТОВ.
        - СТРОГИЙ ЗАПРЕТ: НЕ создавай ключ "tools"! Используй ТОЛЬКО разрешенный ключ "tools_used_by" внутри capabilities.
        - ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{type}". НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи (например, "experience"). Твои объекты должны напрямую содержать поля "expertise", "capabilities" и т.д.
        - Если не хватает информации, делай реалистичные предположения и помечай их в поле `inference_notes`.

        profile:\n {json.dumps(profile, ensure_ascii=False)}
    """
    
    experience_schema = {
        "type": "object",
        "required": ["expertise", "capabilities", "employment", "typical_active_hours"],
        "additionalProperties": False,
        "properties": {
            # Экспертиза
            "expertise": {"type": "array", "items": {"type": "string"}},

            # Возможности
            "capabilities": {
                "type": "object",
                "required": ["intelligence", "languages", "skills", "hard_skills", "soft_skills", "tools_used_by", "certifications", "availability", "inference_notes"],
                "additionalProperties": False,
                "properties": {
                    # Интеллект
                    "intelligence": {
                        "type": "object",
                        "required": ["score", "category", "profile"],
                        "additionalProperties": False,
                        "properties": {
                            # Оценка
                            "score": {"type": "number", "minimum": 0, "maximum": 100},
                            # Категория
                            "category": {"type": "string", "enum": ["very_low", "low", "below_average", "average", "above_average", "high", "very_high"]},
                            # Профиль
                            "profile": {"type": "array", "items": {"type": "string"}}
                        }
                    },

                    # Языки
                    "languages": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["language", "proficiency"],
                            "additionalProperties": False,
                            "properties": {
                                # Язык
                                "language": {"type": "string"},
                                # Профессионализм
                                "proficiency": {"type": "string", "enum": ["native", "fluent", "professional", "advanced", "intermediate", "basic"]}
                            }
                        },
                    },

                    # Нывыки
                    "skills": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["title", "category", "level", "years"],
                            "additionalProperties": False,
                            "properties": {
                                # Название
                                "title": {"type": "string"},
                                # Категория
                                "category": {"type": "string"},
                                # Уровень
                                "level": {"type": "string", "enum": ["novice", "intermediate", "advanced", "expert"]},
                                # Лет
                                "years": {"type": "integer", "minimum": 0}
                            }
                        }
                    },

                    # Твердые навыки
                    "hard_skills": {"type": "array", "items": {"type": "string"}},

                    # Мягкие навыки
                    "soft_skills": {"type": "array", "items": {"type": "string"}},

                    # Используемые инструменты
                    "tools_used_by": {"type": "array", "items": {"type": "string"}},

                    # Сертификаты
                    "certifications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["title", "issuer", "year"], 
                            "properties": {
                                # Название
                                "title": {"type": "string"},
                                # Эмитент
                                "issuer": {"type": ["string", "null"]},
                                # Год 
                                "year": {"type": ["integer", "null"], "minimum": 1960}
                            }
                        }
                    },

                    # Доступность
                    "availability": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["work_hours", "peak_hours"],
                        "properties": {
                            # Рабочие часы
                            # Рабочие часы (строгий формат снят, чтобы LLM мог писать 'flexible' и т.д.)
                            "work_hours": {"type": "string"},
                            # Пиковые часы
                            "peak_hours": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 23}}
                        }
                    },

                    # Заметки о выводах
                    "inference_notes": {"type": ["string", "null"]}
                }
            },

            # Занятость
            "employment": {
                "type": "object",
                "additionalProperties": False,
                "required": ["current_occupation", "occupation_industry", "occupation_history"],
                "properties": {
                    # Текущая профессия
                    "current_occupation": {"type": ["string", "null"]},

                    # Профессия и отрасль
                    "occupation_industry": {"type": ["string", "null"]},


                    # История занятости
                    "occupation_history": {
                        "type": "array", 
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["start_year", "end_year", "title", "employer"],
                            "properties": {
                                # Начало года
                                "start_year": {"type": "integer"},
                                # Конец год
                                "end_year": {"type": ["integer", "null"]},
                                # Название
                                "title": {"type": "string"},
                                # Работодатель
                                "employer": {"type": ["string", "null"]}
                            }
                        }
                    }
                }
            },
            
            # Типичные активные часы
            "typical_active_hours": {
                "type": "object",
                "additionalProperties": False,
                "required": ["weekend_behavior", "vacation_patterns"],
                "properties": {

                    # Поведение в выходные
                    "weekend_behavior": {"type": "string"},

                    # Шаблоны отпуска
                    "vacation_patterns": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["frequency", "preferred_destination"],
                        "properties": {
                            # Частота
                            "frequency": {"type": "string"},
                            # Предпочтительный пункт назначения
                            "preferred_destination": {"type": "string"},
                        }
                    }
                }
            },
            "metadata": {"type": "object", "additionalProperties": True}
        }
    }

    schema = {
        "type": "object",
        "required": ["experience"],
        "additionalProperties": False,
        "properties": {
            "experience": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": experience_schema
            }
        },
    }

    example = {
        "experience": [{
            "expertise": ["machine learning", "product management"],

            "capabilities": {
                "intelligence": {
                    "score": 78,
                    "category": "above_average",
                    "profile": ["analytical", "creative"]
                },

                "languages": [
                    { "language": "Русский", "proficiency": "native" },
                ],

                "skills": [
                    { "title": "Python", "category": "programming", "level": "expert", "years": 6 }
                ],

                "hard_skills": ["python", "sql", "pytorch"],
                "soft_skills": ["communication", "problem solving"],
                "tools_used_by": ["Notebook", "VScode", "ChatGPT", "PostgreSQL", "FastAPI"],

                "certifications": [
                    {"title": "AWS Solutions Architect", "issuer": "AWS", "year": 2025 }
                ],

                "availability": {
                    "work_hours": "09:00-18:00",
                    "peak_hours": [10, 11, 15]
                },

                "inference_notes": "Предполагаемая квалификация на основании образования и опыта работы, указанных в профиле"
            },

            "employment": {
                "current_occupation": "CTO",
                "occupation_industry": "software",
                "occupation_history": [{
                    "start_year": 2022,
                    "end_year": None,
                    "title": "CTO",
                    "employer": "Startup X"
                }]

            },
                
            "typical_active_hours": {
                "weekend_behavior": "learning",
                "vacation_patterns": {
                    "frequency": "1-2/year",
                    "preferred_destination": "beach",
                },
            }
        }]
    }

    return system_instruction_experience, example, schema