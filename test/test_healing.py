import asyncio
import logging
import json
from app.services.validation.schema_utils import validate_and_parse_response
from app.services.schemas.core_demographics import get_core_demographics_schema

logging.basicConfig(level=logging.DEBUG)

async def main():
    _, _, schema = await get_core_demographics_schema(1)
    
    llm_resp = {'ok': True, 'content': '```json\n{"name": "Ivan Петров", "role": "Software Engineer", "age": 30, "gender": "male", "marital_status": "single", "education_level": "bachelor\'s degree", "income_level": "middle", "location": {"city": "Москва", "coordinates": {"latitude": 55.7558, "longitude": 37.6173}}, "favorite_spots": [{"name": "Gorky Park", "spot_type": "park", "lat": 55.7316, "lng": 37.6033, "backstory": "likes to walk", "emotional_attachment": 0.8, "visit_frequency": "weekly"}]}\n```'}
    
    try:
        parsed = await validate_and_parse_response(llm_resp, schema, "core_demographics")
        print("\n\nSUCCESS:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except Exception as e:
        print("\n\nFAILED:")
        print(e)

asyncio.run(main())
