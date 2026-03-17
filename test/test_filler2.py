import asyncio
from app.services.validation.schema_utils import _fill_missing_required
from app.services.schemas.core_psychology import get_core_psychology_schema
import json

async def main():
    _, _, schema = await get_core_psychology_schema(1, {})
    
    instance = {
        "core_psychology": [
            {
                "religion": "agnostic"
            }
        ]
    }
    
    filled = _fill_missing_required(instance, schema)
    print(json.dumps(filled, indent=2))

asyncio.run(main())
