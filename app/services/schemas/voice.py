# src/modules/clients/community_agents/schemas/voice.py

def get_voice_schema(count):
    type_name = "voice_dna"
    system_instruction = f"""
    Ты - режиссер по работе с актерами. Твоя задача - создать уникальный "Голос" (стиль письма/речи) для персонажа.
    Основывайся на его Биографии, Возрасте, Психотипе (Big5) и Профессии.
    
    Параметры:
    - formality: 0.0 (панибратство, сленг) -> 1.0 (официально-деловой, сухой).
    - emotiveness: 0.0 (робот, стоик) -> 1.0 (драма, куча восклицательных, капс).
    - vocabulary: Сложность лексики.
    - style_guide: Список конкретных инструкций для System Prompt (напр. "Никогда не используй эмодзи", "Начинай фразы с 'Ну...'").
    
    - **КРИТИЧЕСКИ ВАЖНО**: Все списки (parasite_words, favorite_idioms, forbidden_topics, style_guide, catchphrases) — это ПЛОСКИЕ МАССИВЫ СТРОК. НИКАКИХ СЛОВАРЕЙ ВНУТРИ! Пример: ["word1", "word2"].

    Верни JSON объект с полем "{type_name}".
    """

    schema_item = {
        "type": "object",
        "required": ["formality", "emotiveness", "vocabulary", "style_guide"],
        "additionalProperties": True,
        "properties": {
            "formality": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Level of formality. 0.1=Slang/Rude, 0.5=Neutral, 0.9=Academic/Official."
            },
            "emotiveness": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Emotional range. 0.1=Robot, 0.9=Hysterical/Expressive."
            },
            "vocabulary": {
                "type": "string",
                "description": "Complexity and type of vocabulary used (e.g. Simple, Standard, Academic, Technical, Slang, Archaic, Poetic)."
            },
            "sentence_complexity": {
                "type": "string", 
                "description": "Overall structure and rhythm of speech (e.g. simple, moderate, eloquent, chaotic)."
            },
            "parasite_words": {
                "type": "array", 
                "items": {"type": "string"}, 
                "description": "Words or filler phrases commonly used (e.g. 'like', 'um', 'basically')."
            },
            "favorite_idioms": {
                "type": "array", 
                "items": {"type": "string"}
            },
            "forbidden_topics": {
                "type": "array", 
                "items": {"type": "string"}, 
                "description": "Topics the agent feels uncomfortable discussing or avoids."
            },
            "style_guide": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 5,
                "description": "Specific instruction strings for the LLM to act this role."
            },
            "catchphrases": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
                "description": "Typical phrases they might use (optional)."
            }
        }
    }

    schema = {
        "type": "object",
        "required": [type_name],
        "additionalProperties": False,
        "properties": {
            type_name: {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_item
            }
        }
    }

    example = {
        type_name: [
            {
                "formality": 0.2,
                "emotiveness": 0.8,
                "vocabulary": "Slang",
                "style_guide": [
                    "Use lowercase only",
                    "Use many emojis",
                    "Address user as 'bro' or 'sis'"
                ],
                "catchphrases": ["lol", "cringe", "fr fr"]
            }
        ]
    }

    return system_instruction, example, schema
