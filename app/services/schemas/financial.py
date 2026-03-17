# src/modules/clients/community_agents/schemas/financial.py

import json

async def get_fin_part1_schema(count, profile):
    fin_type = "financial"
    system_instruction = f"""
        Ты - генератор подробных финансовых данных агента (Часть 1: Базовые финансы).
        Вход: JSON-объект profile (полный профиль агента).
        Задача: Сгенерировать базовые финансовые показатели: Income, Expenses, Savings, Assets, Liabilities.
        Дополнительно: Сгенерируй **current_inventory** — список предметов, которые агент носит с собой прямо сейчаc (в карманах или сумке).
        
        Правила:
        - Генерируй КОНКРЕТНЫЕ ЧИСЛА, а не диапазоны.
        - Строго следуй именам полей в схеме.
        - Валюта должна совпадать с регионом агента (обычно KZT).
        - ВАЖНО: Поле "{fin_type}" ОБЯЗАНО быть СПИСКОМ (ARRAY) объектов.
        - **current_inventory**: ЭТО СТРОГИЙ МАССИВ ОБЪЕКТОВ внутри каждого финансового профиля.
        - ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{fin_type}". 
        - СТРОГИЙ ЗАПРЕТ: НЕ создавай ключ "financial_part1"! Внутренние объекты должны напрямую содержать ключи "income", "expenses", "savings", "assets", "liabilities", "current_inventory".
    """

    schema_part1 = {
        "type": "object",
        "required": ["income", "expenses", "savings", "assets", "liabilities", "current_inventory"],
        "additionalProperties": False,
        "properties": {
            "assets": {"type": ["number", "null"], "minimum": 0},
            "liabilities": {"type": ["number", "null"], "minimum": 0},
            "income": {
                "type": "object",
                "required": ["currency", "income_period", "income_monthly", "income_annual", "income_type"],
                "additionalProperties": False,
                "properties": {
                    "currency": {"type": "string"},
                    "income_period": {"type": "string"},
                    "income_monthly": {"type": ["number", "null"], "minimum": 0},
                    "income_annual": {"type": ["number", "null"], "minimum": 0},
                    "income_type": {"type": ["string", "null"]}
                }
            },
            "expenses": {
                "type": "object",
                "required": ["expenses_monthly"],
                "additionalProperties": False,
                "properties": {
                    "expenses_monthly": {"type": "number", "minimum": 0}
                }
            },
            "savings": {
                "type": "object",
                "required": ["savings", "savings_rate"],
                "additionalProperties": False,
                "properties": {
                    "savings": {"type": ["number", "null"], "minimum": 0},
                    "savings_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 1}
                }
            },
            "current_inventory": {
                "type": "array",
                "description": "Items the agent carries in pockets or bags.",
                "items": {
                    "type": "object",
                    "required": ["item", "condition", "emotional_value"],
                    "properties": {
                        "item": {"type": "string", "description": "e.g. 'Old iPhone with cracked screen', 'Silver lucky coin'"},
                        "condition": {"type": "string"},
                        "emotional_value": {"type": "number", "minimum": 0, "maximum": 1}
                    }
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["financial"],
        "additionalProperties": False,
        "properties": {
            "financial": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part1
            }
        }
    }
    
    example = {
        "financial": [{
            "income": {
                "currency": "KZT",
                "income_period": "monthly",
                "income_monthly": 450000,
                "income_annual": 5400000,
                "income_type": "salary"
            },
            "expenses": {
                "expenses_monthly": 210000
            },
            "savings": {
                "savings": 2000000,
                "savings_rate": 0.2
            },
            "assets": 1500000,
            "liabilities": 500000,
            "current_inventory": [
                 {"item": "Smartphone", "condition": "good", "emotional_value": 0.8}
            ]
        }]
    }
    return system_instruction, example, schema


async def get_fin_part2_schema(count, profile_with_part1):
    # SIMPLIFIED: Part 2 is mostly removed as low-ROI.
    # We keep it as a stub or just very high-level goals if needed.
    # Currently just returning generic financial goals to avoid breaking pipeline.
    fin_type = "financial"
    system_instruction = f"""
        Ты - генератор финансовых целей.
        Вход: Доходы/Расходы из Part 1.
        Задача: Сгенерировать только Краткосрочные финансовые цели.
        Остальное (кредиты, страховка) отключено для экономии.
        
        Возвращай ровно {count} объектов внутри поля "{fin_type}".
        ОЧЕНЬ ВАЖНО: Каждая КРАТКОСРОЧНАЯ ЦЕЛЬ должна быть объектом с ключами goal, target_amount, priority.
        ОЧЕНЬ ВАЖНО: НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи. Твои объекты в массиве "{fin_type}" должны напрямую содержать поле "goals" (массив целей).
    """

    schema_part2 = {
        "type": "object",
        "required": ["goals"],
        "additionalProperties": False,
        "properties": {
            "goals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["goal", "target_amount", "priority"],
                    "properties": {
                        "goal": {"type": "string"},
                        "target_amount": {"type": ["number", "null"]},
                        "priority": {"type": "string"}
                    }
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["financial"],
        "additionalProperties": False,
        "properties": {
            "financial": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_part2
            }
        }
    }
    
    example = {
        "financial": [{
            "goals": [
                {"goal": "Buy car", "target_amount": 5000000, "priority": "high"}
            ]
        }]
    }
    return system_instruction, example, schema