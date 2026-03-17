import asyncio
import logging
import json
from app.services.validation.schema_utils import validate_and_parse_response
from app.services.schemas.core_psychology import get_core_psychology_schema

logging.basicConfig(level=logging.DEBUG)

async def main():
    _, _, schema = await get_core_psychology_schema(1, {})
    llm_resp = {'ok': True, 'content': '''```json
{
  "core_psychology": [
    {
      "personality": {
        "big5": {
          "openness": 0.8,
          "conscientiousness": 0.8,
          "extraversion": 0.5,
          "agreeableness": 0.5,
          "neuroticism": 0.2
        },
        "values": [
          "интеллектуальное развитие",
          "творчество"
        ],
        "quirks": [
          "любит делиться фактами"
        ]
      },
      "needs": {"survival": 1.0, "safety": 1.0, "social": 0.5, "esteem": 0.5, "self_actualization": 0.8},
      "dark_triad": {"narcissism": 0.1, "machiavellianism": 0.1, "psychopathy": 0.1},
      "fears": ["неудача"],
      "motivations": ["найти партнера"],
      "achievements": ["успешная карьера"],
      "emotional_triggers": [{"trigger": "критика", "trigger_type": "situation", "reaction": "защищается", "intensity": 0.5}],
      "coping_mechanisms": [{"mechanism": "анализ", "adaptive": true, "frequency": "often"}],
      "religion": "agnostic",
      "worldview": "рационализм",
      "hobbies": ["спорт", "чтение"],
      "social_interactions": "интроверт",
      "self_perception": "умный",
      "relationship_style": "дистанцируется",
      "stress_management": "изоляция"
    }
  ]
}
```'''}
    
    try:
        parsed = await validate_and_parse_response(llm_resp, schema, "core_psychology")
        print("SUCCESS:\n", json.dumps(parsed, indent=2, ensure_ascii=False))
    except Exception as e:
        print("FAILED:\n", e)

asyncio.run(main())
