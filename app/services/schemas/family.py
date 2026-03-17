
import json

async def get_family_schema(count, profile):
    type = "family"
    system_instruction_family = f"""
        Ты - генератор семейных связей агента.
        Вход: JSON-объект profile (включая core данные, возраст, страну и т.д.).
        Задача: Сгенерировать детальную структуру семьи.
        Возвращай ровно {count} объектов внутри поля \"{type}\" - т.е. объект {{ \"{type}\": [...] }}.

        Правила:
        - Генерируй как близких родственников (родители, братья/сестры, супруги, дети), так и расширенную семью (дяди, тети, бабушки, дедушки, кузены).
        - Учитывай возраст агента (например, если агенту 60 лет, родители скорее всего умерли, но есть внуки).
        - Указывай статус (alive/deceased) и качество отношений.

        ВАЖНО: Для полей с фиксированным списком значений (Enum) — используй ТОЛЬКО разрешенные значения.
    """

    member_schema = {
        "type": "object",
        "required": ["relation_type", "name", "age", "gender", "is_alive", "occupation", "relationship_quality"],
        "additionalProperties": False,
        "properties": {
            # Тип родства: Father, Mother, Brother, Sister, Spouse, Son, Daughter, 
             # Grandfather, Grandmother, Uncle, Aunt, Cousin, Nephew, Niece, Grandson, Granddaughter, etc.
            "relation_type": {
                "type": "string",
                "enum": ["Self", "Father", "Mother", "Brother", "Sister", "Spouse", "Son", "Daughter", "Grandfather", "Grandmother", "Uncle", "Aunt", "Cousin", "Nephew", "Niece", "Grandson", "Granddaughter", "Other"],
                "description": "Standardized relationship type. Strictly choose from list."
            },
            "name": {"type": "string"},
            "age": {"type": ["integer", "null"], "description": "Age in years. Use null ONLY if age is absolutely impossible to determine (e.g. dead long ago)."},
            "gender": {"type": "string", "enum": ["Male", "Female", "Other", "Non-binary"], "description": "Choose from list. Use 'Other' or 'Non-binary' if appropriate."},
            "is_alive": {"type": ["boolean", "null"], "description": "True if alive, False if deceased. Use null if status is completely unknown (rare)."},
            "occupation": {"type": ["string", "null"]},
            # Качество отношений от 0 до 10, или null если умер/не общаются
            "relationship_quality": {"type": ["integer", "null"], "minimum": 0, "maximum": 10}, 
            "notes": {"type": ["string", "null"], "description": "Краткие заметки: живет ли вместе, конфликты, помощь и т.п."}
        }
    }

    schema_family = {
        "type": "object",
        "required": ["total_members_count", "immediate_family", "extended_family"],
        "additionalProperties": False,
        "properties": {
            "total_members_count": {"type": "integer"},
            "immediate_family": {
                "type": "array",
                "items": member_schema,
                "description": "Родители, супруги, дети, родные братья и сестры"
            },
            "extended_family": {
                "type": "array",
                "items": member_schema,
                "description": "Бабушки, дедушки, дяди, тети, племянники, двоюродные"
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["family"],
        "additionalProperties": False,
        "properties": {
            "family": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_family
            }
        },
    }

    example = {
        "family": [{
            "total_members_count": 5,
            "immediate_family": [
                 {
                    "relation_type": "Father",
                    "name": "Азамат",
                    "age": 55,
                    "gender": "Male",
                    "is_alive": True,
                    "occupation": "Инженер",
                    "relationship_quality": 8,
                    "notes": "Живет в другом городе, созваниваются раз в неделю"
                 }
            ],
            "extended_family": [
                 {
                    "relation_type": "Uncle",
                    "name": "Серик",
                    "age": 50,
                    "gender": "Male",
                    "is_alive": True,
                    "occupation": "Бизнесмен",
                    "relationship_quality": 5,
                    "notes": "Богатый родственник, видятся на праздниках"
                 }
            ]
        }]
    }

    return system_instruction_family, example, schema
