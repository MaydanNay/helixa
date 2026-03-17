import json

async def get_core_demographics_schema(count, profile_context=None):
    type = "core_demographics"
    system_instruction = f"""
        Ты - генератор демографических данных агента.
        Вход: Context (если есть), нужно сгенерировать базовые демографические данные.
        Возвращай ровно {count} объектов внутри поля "{type}".
        
10:         Поведение:
11:             - Делай профили разнообразными.
12:             - ГЕНЕРАЦИЯ ИМЕН: Генерируй КРАЙНЕ уникальные, редкие и запоминающиеся имена и фамилии. Избегай клише.
13:             - РАЗНООБРАЗИЕ: Если ты генерируешь пачку агентов, каждый должен иметь кардинально разную судьбу, возраст и происхождение. Удивляй!
14:             - ГЕНЕРАЦИЯ ЛОКАЦИЙ: Реалистичные координаты в пределах города.
            - **favorite_spots**: Создай 2-3 любимых места с историей.
            - **sensory**: Опиши "сенсорную подпись" (запах, походку, текстуру кожи).
            - **personal_spaces**: Опиши личное пространство (рабочий стол, прикроватная тумбочка).
            - **gestures**: Опиши характерные жесты и мимику.
            
            ВАЖНО: Для полей с фиксированным списком значений (Enum) — используй ТОЛЬКО разрешенные значения. Например, для 'spot_type' используй только: cafe, restaurant, park, gym, bar, shop, religious, cultural, nature, other. Если место — рынок или ТЦ, пиши 'other' или 'shop'.
            ОЧЕНЬ ВАЖНО: Используй точные ключи из схемы. У ключа имени ДОЛЖНО быть название "agent_name", НЕ "name". НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи (например, "core_demographics").

            ПРИМЕР СТРУКТУРЫ (ДЛЯ ФОРМАТА, НЕ ИСПОЛЬЗУЙ ДАННЫЕ):
            {{
                "core_demographics": [
                    {{
                        "agent_name": "NAME",
                        "last_name": "SURNAME",
                        "agent_role": "ROLE",
                        "demographics": {{
                            "age": 25,
                            "birth": "1999-01-01",
                            "gender": "GENDER",
                            "city": "CITY",
                            "locations": {{
                                "home": {{"address": "STREET_NAME", "lat": 0.0, "lng": 0.0}},
                                "favorite_spots": [{{"name": "SPOT", "spot_type": "cafe", "lat": 0.0, "lng": 0.0, "backstory": "TEXT", "emotional_attachment": 0.5, "visit_frequency": "weekly"}}]
                            }}
                        }}
                    }}
                ]
            }}
    """

    schema = {
        "type": "object",
        "required": ["agent_name"],
        "additionalProperties": True,
        "properties": {
            "agent_name": {"type": "string"},
            "last_name": {"type": "string", "description": "Фамилия агента."}, 
            "agent_role": {"type": "string"},
            "agent_profile": {"type": "string"},
            "demographics": {
                "type": "object",
                "required": [
                    "age", "birth", "gender", "ethnicity", "country", "city",
                    "locale", "primary_currency", "timezone", "marital_status", 
                    "children_count", "education_level", "education", "hobbies", "home_owner", "vehicle", "locations"
                ],
                "additionalProperties": False,
                "properties": {
                    "age": {"type": "integer", "minimum": 16, "maximum": 70},
                    "birth": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                    "gender": {"type": "string"},
                    "ethnicity": {"type": "string"},
                    "country": {"type": "string"},
                    "city": {"type": "string"},
                    "locale": {"type": "string"},
                    "primary_currency": {"type": "string"},
                    "timezone": {"type": "string"},
                    "locations": {
                        "type": "object",
                        "required": ["home"],
                        "properties": {
                            "home": {
                                "type": "object", 
                                "required": ["address", "lat", "lng"], 
                                "properties": {
                                    "address": {"type": "string"}, 
                                    "lat": {"type": "number", "minimum": -90, "maximum": 90}, 
                                    "lng": {"type": "number", "minimum": -180, "maximum": 180}
                                }
                            },
                            "work": {
                                "type": ["object", "null"], 
                                "properties": {
                                    "address": {"type": "string"}, 
                                    "lat": {"type": "number", "minimum": -90, "maximum": 90}, 
                                    "lng": {"type": "number", "minimum": -180, "maximum": 180}
                                }
                            },
                            "favorite_spots": {
                                "type": "array",
                                "description": "Personal places with emotional significance.",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "spot_type", "lat", "lng", "backstory", "emotional_attachment", "visit_frequency"],
                                    "properties": {
                                        "name": {"type": "string", "description": "Name of the place (e.g. 'Café Luna')"},
                                        "spot_type": {"type": "string", "enum": ["cafe", "restaurant", "park", "gym", "bar", "shop", "religious", "cultural", "nature", "other"]},
                                        "lat": {"type": "number", "minimum": -90, "maximum": 90},
                                        "lng": {"type": "number", "minimum": -180, "maximum": 180},
                                        "backstory": {"type": "string"},
                                        "emotional_attachment": {"type": "number", "minimum": 0, "maximum": 1},
                                        "visit_frequency": {"type": "string", "enum": ["daily", "weekly", "monthly", "rarely", "special_occasions"]}
                                    }
                                }
                            }
                        }
                    },
                    "marital_status": {"type": "string"},
                    "children_count": {"type": "integer", "minimum": 0},
                    "education_level": {"type": "string"},
                    "education": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["stage", "field", "institution", "start_year", "graduation_year"],
                            "properties": {
                                "stage": {"type": "string"},
                                "degree": {"type": ["string", "null"]},
                                "field": {"type": "string"},
                                "institution": {"type": "string"},
                                "start_year": {"type": "integer"},
                                "graduation_year": {"type": "integer"},
                                "notes": {"type": "string"}
                            }
                        }
                    },
                    "hobbies": {"type": "array", "items": {"type": "string"}},
                    "home_owner": {"type": "boolean"},
                    "vehicle": {"type": "boolean"},
                }
            }
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
        "core_demographics": [
            {
                "agent_name": "Azamat",
                "last_name": "Suleymenov",
                "agent_role": "Architect",
                "agent_profile": "Creative and ambitious architect from Almaty.",
                "demographics": {
                    "age": 34,
                    "birth": "1992-05-12",
                    "gender": "Male",
                    "ethnicity": "Kazakh",
                    "country": "Kazakhstan",
                    "city": "Almaty",
                    "locale": "ru_KZ",
                    "primary_currency": "KZT",
                    "timezone": "Asia/Almaty",
                    "locations": {
                        "home": {
                            "address": "Abay Ave 10, Apt 45",
                            "lat": 43.238949,
                            "lng": 76.889709
                        },
                        "work": {
                            "address": "Al-Farabi 77, Esentai Tower",
                            "lat": 43.218949,
                            "lng": 76.929709
                        },
                        "favorite_spots": [
                            {
                                "name": "Nedelka",
                                "spot_type": "cafe",
                                "lat": 43.24,
                                "lng": 76.91,
                                "backstory": "Favorite coffee place for morning sketches.",
                                "emotional_attachment": 0.8,
                                "visit_frequency": "daily"
                            }
                        ]
                    },
                    "marital_status": "Single",
                    "children_count": 0,
                    "education_level": "Master",
                    "education": [
                        {
                            "stage": "University",
                            "degree": "Master of Architecture",
                            "field": "Urban Planning",
                            "institution": "KazGASA",
                            "start_year": 2010,
                            "graduation_year": 2016,
                            "notes": "Graduated with honors"
                        }
                    ],
                    "hobbies": ["Photography", "Hiking"],
                    "home_owner": True,
                    "vehicle": True
                }
            }
        ]
    }
    
    return system_instruction, example, wrapper_schema
