import json

async def get_cognitive_profile_schema(count, profile_context):
    type = "cognitive_profile"
    system_instruction = f"""
        Ты - проектировщик когнитивных ограничений ИИ (Artificial Ignorance Architect).
        Вход: Demographics.
        Задача: Сгенерировать профиль "интеллектуальных и человеческих несовершенств" агента. 
        Агент НЕ должен быть всезнающим или идеально рациональным. Мы создаем правдоподобного человека с багами и ленью.

        Инструкции по полям:
        - education_level: Уровень образования (Illiterate, Basic, Secondary, Higher, Expert). 
        - analytical_depth: Насколько глубоко агент может анализировать данные (0.1 - поверхностно, 1.0 - системный аналитик).
        - memory_fidelity: Насколько точно агент помнит детали (0.1 - путается и забывает, 1.0 - эйдетическая память).
        - blind_spots: Список тем, в которых агент СОВЕРШЕННО не разбирается.
        
        [COGNITIVE BIAS ENGINE]:
        - bias_weights: Объект с весами (0.1 - 1.0) для искажений:
            - sunk_cost_fallacy: Склонность продолжать убыточное дело (бросает сразу vs терпит до конца).
            - bandwagon_effect: Склонность следовать за толпой (индивидуалист vs конформист).
            - outcome_bias: Оценка решения по результату, а не по качеству процесса.
            - availability_heuristic: Переоценка значимости легкодоступной информации.
        - impulse_control: (0.1 - 1.0) Низкое значение = импульсивные покупки и решения, высокое = самоконтроль.
        
        [FRICTION & ENERGY]:
        - energy_wallet:
            - initial_energy: (50 - 100) Максимальный запас сил на день.
            - burn_rate: (0.5 - 2.0) Скорость сгорания энергии при ментальной нагрузке.

        ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{type}".
    """

    schema = {
        "type": "object",
        "required": [
            "education_level", "analytical_depth", "memory_fidelity", 
            "blind_spots", "bias_weights", "impulse_control", "energy_wallet", "speech_complexity"
        ],
        "additionalProperties": False,
        "properties": {
            "education_level": {
                "type": "string",
                "enum": ["Illiterate", "Basic", "Secondary", "Higher", "Expert"]
            },
            "analytical_depth": {
                "type": "number", 
                "minimum": 0.1, 
                "maximum": 1.0,
                "description": "Limits the reasoning tokens and complexity of logic."
            },
            "memory_fidelity": {
                "type": "number", 
                "minimum": 0.1, 
                "maximum": 1.0,
                "description": "Affects RAG retrieval noise and forgetting speed."
            },
            "blind_spots": {
                "type": "array", 
                "items": {"type": "string"},
                "description": "Topics the agent will refuse to discuss with authority."
            },
            "bias_weights": {
                "type": "object",
                "properties": {
                    "sunk_cost_fallacy": {"type": "number", "minimum": 0.1, "maximum": 1.0},
                    "bandwagon_effect": {"type": "number", "minimum": 0.1, "maximum": 1.0},
                    "outcome_bias": {"type": "number", "minimum": 0.1, "maximum": 1.0},
                    "availability_heuristic": {"type": "number", "minimum": 0.1, "maximum": 1.0}
                },
                "required": ["sunk_cost_fallacy", "bandwagon_effect", "outcome_bias", "availability_heuristic"]
            },
            "impulse_control": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 1.0
            },
            "energy_wallet": {
                "type": "object",
                "properties": {
                    "initial_energy": {"type": "integer", "minimum": 30, "maximum": 100},
                    "burn_rate": {"type": "number", "minimum": 0.5, "maximum": 2.5}
                },
                "required": ["initial_energy", "burn_rate"]
            },
            "speech_complexity": {
                "type": "string",
                "enum": ["Low", "Medium", "High"]
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
        "cognitive_profile": [
            {
                "education_level": "Secondary",
                "analytical_depth": 0.4,
                "memory_fidelity": 0.6,
                "blind_spots": ["Quantum physics", "Corporate law"],
                "bias_weights": {
                    "sunk_cost_fallacy": 0.8,
                    "bandwagon_effect": 0.4,
                    "outcome_bias": 0.7,
                    "availability_heuristic": 0.5
                },
                "impulse_control": 0.3,
                "energy_wallet": {
                    "initial_energy": 80,
                    "burn_rate": 1.2
                },
                "speech_complexity": "Medium"
            }
        ]
    }

    return system_instruction, example, wrapper_schema
