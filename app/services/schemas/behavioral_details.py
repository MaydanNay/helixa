import json

async def get_behavioral_details_schema(count, profile_context):
    type = "behavioral_details"
    system_instruction = f"""
        Ты - генератор детальных предпочтений.
        Вход: Full Profile.
        Задача: Сгенерировать предпочтения.
        Возвращай ровно {count} объектов внутри поля "{type}".
    """

    schema = {
        "type": "object",
        "required": ["daily_life", "relationships", "preferences_and_tastes"],
        "additionalProperties": False,
        "properties": {
            "preferred_channels": {
                "type": "array",
                "items": {"type": "object", "required": ["channel", "weight"], "properties": {"channel": {"type": "string"}, "weight": {"type": "number"}}}
            },
            "daily_life": {
                "type": "object",
                "required": ["daily_routine"],
                "additionalProperties": False,
                "properties": {
                    "daily_routine": {"type": "string"},
                }
            },
            "relationships": {
                "type": "object",
                "required": ["to_money", "to_children", "to_animals", "to_nature", "social_style", "conflict_resolution", "emotional_expression"],
                "additionalProperties": False,
                "properties": {
                    "to_money": {"type": "string"},
                    "to_children": {"type": "string"}, 
                    "to_animals": {"type": "string"}, 
                    "to_nature": {"type": "string"},
                    "social_style": {"type": "string"},
                    "conflict_resolution": {"type": "string"},
                    "emotional_expression": {"type": "string"}
                }
            },
            "preferences_and_tastes": {
                "type": "object",
                "required": ["favorite_topics", "aesthetic"],
                "additionalProperties": False,
                "properties": {
                    "favorite_topics": {"type": "array", "items": {"type": "string"}},
                    "disliked_topics": {"type": "array", "items": {"type": "string"}},
                    "favorite_brands": {"type": "array", "items": {"type": ["string", "null"]}},
                    "favorite_foods": {"type": "array", "items": {"type": ["string", "null"]}},
                    "aesthetic": {"type": "string"},
                    "favorite_media": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "movies": {"type": "array", "items": {"type": ["string", "null"]}},
                            "books": {"type": "array", "items": {"type": ["string", "null"]}},
                            "music": {"type": "array", "items": {"type": ["string", "null"]}}
                        }
                    }
                }
            }
        }
    }

    wrapper_schema = {
        "type": "object",
        "required": [type],
        "additionalProperties": False,
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
        type: [
            {
                "preferred_channels": [{"channel": "Telegram", "weight": 0.8}],
                "daily_life": {"daily_routine": "Wake up at 7 AM, work till 5 PM."},
                "relationships": {
                    "to_money": "Saver",
                    "to_children": "Neutral",
                    "to_animals": "Love cats",
                    "to_nature": "Enjoys hiking"
                },
                "preferences_and_tastes": {
                    "favorite_topics": ["Technology", "Sci-Fi"],
                    "disliked_topics": ["Politics"],
                    "favorite_brands": ["Apple"],
                    "favorite_foods": ["Sushi"],
                    "aesthetic": "Minimalist",
                    "favorite_media": {
                        "movies": ["Inception"],
                        "books": ["1984"],
                        "music": ["Synthwave"]
                    }
                }
            }
        ]
    }
    
    return system_instruction, example, wrapper_schema
