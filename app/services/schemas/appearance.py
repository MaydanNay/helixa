# backend/app.services.schemas/appearance.py

async def get_appearance_schema(count, profile_context):
    type_name = "appearance_details"
    system_instruction = f"""
        Ты - профессиональный дизайнер персонажей и генетик.
        Вход: Полный профиль агента (Демография, Здоровье, Биография).
        Задача: Сгенерировать детальное описание внешности, которое отражает жизнь и характер персонажа.
        
        **Параметры:**
        - **genetic_traits**: Генетические особенности (цвет глаз, тип волос, рост, телосложение).
        - **aging_effects**: Как жизнь отразилась на лице (морщины, шрамы, усталость).
        - **style_and_grooming**: Личный стиль, прическа, ухоженность.
        - **distinctive_features**: Особенные приметы (тату, пирсинг, родимые пятна).
        - **clothing_preferences**: Типичный гардероб на основе финансового статуса и работы.
        
        Верни JSON объект с полем "{type_name}".
    """

    schema_item = {
        "type": "object",
        "required": [
            "height_cm", "body_type", "skin_tone", "eye_color", "hair", 
            "face_features", "clothing_style", "accessories", "aesthetic_vibe"
        ],
        "properties": {
            "height_cm": {"type": "integer", "minimum": 50, "maximum": 250},
            "body_type": {"type": "string", "enum": ["underweight", "slim", "athletic", "average", "heavy", "obese"]},
            "skin_tone": {"type": "string"},
            "eye_color": {"type": "string"},
            "hair": {
                "type": "object",
                "required": ["color", "length", "texture", "style"],
                "properties": {
                    "color": {"type": "string"},
                    "length": {"type": "string", "enum": ["bald", "very short", "short", "medium", "long"]},
                    "texture": {"type": "string", "enum": ["straight", "wavy", "curly", "coily"]},
                    "style": {"type": "string"}
                }
            },
            "face_features": {
                "type": "object",
                "required": ["shape", "notable_traits"],
                "properties": {
                    "shape": {"type": "string", "enum": ["oval", "round", "square", "heart", "diamond", "long"]},
                    "notable_traits": {"type": "array", "items": {"type": "string"}, "description": "e.g., freckles, scars, sharp jawline"}
                }
            },
            "clothing_style": {
                "type": "object",
                "required": ["general_vibe", "typical_outfit"],
                "properties": {
                    "general_vibe": {"type": "string", "description": "e.g., 'Corporate Minimalist', 'Streetwear', 'Bohemian'"},
                    "typical_outfit": {"type": "string"}
                }
            },
            "accessories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "e.g., 'glasses', 'silver rings', 'watch'"
            },
            "aesthetic_vibe": {
                "type": "string",
                "description": "A powerful 1-sentence summary of the visual presence."
            }
        }
    }

    schema = {
        "type": "object",
        "required": [type_name],
        "properties": {
            type_name: {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_item
            }
        }
    }

    return system_instruction, {}, schema
