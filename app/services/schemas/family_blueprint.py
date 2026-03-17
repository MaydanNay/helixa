# app.services.schemas/family_blueprint.py

from typing import Dict, Any, Tuple, List

async def get_family_blueprint_schema(count_approx: int) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Returns the system prompt and JSON schema for generating a Family Blueprint (Graph).
    """
    
    system_instruction = (
        "You are an expert sociologist and screenwriter. Your task is to design a cohesive, realistic family structure.\n"
        "You must output a JSON object containing a list of family members with their roles and relationships.\n"
        "Think about family dynamics, consistent ages, and interesting backstories."
    )
    
    example_output = {
        "family_name": "Kim",
        "scenario_description": "A wealthy banking family dealing with succession crisis.",
        "members": [
            {
                "temp_id": "dad",
                "role": "Father",
                "name": "Dae-Jung",
                "age": 55,
                "gender": "Male",
                "key_traits": ["Strict", "Workaholic", "Traditional"],
                "relationships": []
            },
            {
                "temp_id": "mom",
                "role": "Mother",
                "name": "Soo-Jin",
                "age": 52,
                "gender": "Female",
                "key_traits": ["Diplomatic", "Art lover"],
                "relationships": [{"target_id": "dad", "relation": "Husband"}]
            },
            {
                "temp_id": "son",
                "role": "Son",
                "name": "Min-Ho",
                "age": 25,
                "gender": "Male",
                "key_traits": ["Rebellious", "Tech-savvy"],
                "relationships": [{"target_id": "dad", "relation": "Father"}, {"target_id": "mom", "relation": "Mother"}]
            }
        ]
    }
    
    schema = {
        "type": "object",
        "properties": {
            "family_name": {"type": "string", "description": "Shared last name for the core family"},
            "scenario_description": {"type": "string", "description": "Brief description of the family vibe/story"},
            "members": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "temp_id": {"type": "string", "description": "Short unique ID for internal linking (e.g. 'm1', 'f1')"},
                        "role": {"type": "string", "description": "Family role (Father, Cousin, Grandmother, etc.)"},
                        "name": {"type": "string", "description": "First Name"},
                        "age": {"type": "integer"},
                        "gender": {"type": "string", "enum": ["Male", "Female"]},
                        "key_traits": {"type": "array", "items": {"type": "string"}, "description": "3-4 personality adjectives"},
                        "occupation": {"type": "string", "description": "Job or main activity"},
                        "relationships": {
                            "description": "List or Dict of relationships",
                            "anyOf": [
                                {"type": "array", "items": {"type": "object"}},
                                {"type": "object"}
                            ]
                        }
                    },
                    "required": []
                }
            }
        },
        "required": ["family_name", "members"]
    }
    
    return system_instruction, example_output, schema
