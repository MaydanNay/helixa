# src/modules/clients/community_agents/schemas/private.py

import json

async def get_private_schema(count, profile):
    type = "private"
    system_instruction_private = f"""
        Ты - генератор синтетических приватных данных агента.
        Вход: JSON-объект profile (полный профиль агента), который нужно проанализировать.
        Задача: на основе profile сгенерировать ТОЛЬКО JSON-объект(ы) соответствующие схеме {type}.
        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Числовые значения в пределах логичных диапазонов.
        - Даты в формате YYYY-MM-DD либо ISO 8601.
        - Используй данные из profile (core, experience, behavioral, sociology, financial) для приоритета и наполнения памяти.
        - Делай реалистичные и логически обоснованные предположения.

        profile:\n {json.dumps(profile, ensure_ascii=False)}
    """

    schema_private = {
        "type": "object",
        "required": ["secrets", "sexual_history", "mental_and_trauma", "other_private_questions", "storytelling_depths"],
        "additionalProperties": False,
        "properties": {
            # Секреты
            "secrets": {"type": "array", "items": {"type": "string"}},

            # Сексуальная история
            "sexual_history": {
                "type": "object",
                "required": [
                    "sexual_activity_count", "sexual_partners_count", "last_activity_date", "currently_sexually_active", "libido_level", 
                    "masturbation_frequency_per_week", "sexual_orientation", "kinks", "stis_history", "safe_sex_practices"
                ],
                "additionalProperties": {"type": "string"},
                "properties": {
                    # Количество сексуальных контактов
                    "sexual_activity_count": {"type": "integer", "minimum": 0},

                    # Количество сексуальных партнеров
                    "sexual_partners_count": {"type": "integer", "minimum": 0},

                    # Дата последней активности
                    "last_activity_date": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},

                    # В настоящее время сексуально активный
                    "currently_sexually_active": {"type": ["boolean", "null"]},
                    
                    # Уровень либидо
                    "libido_level": {"type": "integer", "minimum": 0, "maximum": 10},
                    
                    # Частота мастурбации в неделю 
                    "masturbation_frequency_per_week": {"type": "number", "minimum": 0},
                    
                    # Сексуальная ориентация
                    "sexual_orientation": {"type": "string", "enum": ["heterosexual", "homosexual", "bisexual", "asexual", "pansexual", "other", "null"]},
                    
                    # Изгибы
                    "kinks": {"type": "array", "items": {"type": "string"}},
                    
                    # История СТИС
                    "stis_history": {"type": ["string", "null"], "description": "Необязательно, обобщённо"},
                    
                    # Безопасные сексуальные практики
                    # LLM часто возвращает True/False (boolean) — принимаем и кастуем в строку
                    "safe_sex_practices": {"type": ["string", "boolean", "null"]}
                },
            },

            # Психическое и травматическое
            "mental_and_trauma": {
                "type": "object",
                "required": ["sexual_trauma_flag", "therapy_history"],
                "additionalProperties": {"type": "string"},
                "properties": {
                    # Сексуальная травма
                    "sexual_trauma_flag": {"type": "boolean", "description": "Если true - не раскрывать детали автоматически"},
                    
                    # История терапии
                    "therapy_history": {"type": ["string", "null"]}
                },
            },

            # Другие личные вопросы
            "other_private_questions": {
                "type": "object",
                "required": ["porn_consumption", "cheating_history", "bank_pin_or_similar"],
                "additionalProperties": {"type": "string"},
                "properties": {
                    # Потребление порнографии
                    # LLM иногда пишет 'false' или 'true' — добавляем в enum как допустимые
                    "porn_consumption": {"type": "string", "enum": ["never", "rarely", "sometimes", "often", "daily", "null", "false", "true"]},
                    
                    # История обмана
                    "cheating_history": {"type": ["string", "null"]},
                    
                    # Банковский PIN-код или аналогичный код
                    "bank_pin_or_similar": {"type": ["string", "null"], "description": "НЕ хранить реальные секреты/ключи"}
                },
            },

            # [NEW] Storytelling Depths
            "storytelling_depths": {
                "type": "object",
                "required": ["true_intentions", "internal_conflict", "hidden_fear"],
                "properties": {
                    "true_intentions": {"type": "string", "description": "What they REALLY want, even if they lie about it."},
                    "internal_conflict": {"type": "string", "description": "Two competing desires or values causing tension."},
                    "hidden_fear": {"type": "string", "description": "A fear they rarely admit even to themselves."}
                }
            },
        }
    }

    schema = {
        "type": "object",
        "required": ["private"],
        "additionalProperties": False,
        "properties": {
            "private": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_private
            }
        }
    }

    example = ""

    return system_instruction_private, example, schema
























    # example = {
    #     "private": [{
    #         "secrets": [
    #             "Когда был подростком, взял у отца деньги из кошелька и никому не рассказывал.",
    #             "Скрывал от семьи серьёзные долги в 2019 году.",
    #             "Однажды подделал подпись ради ускорения сделки.",
    #             "В университете списывал на экзамене и спасся от отчисления.",
    #             "Раз в несколько лет тайно поддерживает контакт с бывшим партнёром."
    #         ],
    #         "sexual_history": {
    #             "sexual_activity_count": 24,
    #             "sexual_partners_count": 7,
    #             "last_activity_date": "2025-10-20",
    #             "currently_sexually_active": True,
    #             "libido_level": 6,
    #             "masturbation_frequency_per_week": 3.0,
    #             "sexual_orientation": "heterosexual",
    #             "kinks": ["roleplay", "light BDSM"],
    #             "stis_history": "null",
    #             "safe_sex_practices": "uses_condoms_sometimes"
    #         },
    #         "mental_and_trauma": {
    #             "sexual_trauma_flag": False,
    #             "therapy_history": "Краткая терапия по тревожности в 2023 - 6 сессий"
    #         },
    #         "other_private_questions": {
    #             "porn_consumption": "sometimes",
    #             "cheating_history": "однократно в 2018",
    #             "bank_pin_or_similar": "REDACTED"
    #         },
    #     }]
    # }