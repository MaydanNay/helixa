import json

async def get_core_biography_schema(count, profile_context):
    type = "core_biography"
    
    # We expect 'profile_context' to contain the merged demographics + psychology + health + experience + behavioral (+ family?)
    # ideally passed as a dict.
    
    system_instruction = f"""
        Ты - профессиональный биограф и сценарист.
        Вход: Полный профиль агента (Демография, Психология, Здоровье, Опыт, Поведение).
        Задача: Сгенерировать связную "Историю Происхождения", определить текущий жизненный контекст и создать образец голоса.
        
        Твоя цель - объяснить, ПОЧЕМУ агент стал таким (почему он тревожный? почему он выбрал эту работу?).
        Свяжи факты из разных частей профиля в единый нарратив.
        
        - **current_context**: **КРИТИЧЕСКИ ВАЖНО**: Это должен быть СТРОГИЙ ОБЪЕКТ, а не просто абзац текста! Внутри него должны быть: current_chapter_title, status_description, primary_motivation_now, immediate_challenges и initial_state.
        - **initial_state**: На основе status_description определи ЧИСЛОВЫЕ значения mood/energy/stress/social_battery (0-1).
          Например, "В кризисе" → mood=0.3, stress=0.8. "На подъеме" → mood=0.8, energy=0.9.
        - **unresolved_tensions**: **КРИТИЧЕСКИ ВАЖНО**: Это должен быть СТРОГИЙ МАССИВ ОБЪЕКТОВ (Array of Objects), а не массив строк! Каждый объект должен иметь ключи: tension_type, description, trigger_topics.
        - **voice_sample**: **ВАЖНО**: Строгий объект с ключами sample_paragraph и style_notes.
 
        ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{type}" - т.е. объект {{ "{type}": [...] }}. НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи (например, "biography"). Твои объекты должны напрямую содержать поля "origin_story", "current_context" и т.д.
    """

    biography_schema = {
        "type": "object",
        "required": ["origin_story", "current_context", "voice_sample", "narrative_anchors", "unresolved_tensions"],
        "additionalProperties": False,
        "properties": {
            "origin_story": {
                "type": "string", 
                "description": "3 paragraphs describing childhood, major life turning points, and how they became who they are today."
            },
            "current_context": {
                "type": "object",
                "required": ["current_chapter_title", "status_description", "primary_motivation_now", "immediate_challenges", "initial_state"],
                "properties": {
                    "current_chapter_title": {"type": "string", "description": "Metaphorical title for their current life phase."},
                    "status_description": {"type": "string"},
                    "primary_motivation_now": {"type": "string"},
                    "immediate_challenges": {"type": "array", "items": {"type": "string"}},
                    "initial_state": {
                        "type": "object",
                        "required": ["mood", "energy", "stress", "social_battery"],
                        "properties": {
                            "mood": {"type": "number", "minimum": 0, "maximum": 1},
                            "energy": {"type": "number", "minimum": 0, "maximum": 1},
                            "stress": {"type": "number", "minimum": 0, "maximum": 1},
                            "social_battery": {"type": "number", "minimum": 0, "maximum": 1}
                        }
                    }
                }
            },
            "voice_sample": {
                "type": "object",
                "required": ["sample_paragraph", "style_notes"],
                "properties": {
                    "sample_paragraph": {"type": "string", "description": "A monologue (~50-100 words) introducing themselves."},
                    "style_notes": {"type": "string", "description": "Instructions for TTS or Text-Gen (speed, pitch, attitude)."}
                }
            },
            "narrative_anchors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key 'hooks' that could drive future plotlines."
            },
            "unresolved_tensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["tension_type", "description", "trigger_topics"],
                    "properties": {
                        "tension_type": {"type": "string", "enum": ["family", "career", "professional", "social", "romantic", "trauma", "financial", "health", "identity", "other"]},
                        "description": {"type": "string"},
                        "trigger_topics": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            "metadata": {"type": "object", "additionalProperties": True}
        }
    }

    schema = {
        "type": "object",
        "required": ["core_biography"],
        "additionalProperties": False,
        "properties": {
            "core_biography": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": biography_schema
            }
        }
    }
    example = {
        "core_biography": [
            {
                "origin_story": "Иван Петров вырос в интеллигентной семье в Москве, где с ранних лет был окружен книгами и техникой. Его отец, инженер-программист, часто приносил домой старые компьютеры, которые они разбирали вместе. Эти моменты стали для Ивана не просто игрой, а первым шагом в мир программирования.",
                "current_context": {
                    "current_chapter_title": "Поиск баланса",
                    "status_description": "Стабильная работа, но внутреннее выгорание.",
                    "primary_motivation_now": "Найти смысл жизни за пределами работы",
                    "immediate_challenges": ["Справиться с выгоранием", "Наладить личную жизнь"],
                    "initial_state": {
                        "mood": 0.4,
                        "energy": 0.5,
                        "stress": 0.8,
                        "social_battery": 0.3
                    }
                },
                "voice_sample": {
                    "sample_paragraph": "Слушай, я опять всю ночь просидел над этим кодом. Да, знаю, надо было лечь спать, но эта бага... она просто выводила меня из себя. Зато теперь всё работает идеально. Ладно, пошли за кофе, я сейчас усну прямо здесь.",
                    "style_notes": "Говорит быстро, немного устало. Часто использует технический сленг, но старается быть понятным для друзей. Периодически замолкает, подбирая слова."
                },
                "narrative_anchors": ["Неожиданное наследство", "Встреча из прошлого"],
                "unresolved_tensions": [
                    {
                        "tension_type": "family",
                        "description": "Сложные отношения с отцом из-за выбора карьеры",
                        "trigger_topics": ["Отец", "Семейные ожидания", "Одобрение"]
                    }
                ]
            }
        ]
    }
    
    return system_instruction, example, schema
