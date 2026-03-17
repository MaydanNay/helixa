# src/modules/clients/community_agents/ai_people/create/auto/services/social_engine.py

import json
import logging
import random
from app.services.schemas.compatibility import get_compatibility_schema
from app.services.schemas.relationships import get_relationship_context_schema
from app.services.llm.retry import call_with_retries
from app.services.stage_generators import generate_field

async def calculate_compatibility(agent_a_cfg, agent_b_cfg, llm_call):
    """Calculates compatibility score and chemistry notes between two agents."""
    sys_inst, _, schema = await get_compatibility_schema()
    
    agent_a_brief = {
        "name": agent_a_cfg.get("agent_name"),
        "profile": agent_a_cfg.get("agent_profile"),
        "demographics": agent_a_cfg.get("agent_data", {}).get("demographics"),
        "psychology": agent_a_cfg.get("agent_data", {}).get("psychology")
    }
    
    agent_b_brief = {
        "name": agent_b_cfg.get("agent_name"),
        "profile": agent_b_cfg.get("agent_profile"),
        "demographics": agent_b_cfg.get("agent_data", {}).get("demographics"),
        "psychology": agent_b_cfg.get("agent_data", {}).get("psychology")
    }

    user_prompt = f"Analyze compatibility between:\nAgent A: {json.dumps(agent_a_brief, ensure_ascii=False)}\n\nAgent B: {json.dumps(agent_b_brief, ensure_ascii=False)}"
    
    try:
        # Using provided llm_call provider for social analysis
        resp, _ = await generate_field(sys_inst, user_prompt, schema, "compatibility", "compat_check", llm_call)
        return resp
    except Exception as e:
        logging.error(f"Compatibility calculation failed: {e}")
        return {"compatibility_score": 50, "chemistry_notes": "Unexpected error during analysis.", "potential_dynamic": "Neutral"}

async def create_batch_social_graph(batch_configs, llm_call, density=0.2):
    """
    Connects agents within a batch based on compatibility and density.
    Updates the configs in-place with relationship_context.
    """
    if len(batch_configs) < 2:
        return batch_configs

    # Number of connections to create
    num_agents = len(batch_configs)
    possible_pairs = [(i, j) for i in range(num_agents) for j in range(i + 1, num_agents)]
    num_connections = max(1, int(len(possible_pairs) * density))
    
    pairs_to_connect = random.sample(possible_pairs, min(num_connections, len(possible_pairs)))

    for i, j in pairs_to_connect:
        agent_a = batch_configs[i]
        agent_b = batch_configs[j]
        
        compat = await calculate_compatibility(agent_a, agent_b, llm_call)
        
        # Generate detailed relationship context
        sys_inst, _, schema = get_relationship_context_schema(1)
        
        # Simple heuristic for relation type based on compatibility
        score = compat.get("compatibility_score", 50)
        if score > 80: relation = "Close Friend"
        elif score > 60: relation = "Friend"
        elif score < 30: relation = "Rival"
        else: relation = "Acquaintance"

        user_prompt = (
            f"Create a '{relation}' relationship between {agent_a.get('agent_name')} and {agent_b.get('agent_name')}.\n"
            f"Compatibility analysis: {compat.get('chemistry_notes')}\n"
            f"Dynamic: {compat.get('potential_dynamic')}"
        )

        try:
            rel_data, _ = await generate_field(sys_inst, user_prompt, schema, "relationship_context", "batch_rel", llm_call)
            if isinstance(rel_data, list): rel_data = rel_data[0]
            
            # Add to both agents
            for agent, other in [(agent_a, agent_b), (agent_b, agent_a)]:
                if "relationships" not in agent["agent_data"]:
                    agent["agent_data"]["relationships"] = []
                
                agent["agent_data"]["relationships"].append({
                    "target_id": other.get("meta", {}).get("agent_id") or f"batch_agent_{batch_configs.index(other)}",
                    "target_name": other.get("agent_name"),
                    "relation_type": relation,
                    "compatibility_score": score,
                    "details": rel_data
                })
        except Exception as e:
            logging.error(f"Failed to generate relationship between {i} and {j}: {e}")

    return batch_configs
