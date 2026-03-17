# app.services.schemas/batch_manifest.py

async def get_batch_manifest_schema(count):

    type = "manifest"
    system_instruction = f"""
        You are an Agent Director responsible for casting a diverse group of AI characters for a simulation.
        Required output: A JSON object with key "{type}" (list of agents) and "relationships" (social connections).
        
        PART 1: AGENTS
        Goal: Maximum Diversity.
        - Vary gender, age groups, roles/occupations, and personalities.
        - Ensure names are distinct.

        PART 2: RELATIONSHIPS
        Goal: Create a connected social graph.
        - Define connections between the agents you just generated (using their 0-based index).
        - Include a mix of: Friends, Colleagues, Family, Rivals, Neighbors.
        - 'context': The backstory of their relationship (e.g. "Childhood best friends", "Work in the same office", "Divorced couple").
        - 'rel_type': Must be one of [FRIEND, ENEMY, COLLEAGUE, FAMILY, SPOUSE, DATING, ACQUAINTANCE, NEUTRAL, KNOWS, NEIGHBOR].
        
        Output Structure:
        {{
            "manifest": [ ... {count} agents ... ],
            "relationships": [
                {{ "agent_index_1": 0, "agent_index_2": 3, "rel_type": "FRIEND", "context": "..." }},
                ...
            ]
        }}
    """

    schema_item = {
        "type": "object",
        "required": ["agent_name", "agent_role", "age", "gender", "key_trait", "distinctive_feature", "short_bio"],
        "additionalProperties": False,
        "properties": {
            "agent_name": {"type": "string"},
            "agent_role": {"type": "string"},
            "age": {"type": "integer"},
            "gender": {"type": "string"},
            "key_trait": {"type": "string"},
            "distinctive_feature": {"type": "string"},
            "short_bio": {"type": "string"}
        }
    }

    rel_item = {
        "type": "object",
        "required": ["agent_index_1", "agent_index_2", "rel_type", "context"],
        "additionalProperties": False,
        "properties": {
            "agent_index_1": {"type": "integer", "description": "Index of the first agent in the manifest list"},
            "agent_index_2": {"type": "integer", "description": "Index of the second agent in the manifest list"},
            "rel_type": {"type": "string", "enum": ["FRIEND", "ENEMY", "COLLEAGUE", "FAMILY", "SPOUSE", "DATING", "ACQUAINTANCE", "NEUTRAL", "KNOWS", "NEIGHBOR", "SOURCE"]},
            "context": {"type": "string"}
        }
    }

    schema = {
        "type": "object",
        "required": ["manifest", "relationships"],
        "additionalProperties": False,
        "properties": {
            "manifest": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_item
            },
            "relationships": {
                "type": "array",
                "items": rel_item
            }
        }
    }

    example = ""

    return system_instruction, example, schema
