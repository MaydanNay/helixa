import json

async def get_core_psychology_schema(count, profile_context):
    type = "core_psychology"
    system_instruction = f"""
        Ты - генератор психологического портрета.
        Вход: Demographics.
        - СТРОГО генерируй ВСЕ ТРЕБУЕМЫЕ ПОЛЯ: "religion", "worldview", "core_values", "moral_principles", "self_concept", "fears", "dream", "motivations", "achievements", "character", "temperament", "personality", "needs", "dark_triad", "advantages", "disadvantages", "emotional_triggers", "coping_mechanisms".
        - Личность (Big5, ценности, причуды). **КРИТИЧЕСКИ ВАЖНО**: ВСЕ списки ценностей (values, core_values, moral_principles) — это ПЛОСКИЕ МАССИВЫ СТРОК (Array of Strings). НИКАКИХ СЛОВАРЕЙ {{"achievement": 0.8}} ВНУТРИ! Пример: ["Честность", "Доброта"].
        - Needs (Maslow: survival, safety, social, esteem, self_actualization). **ВАЖНО**: Значения должны быть ЧИСЛАМИ (float) от 0.0 до 1.0 (например 0.8), НИКАКИХ СТРОК (типа "fulfilled")!
        - Dark Triad (narcissism, machiavellianism, psychopathy). **ВАЖНО**: Аналогично, строго числа от 0.0 до 1.0!
        - **ВАЖНО: emotional_triggers** — темы/фразы, вызывающие эмоции. **КРИТИЧЕСКИ ВАЖНО**: Это должен быть СТРОГИЙ МАССИВ ОБЪЕКТОВ (Array of Objects), а не просто словарь {{ключ: значение}}! Каждый объект должен иметь ключи: trigger, trigger_type, reaction, intensity!
        - **ВАЖНО: coping_mechanisms** — как справляется со стрессом (массив объектов с mechanism, adaptive, frequency).
        
        ВАЖНО: Для полей с фиксированным списком значений (Enum) — используй ТОЛЬКО разрешенные значения.
        **СТРОГО ЗАПРЕЩАЕТСЯ** возвращать входные данные (Demographics) обратно. Генерируй ТОЛЬКО параметры психологии, описанные в схеме.
        ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{type}". НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи типа "psychology". Твои объекты должны напрямую содержать поля "religion", "worldview" и т.д.

        ПРИМЕР СТРУКТУРЫ (ДЛЯ ФОРМАТА, НЕ ИСПОЛЬЗУЙ ДАННЫЕ):
        {{
            "core_psychology": [
                {{
                    "religion": "RELIGION",
                    "personality": {{
                        "big5": {{"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5}},
                        "values": ["VALUE1", "VALUE2"],
                        "quirks": ["QUIRK1"]
                    }},
                    "emotional_triggers": [{{"trigger": "TEXT", "trigger_type": "topic", "reaction": "TEXT", "intensity": 0.5}}]
                }}
            ]
        }}
    """

    schema = {
        "type": "object",
        "required": [
            "religion", "worldview", "core_values", "moral_principles", "self_concept",
            "fears", "dream", "motivations", "achievements", "character", "temperament",
            "personality", "needs", "dark_triad", "advantages", "disadvantages", "emotional_triggers", "coping_mechanisms"
        ],
        "additionalProperties": False,
        "properties": {
            "religion": {"type": "string"},
            "worldview": {"type": "string"},
            "core_values": {"type": "array", "items": {"type": "string"}},
            "moral_principles": {"type": "array", "items": {"type": "string"}},
            "self_concept": {"type": "string"},
            "fears": {"type": "array", "items": {"type": "string"}},
            "dream": {"type": "string"},
            "motivations": {"type": "array", "items": {"type": "string"}},
            "achievements": {"type": "array", "items": {"type": "string"}},
            "character": {"type": "string"},
            "temperament": {"type": "string"},
            "personality": {
                "type": "object",
                "required": ["big5", "values", "quirks"],
                "properties": {
                    "big5": {
                        "type": "object",
                        "required": ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"],
                        "properties": {
                            "openness": {"type": "number"}, 
                            "conscientiousness": {"type": "number"}, 
                            "extraversion": {"type": "number"}, 
                            "agreeableness": {"type": "number"}, 
                            "neuroticism": {"type": "number"} 
                        },
                    },
                    "values": {"type": "array", "items": {"type": "string"}},
                    "quirks": {"type": "array", "items": {"type": "string"}},
                }
            },
            "needs": {
                "type": "object",
                "description": "Current satisfaction level of needs (0.0 = starved, 1.0 = fully satisfied).",
                "required": ["survival", "safety", "social", "esteem", "self_actualization"],
                "properties": {
                    "survival": {"type": "number", "minimum": 0, "maximum": 1},
                    "safety": {"type": "number", "minimum": 0, "maximum": 1},
                    "social": {"type": "number", "minimum": 0, "maximum": 1},
                    "esteem": {"type": "number", "minimum": 0, "maximum": 1},
                    "self_actualization": {"type": "number", "minimum": 0, "maximum": 1}
                }
            },
            "dark_triad": {
                "type": "object",
                "description": "Dark Triad traits (0.0 to 1.0).",
                "required": ["narcissism", "machiavellianism", "psychopathy"],
                "properties": {
                    "narcissism": {"type": "number", "minimum": 0, "maximum": 1},
                    "machiavellianism": {"type": "number", "minimum": 0, "maximum": 1},
                    "psychopathy": {"type": "number", "minimum": 0, "maximum": 1}
                }
            },
            "advantages": {"type": "array", "items": {"type": "string"}},
            "disadvantages": {"type": "array", "items": {"type": "string"}},
            "emotional_triggers": {
                "type": "array",
                "description": "Topics, phrases, or situations that bypass logic and cause emotional reactions.",
                "items": {
                    "type": "object",
                    "required": ["trigger", "trigger_type", "reaction", "intensity"],
                    "properties": {
                        "trigger": {"type": "string", "description": "The phrase, topic or situation (e.g. 'Mentioning father', 'Doubting competence')"},
                        "trigger_type": {"type": "string", "enum": ["topic", "phrase", "situation", "memory", "sound"], "description": "Strictly choose from list."},
                        "reaction": {"type": "string", "description": "How they react (e.g. 'Gets defensive', 'Shuts down', 'Becomes aggressive')"},
                        "intensity": {"type": "number", "minimum": 0, "maximum": 1, "description": "0.3=mild discomfort, 1.0=complete breakdown"}
                    }
                }
            },
            "coping_mechanisms": {
                "type": "array",
                "description": "Predefined responses to stress and emotional pain.",
                "items": {
                    "type": "object",
                    "required": ["mechanism", "adaptive", "frequency"],
                    "properties": {
                        "mechanism": {"type": "string", "description": "The coping strategy (e.g. 'Humor deflection', 'Isolation', 'Seeking validation', 'Exercise')"},
                        "adaptive": {"type": "boolean", "description": "True=healthy coping, False=maladaptive"},
                        "frequency": {"type": "string", "enum": ["rarely", "sometimes", "often", "always"], "description": "Strictly choose from list."}
                    }
                }
            },
            "metadata": {"type": "object", "additionalProperties": True}
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
    
    example = {
        "core_psychology": [
            {
                "religion": "Agnostic",
                "worldview": "Scientific Humanism",
                "core_values": ["Innovation", "Freedom", "Responsibility"],
                "moral_principles": ["Do no harm", "Truth above comfort"],
                "self_concept": "A misunderstood visionary",
                "fears": ["Mediocrity", "Loss of memory"],
                "dream": "Build a sustainable city layout for Almaty",
                "motivations": ["Legacy", "Curiosity"],
                "achievements": ["Won young architect award", "Climbed Pik Almaty"],
                "character": "INTJ-A",
                "temperament": "Phlegmatic",
                "personality": {
                    "big5": {
                        "openness": 0.9,
                        "conscientiousness": 0.8,
                        "extraversion": 0.3,
                        "agreeableness": 0.4,
                        "neuroticism": 0.2
                    },
                    "values": ["Rationality", "Efficiency"],
                    "quirks": ["Counts steps when nervous", "Drink coffee only black"]
                },
                "needs": {
                    "survival": 0.9,
                    "safety": 0.8,
                    "social": 0.4,
                    "esteem": 0.6,
                    "self_actualization": 0.7
                },
                "dark_triad": {
                    "narcissism": 0.4,
                    "machiavellianism": 0.3,
                    "psychopathy": 0.1
                },
                "advantages": ["Systems thinking", "Calm under pressure"],
                "disadvantages": ["Overthinking", "Socially awkward"],
                "emotional_triggers": [
                    {
                        "trigger": "Unlogical arguments",
                        "trigger_type": "situation",
                        "reaction": "Becomes visibly annoyed",
                        "intensity": 0.5
                    }
                ],
                "coping_mechanisms": [
                    {
                        "mechanism": "Long solo walks",
                        "adaptive": True,
                        "frequency": "often"
                    }
                ]
            }
        ]
    }

    return system_instruction, example, wrapper_schema
