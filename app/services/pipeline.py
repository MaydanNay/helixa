import logging
import json
import asyncio
import uuid
from typing import Dict, Any, Optional

from .gemini_client import gemini_client
from .utils import _truncate, calculate_biorhythms, extract_stage
from .llm.retry import call_with_retries
from .consensus_service import ConsensusService
from .qdrant_client import memory_service
from ..config import settings

# Import Stage Schemas
from app.services.schemas.core_demographics import get_core_demographics_schema
from app.services.schemas.core_psychology import get_core_psychology_schema
from app.services.schemas.core_health import get_core_health_schema
from app.services.schemas.core_biography import get_core_biography_schema
from app.services.schemas.experience import get_experience_schema
from app.services.schemas.family import get_family_schema
from app.services.schemas.voice import get_voice_schema
from app.services.schemas.sociology import get_soc_part1_schema, get_soc_part2_schema
from app.services.schemas.behavioral_main import get_behavioral_main_schema
from app.services.schemas.behavioral_details import get_behavioral_details_schema
from app.services.schemas.financial import get_fin_part1_schema, get_fin_part2_schema
from app.services.schemas.planning import get_planning_strategy_schema, get_planning_routine_schema, get_planning_day_schema
from app.services.schemas.memory import get_mem_part1_schema, get_mem_part2_schema, get_mem_part3_schema
from app.services.schemas.relationships import get_relationship_context_schema
from app.services.schemas.appearance import get_appearance_schema
from app.services.schemas.private import get_private_schema
from app.services.schemas.cognitive_profile import get_cognitive_profile_schema

from app.services.schemas.editor import get_consistency_editor_schema
from app.services.stage_generators import generate_field
from app.services.judge_service import generate_field_with_judge
from app.services.validation.schema_utils import ensure_schema_valid

logger = logging.getLogger(__name__)

# Feature flag: set ENABLE_CONSENSUS=false in .env to skip consensus review
# Useful for cheaper/faster providers where repeated LLM calls are expensive
ENABLE_CONSENSUS = getattr(settings, "enable_consensus", "true").lower() != "false"

# Feature flag: ENABLE_JUDGE=true → all stages use Super Judge (3 models + synthesis)
# Set ENABLE_JUDGE=false to revert to single-model generation (faster, fewer requests)
ENABLE_JUDGE = getattr(settings, "enable_judge", "true").lower() != "false"

# Per-stage temperature tuning:
#   低 (factual/schema-heavy) — precision over creativity
#   高 (narrative/character)  — richness over precision
STAGE_TEMPERATURES: dict = {
    # --- Factual / structured (increased for diversity) ---
    "core_demographics":    0.85,   # names, dates, nationality — concrete facts
    "demographics":         0.85,
    "financial":            0.60,   # numbers, budgets — strict
    "fin_p1":               0.60,
    "fin_p2":               0.60,
    "memory":               0.60,   # episodic facts — semi-structured
    "mem_p1":               0.60,
    "mem_p2":               0.65,
    "mem_p3":               0.65,
    "health":               0.50,   # medical / wellness data
    "core_health":          0.50,
    "experience":           0.65,   # CV-style history
    "planning_strategy":    0.60,   # goals & plans — logical
    "planning_routine":     0.65,
    "planning_day":         0.65,
    "plan_p1":              0.60,
    "plan_p2":              0.65,
    "plan_p3":              0.65,
    "appearance_details":   0.65,   # physical traits
    "appearance":           0.65,
    # --- Character / narrative ---
    "core_psychology":      0.80,   # personality nuances — creative
    "psychology":           0.80,
    "behavioral_main":      0.75,   # habits & patterns
    "behavioral":           0.75,
    "behavioral_details":   0.78,
    "behavioral_ext":       0.78,
    "sociology":            0.72,   # social dynamics
    "soc_p1":               0.72,
    "soc_p2":               0.72,
    "relationship_context": 0.72,
    "relations":            0.72,
    "voice_dna":            0.85,   # speech style — most creative
    "voice":                0.85,
    "core_biography":       0.88,   # life story — rich narrative
    "biography":            0.88,
    "family":               0.70,   # family dynamics
    "private":              0.90,   # secrets / intimate details — max creativity
    # --- Editor (consistency pass) — precision needed ---
    "editor":               0.30,
    "consistency_editor":   0.30,
    "cognitive_profile":    0.70,   # logic/limitations — balanced
}
DEFAULT_TEMPERATURE = 0.70   # fallback if stage not in map


# Stage-Model Specialization:
#   Gemma 3 excels at character depth, voice, and psychology.
#   Qwen 3 excels at broad knowledge, culture, and social structures.
#   GPT-OSS is a strong generalist for demographics and facts.
STAGE_MODEL_MAPPING: dict = {
    # --- Character / Personality (Alem Plus & Gemma 3) ---
    "psychology":           "alemllm",
    "core_psychology":      "alemllm",
    "voice":                "alemllm",
    "voice_dna":            "alemllm",
    "behavioral":           "qwen3",
    "behavioral_main":      "qwen3",
    "behavioral_details":   "qwen3",
    "behavioral_ext":       "qwen3",
    "private":              "gpt-oss",
    "archetype_selector":   "gpt-oss",
    "core_demographics":    "gpt-oss",
    "appearance":           "gpt-oss",
    "editor":               "gpt-oss",
    
    # --- Narrative / History (Qwen 3 & Alem Plus) ---
    "biography":            "alemllm",
    "core_biography":       "alemllm",
    "sociology":            "qwen3",
    "family":               "alemllm",
    "experience":           "alemllm",
    "relationship_context": "gemma3", 
    "relationships":        "gemma3",
    "soc_p1":               "qwen3",
    "soc_p2":               "qwen3",
    
    # --- Planning & Routines (Qwen 3) ---
    "planning_strategy":    "qwen3",
    "planning_routine":     "qwen3",
    "planning_day":         "qwen3",
    "plan_p1":              "qwen3",
    "plan_p2":              "qwen3",
    "plan_p3":              "qwen3",
    "cognitive_profile":    "gpt-oss",
}
DEFAULT_MODEL = settings.generator_provider


async def _gen(sys_inst, prompt, schema, field_name, w_name, llm_call_fn, identity: Optional[Dict[str, Any]] = None):
    """Wrapper: routes to Super Judge or single-model generate_field based on ENABLE_JUDGE.
    Automatically applies per-stage temperature and primary model specialization.
    Also injects identity summary if identity dict is provided.
    """
    temp = STAGE_TEMPERATURES.get(field_name) or STAGE_TEMPERATURES.get(w_name) or DEFAULT_TEMPERATURE
    primary = STAGE_MODEL_MAPPING.get(field_name) or STAGE_MODEL_MAPPING.get(w_name) or DEFAULT_MODEL
    
    # Inject identity summary to maintain consistency between stages
    summary = ""
    if identity:
        summary = _get_identity_summary(identity)
    
    full_prompt = (summary + "\n" + prompt).strip() if summary else prompt

    if ENABLE_JUDGE:
        # Judge runs its own 3 parallel models (JUDGE_MODELS)
        # We pass settings.judge_provider (o4-mini) to perform the final synthesis.
        return await generate_field_with_judge(
            sys_inst, full_prompt, schema, field_name, w_name, 
            temperature=temp, primary_model=settings.judge_provider
        )
    
    # Fallback/Single-model mode: Bind the correct temperature and SPECIALIZED provider to the caller
    async def llm_with_options(s, p, ws, wn):
        return await llm_call_fn(s, p, ws, wn, temperature=temp, provider=primary)
        
    obj, data = await generate_field(sys_inst, full_prompt, schema, field_name, w_name, llm_with_options)

    # --- STAGE 5 IMPROVEMENT: SECOND PASS (Refinement) ---
    # If the generated data is suspiciously short or generic, trigger a refinement pass.
    # threshold = 150 chars of JSON text as a proxy for "thin" content
    try:
        content_str = json.dumps(data, ensure_ascii=False)
        if len(content_str) < 150 and field_name not in ["core_demographics", "appearance", "core_health", "financial", "memory", "planning_strategy", "planning_routine"]:
            logger.info(f" - [REFINEMENT] Stage {field_name} seems thin ({len(content_str)} chars). Triggering second pass.")
            refine_prompt = f"The previous response for {field_name} was too brief. Please expand on this, adding more emotional depth, specific details, and psychological nuance that fits the character's background.\n\nPREVIOUS DATA:\n{content_str}"
            obj_ref, data_ref = await generate_field(sys_inst, refine_prompt, schema, field_name, w_name + "_refine", llm_with_options)
            return obj_ref, data_ref
    except Exception as re:
        logger.warning(f"Refinement pass failed for {field_name}: {re}")

    return obj, data



async def _consensus(data, stage_name, schema, sys_prompt, agent_id, profile_context):
    """Conditionally run ConsensusService based on ENABLE_CONSENSUS flag.
    BYPASS if ENABLE_JUDGE is active, as the judge already handles synthesis.
    """
    if not ENABLE_CONSENSUS or ENABLE_JUDGE:
        return data
    return await ConsensusService.review_and_refine(
        data, stage_name, schema, sys_prompt,
        agent_id=agent_id,
        profile_context=profile_context
    )


async def _rate_agent_quality(identity: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Uses LLM to perform a high-level audit of the generated character.
    Returns a score (1-10) and a brief review.
    """
    try:
        sys_auditor = "You are a Master Character Auditor. Rate the provided AI agent profile for depth, uniqueness, and internal consistency."
        prompt = f"""
Review the full profile of the agent: {identity.get('archetype', 'Unknown')}
AGENT DATA:
{json.dumps(identity, ensure_ascii=False)[:6000]}

Score the agent on a scale of 1-10:
- 1-3: Generic, thin, boring, or contradictory.
- 4-6: Solid, standard character.
- 7-10: Exceptional, deeply interesting, unique personality.

Return ONLY a JSON object:
{{
  "score": <int>,
  "review": "<brief string why this score was given>",
  "suggestions": ["<improvement1>", ...]
}}
"""
        res = await call_with_retries(sys_auditor, prompt, None, "auditor", attempts=2, provider=provider, temperature=0.3)
        if res.get("ok") and res.get("output_text"):
            import re
            match = re.search(r'\{.*\}', res["output_text"], re.DOTALL)
            if match:
                score_data = json.loads(match.group(0))
                return score_data
    except Exception as ae:
        logger.warning(f"Quality audit failed: {ae}")
    return {"score": 5, "review": "Auto-assigned (audit failed)", "suggestions": []}


async def _index_fragment(agent_id: str, stage: str, data: Any) -> None:
    """Vectorise and store a generated stage fragment in Qdrant so later
    stages can retrieve it via RAG."""
    try:
        col_name = f"agent_memory_{agent_id}"
        text = f"[{stage.upper()}]\n{json.dumps(data, ensure_ascii=False)[:3000]}"
        vector = await gemini_client.generate_embedding(text)
        if vector:
            await memory_service.add_memory(col_name, text, vector, {"type": "stage", "stage": stage})
    except Exception as e:
        logger.warning(" - [FALLBACK] RAG index failed for stage [%s]: %s", stage, e)



async def _rag_context(agent_id: str, stage: str) -> str:
    """Pull relevant fragments from Qdrant memory for the given stage."""
    try:
        col_name = f"agent_memory_{agent_id}"
        results = await memory_service.search_memory(
            col_name, f"Facts relevant to {stage}", limit=4
        )
        if results:
            return "\n\n=== CONTEXT FROM PREVIOUS STAGES ===\n" + "\n".join(
                [r.get("text", "")[:500] for r in results]
            )
    except Exception as e:
        logger.warning(" - [FALLBACK] RAG context fetch failed for [%s]: %s", stage, e)

    return ""

from .archetypes import get_random_archetype, get_archetype_by_name, ARCHETYPES

async def _select_archetype(name: Optional[str], role: Optional[str], personality: Optional[str], provider: str, seed: Optional[str] = None) -> Dict[str, Any]:
    """Selects the best fitting archetype from the library based on user hints.
    Injects seed to ensure uniqueness in parallel batch calls.
    """
    if not any([name, role, personality]):
        return get_random_archetype()

    try:
        archetypes_list = "\n".join([f"- {a['name']}: {a['vibe']}" for a in ARCHETYPES])
        sys_inst = "You are a Master Character Architect. Your task is to select the perfect Archetype for a new character based on user-provided hints."
        prompt = f"""
HINTS FROM USER:
Name: {name or 'Not specified'}
Role: {role or 'Not specified'}
Personality: {personality or 'Not specified'}

LIBRARY OF ARCHETYPES:
{archetypes_list}

Strictly select ONE archetype from the list that is a compelling fit for the hints. 

DIVERSITY REQUIREMENT: If this is a batch generation, AVOID the most obvious or stereotypic choices. For example, if the theme is "Cyberpunk", don't just pick "The Disillusioned Visionary" every time. Maybe a "Gentle Nurturer" in a cyberpunk world is more interesting. 

RANDOM SEED: {seed or 'N/A'} (Use this to strictly vary your choices across different calls).

Return ONLY a JSON object:
{{
  "selected_name": "<name of the archetype>"
}}
"""
        target_model = STAGE_MODEL_MAPPING.get("archetype_selector", provider)
        res = await call_with_retries(sys_inst, prompt, None, "archetype_selector", attempts=2, provider=target_model, temperature=0.8)
        if res.get("ok") and res.get("output_text"):
            import re
            match = re.search(r'\{.*\}', res["output_text"], re.DOTALL)
            if match:
                selected_data = json.loads(match.group(0))
                found = get_archetype_by_name(selected_data.get("selected_name"))
                if found:
                    return found
    except Exception as e:
        logger.warning(f"Smart archetype selection failed: {e}")
    
    return get_random_archetype()


def _get_identity_summary(identity: Dict[str, Any]) -> str:
    """Extracts key character facts discovered so far for prompt injection.
    Aligned with real schema fields in core_demographics.py and core_psychology.py.
    """
    parts = []
    
    # Archetype is the "North Star"
    arc = identity.get("archetype_data")
    if arc:
        parts.append(f"ARCHETYPE: {arc.get('name')} ({arc.get('vibe')})")
        parts.append(f"INTERNAL CONFLICT: {arc.get('internal_conflict', 'Not set')}")
        parts.append(f"SPEECH PATTERN: {arc.get('speech_patterns', 'Not set')}")
        parts.append(f"PARADOX: {arc.get('paradox', 'Not set')}")
        parts.append(f"CORE BEHAVIOR SEED: {arc.get('seed_prompt')}")

    demo = identity.get("demographics", {})
    if demo:
        # From core_demographics.py
        name = f"{demo.get('agent_name', '')} {demo.get('last_name', '')}".strip()
        if name: parts.append(f"Identity: {name}")
        role = demo.get('agent_role')
        if role: parts.append(f"Role: {role}")
        
        inner_demo = demo.get('demographics', {})
        if inner_demo:
            if "age" in inner_demo: parts.append(f"Age: {inner_demo['age']}")
            if "gender" in inner_demo: parts.append(f"Gender: {inner_demo['gender']}")
            city = inner_demo.get('city')
            if city: parts.append(f"Location: {city}")
    
    psych = identity.get("psychology", {})
    if psych:
        # From core_psychology.py
        char = psych.get("character")
        if char: parts.append(f"Character: {char}")
        values = psych.get("core_values", [])
        if values and isinstance(values, list):
            parts.append(f"Values: {', '.join(map(str, values[:3]))}")

    bio = identity.get("biography", {})
    if bio:
        # From core_biography.py (usually origin_story)
        story = bio.get("origin_story", "")
        if story:
            parts.append(f"Background: {_truncate(story, 150)}")

    cog = identity.get("cognitive_profile", {})
    if cog:
        # From cognitive_profile.py
        edu = cog.get("education_level")
        if edu: parts.append(f"Education: {edu}")
        blind = cog.get("blind_spots", [])
        if blind: parts.append(f"Blind Spots (Ignorant of): {', '.join(blind)}")
        depth = cog.get("analytical_depth")
        if depth: parts.append(f"Analytical Depth: {depth}")
        bias = cog.get("bias_weights", {})
        if bias:
            parts.append(f"Biases (Weights 0-1): SunkCost={bias.get('sunk_cost_fallacy')}, Bandwagon={bias.get('bandwagon_effect')}")
        impulse = cog.get("impulse_control")
        if impulse is not None:
            parts.append(f"Impulse Control: {impulse}")

    if not parts:
        return ""
    return "\nPROVISIONAL CHARACTER SUMMARY (DO NOT CONTRADICT):\n" + " | ".join(parts) + "\n"


async def generate_vivida_soul(
    name_hint: Optional[str] = None,
    role_hint: Optional[str] = None,
    personality_hint: Optional[str] = None,
    country_hint: Optional[str] = None,
    city_hint: Optional[str] = None,
    criteria: Optional[Dict[str, Any]] = None,
    provider: str = settings.generator_provider,
    stage_callback = None,
    agent_id: Optional[str] = None,   # Pass the real DB UUID to align Qdrant collection
) -> Dict[str, Any]:
    """
    Phase 1: Generates the 'Soul' (Stages 1-13).
    Includes psychology, biography, sociology, and core memory.
    """
    logger.info("Starting Soul Generation for hints: %s, %s", name_hint, role_hint)
    
    identity = {
        # Use the provided DB UUID if given; otherwise generate a temporary one.
        # This ensures the Qdrant collection name matches what the worker and delete
        # endpoint will look for (agent_memory_{db_agent_id}).
        "agent_id": agent_id or str(uuid.uuid4()),
        "meta": {"version": "vivida-1.1"}
    }
    
    location_text = ""
    if country_hint or city_hint:
        location_text = f", Location: {city_hint or ''} {country_hint or ''}".strip(", ")
    
    # Inject randomness to ensure LLM doesn't generate identical demographic profiles for empty hints
    random_seed = str(uuid.uuid4())
    context_text = f"Name: {name_hint}, Role: {role_hint}, Personality Selection: {personality_hint}{location_text}, Generation Seed: {random_seed}"
    criteria_text = json.dumps(criteria or {}, ensure_ascii=False)

    async def llm_call(sys, prompt, w_schema, w_name, temperature=0.7, **kwargs):
        target_provider = kwargs.pop("provider", provider)
        return await call_with_retries(
            sys, prompt, w_schema, wrapper_name=w_name,
            attempts=3, timeout=600, provider=target_provider,
            temperature=temperature, **kwargs
        )

    # --- INITIALIZE MEMORY ---
    col_name = f"agent_memory_{identity['agent_id']}"
    try:
        await memory_service.init_collection(col_name)
    except Exception as ie:
        logger.warning(f"Failed to pre-init memory collection: {ie}")

    # --- STAGE 0: ARCHETYPE SEED ---
    # Smart selection based on hints
    archetype = await _select_archetype(name_hint, role_hint, personality_hint, provider, seed=random_seed)
    identity["archetype"] = archetype["name"]
    identity["archetype_data"] = archetype
    logger.info(f"ARCHETYPE SELECTED (SMART): {archetype['name']} for new agent.")

    # --- STAGE 1: DEMOGRAPHICS ---
    if stage_callback: await stage_callback("demographics", "running")
    sys1, _, schema1 = await get_core_demographics_schema(1)
    prompt1 = f"Generate core demographics based on: {context_text}. Criteria: {criteria_text}"
    res1 = await _gen(sys1, prompt1, ensure_schema_valid(schema1, "core_demographics"), "core_demographics", "demographics", llm_call, identity=identity)
    obj1 = res1[0]
    demographics = extract_stage(obj1, "core_demographics")
    identity["demographics"] = demographics
    
    # Set top-level identifiers for easier persistence and reference
    identity["agent_name"] = demographics.get("agent_name")
    identity["agent_role"] = demographics.get("agent_role")
    
    await _index_fragment(identity["agent_id"], "demographics", demographics)
    if stage_callback: await stage_callback("demographics", "done", data=demographics)
    
    # --- STAGE 2: PSYCHOLOGY ---
    if stage_callback: await stage_callback("psychology", "running")
    rag2 = await _rag_context(identity["agent_id"], "psychology")
    sys2, _, schema2 = await get_core_psychology_schema(1, demographics)
    prompt2 = f"Generate deep psychology profile based on selection: {personality_hint}{rag2}"
    res2 = await _gen(sys2, prompt2, ensure_schema_valid(schema2, "core_psychology"), "core_psychology", "psychology", llm_call, identity=identity)
    obj2 = res2[0]
    psychology = extract_stage(obj2, "core_psychology")
    psychology = await _consensus(psychology, "psychology", schema2, sys2, str(identity["agent_id"]), json.dumps(demographics, ensure_ascii=False))
    identity["psychology"] = psychology
    await _index_fragment(str(identity["agent_id"]), "psychology", psychology)
    if stage_callback: await stage_callback("psychology", "done", data=psychology)

    # --- STAGE 2.5: COGNITIVE PROFILE (Artificial Ignorance) ---
    if stage_callback: await stage_callback("cognitive_profile", "running")
    sys_cog, _, schema_cog = await get_cognitive_profile_schema(1, demographics)
    prompt_cog = f"Generate cognitive limitations and blind spots based on demographics and role: {demographics.get('agent_role')}."
    res_cog = await _gen(sys_cog, prompt_cog, ensure_schema_valid(schema_cog, "cognitive_profile"), "cognitive_profile", "cognitive_profile", llm_call, identity=identity)
    cog_profile = extract_stage(res_cog[0], "cognitive_profile")
    identity["cognitive_profile"] = cog_profile
    await _index_fragment(identity["agent_id"], "cognitive_profile", cog_profile)
    if stage_callback: await stage_callback("cognitive_profile", "done", data=cog_profile)

    # --- STAGE 3: HEALTH & BIORHYTHMS ---
    if stage_callback: await stage_callback("health", "running")
    rag3 = await _rag_context(identity["agent_id"], "health")
    context_health = {**demographics, **psychology}
    sys3, _, schema3 = await get_core_health_schema(1, context_health)
    prompt3 = f"Generate physical health profile.{rag3}"
    obj3, _ = await _gen(sys3, prompt3, ensure_schema_valid(schema3, "core_health"), "core_health", "health", llm_call, identity=identity)
    health = extract_stage(obj3, "core_health")
    try:
        health["energy_cycle"] = calculate_biorhythms(health.get("chronotype", "hummingbird"))
    except Exception as be:
        logger.warning(f"Biorhythm calculation failed: {be}")
    health = await _consensus(health, "health", schema3, sys3, identity["agent_id"], json.dumps({**demographics, **psychology}, ensure_ascii=False))
    identity["health"] = health
    await _index_fragment(str(identity["agent_id"]), "health", health)
    if stage_callback: await stage_callback("health", "done", data=health)

    # --- STAGE 4: BIOGRAPHY ---
    if stage_callback: await stage_callback("biography", "running")
    rag4 = await _rag_context(identity["agent_id"], "biography")
    ctx_bio = {**demographics, **psychology, **health}
    sys4, _, schema4 = await get_core_biography_schema(1, ctx_bio)
    prompt4 = f"Write a consistent biography and life story.{rag4}"
    obj4, _ = await _gen(sys4, prompt4, ensure_schema_valid(schema4, "core_biography"), "core_biography", "biography", llm_call, identity=identity)
    biography = extract_stage(obj4, "core_biography")
    biography = await _consensus(biography, "biography", schema4, sys4, identity["agent_id"], json.dumps({**demographics, **psychology}, ensure_ascii=False))
    identity["biography"] = biography
    await _index_fragment(identity["agent_id"], "biography", biography)
    if stage_callback: await stage_callback("biography", "done", data=biography)

    # --- STAGE 5: FAMILY ---
    if stage_callback: await stage_callback("family", "running")
    rag5 = await _rag_context(identity["agent_id"], "family")
    sys_fam, _, schema_fam = await get_family_schema(1, identity)
    prompt_fam = f"Generate family history and current status.{rag5}"
    obj_fam, _ = await _gen(sys_fam, prompt_fam, ensure_schema_valid(schema_fam, "family"), "family", "family", llm_call, identity=identity)
    family = extract_stage(obj_fam, "family")
    family = await _consensus(family, "family", schema_fam, sys_fam, identity["agent_id"], json.dumps(demographics, ensure_ascii=False))
    identity["family"] = family
    await _index_fragment(identity["agent_id"], "family", family)
    if stage_callback: await stage_callback("family", "done", data=family)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STAGES 6-10 run IN PARALLEL — all depend on biography but not each other
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    logger.info("Starting parallel stages: experience, behavioral, sociology, voice, financial")

    async def _gen_experience(snap):
        rag6 = await _rag_context(snap["agent_id"], "experience")
        sys5, _, schema5 = await get_experience_schema(1, snap)
        obj5, _ = await _gen(sys5, f"Generate professional experience and skills.{rag6}", ensure_schema_valid(schema5, "experience"), "experience", "experience", llm_call, identity=identity)
        exp = extract_stage(obj5, "experience")
        exp = await _consensus(exp, "experience", schema5, sys5, snap["agent_id"], json.dumps({**demographics, **psychology}, ensure_ascii=False))
        await _index_fragment(snap["agent_id"], "experience", exp)
        if stage_callback: await stage_callback("experience", "done", data=exp)
        return exp

    async def _gen_behavioral(snap):
        rag7 = await _rag_context(snap["agent_id"], "behavioral")
        sys6, _, schema6 = await get_behavioral_main_schema(1, snap)
        obj6, _ = await _gen(sys6, f"Generate detailed behavioral patterns and consumer habits.{rag7}", ensure_schema_valid(schema6, "behavioral_main"), "behavioral_main", "behavioral", llm_call, identity=identity)
        behav = extract_stage(obj6, "behavioral_main")
        behav = await _consensus(behav, "behavioral", schema6, sys6, snap["agent_id"], json.dumps(snap["demographics"], ensure_ascii=False))
        await _index_fragment(snap["agent_id"], "behavioral", behav)
        # behavioral_details runs after main
        sys6b, _, schema6b = await get_behavioral_details_schema(1, snap)
        obj6b, _ = await _gen(sys6b, "Generate granular behavioral preferences and tastes.", ensure_schema_valid(schema6b, "behavioral_details"), "behavioral_details", "behavioral_ext", llm_call, identity=identity)
        behav.update(extract_stage(obj6b, "behavioral_details"))
        if stage_callback: await stage_callback("behavioral", "done", data=behav)
        return behav

    async def _gen_sociology(snap):
        rag8 = await _rag_context(snap["agent_id"], "sociology")
        sys_soc1, _, schema_soc1 = await get_soc_part1_schema(1, snap)
        res_soc1 = await _gen(sys_soc1, f"Generate Sociology Part 1: Communication style.{rag8}", ensure_schema_valid(schema_soc1, "sociology"), "sociology", "soc_p1", llm_call, identity=identity)
        soc_p1 = extract_stage(res_soc1[0], "sociology")
        snap_with_soc = {**snap, "sociology": soc_p1}
        sys_soc2, _, schema_soc2 = await get_soc_part2_schema(1, snap_with_soc)
        obj_soc2, _ = await _gen(sys_soc2, "Generate Sociology Part 2: Social Network & Relationships.", ensure_schema_valid(schema_soc2, "sociology"), "sociology", "soc_p2", llm_call, identity=identity)
        soc_p2 = extract_stage(obj_soc2, "sociology")
        soc_p1 = await _consensus(soc_p1, "sociology_part1", schema_soc1, sys_soc1, snap["agent_id"], json.dumps(snap["demographics"], ensure_ascii=False))
        soc_p2 = await _consensus(soc_p2, "sociology_part2", schema_soc2, sys_soc2, snap["agent_id"], json.dumps(snap["demographics"], ensure_ascii=False))
        merged = {**soc_p1, **soc_p2}
        # relationships context
        sys_rel, _, schema_rel = get_relationship_context_schema(1)
        res_rel = await _gen(sys_rel, "Define the social relationship dynamics and shared history context.", ensure_schema_valid(schema_rel, "relationship_context"), "relationship_context", "relations", llm_call, identity=identity)
        merged["relationships_context"] = extract_stage(res_rel[0], "relationship_context")
        await _index_fragment(str(snap["agent_id"]), "sociology", merged)
        if stage_callback: await stage_callback("sociology", "done", data=merged)
        return merged

    async def _gen_voice(snap):
        rag9 = await _rag_context(snap["agent_id"], "voice")
        sys_v, _, schema_v = get_voice_schema(1)
        obj_v, _ = await _gen(sys_v, f"Generate Voice DNA parameters.{rag9}", ensure_schema_valid(schema_v, "voice_dna"), "voice_dna", "voice", llm_call, identity=identity)
        v = extract_stage(obj_v, "voice_dna")
        v = await _consensus(v, "voice_dna", schema_v, sys_v, snap["agent_id"], json.dumps({"demographics": demographics, "psychology": psychology}, ensure_ascii=False))
        await _index_fragment(snap["agent_id"], "voice", v)
        if stage_callback: await stage_callback("voice", "done", data=v)
        return v

    async def _gen_financial(snap):
        rag10 = await _rag_context(snap["agent_id"], "financial")
        sys_f1, _, schema_f1 = await get_fin_part1_schema(1, snap)
        obj_f1, _ = await _gen(sys_f1, f"Generate Financial Part 1: Status & Income.{rag10}", ensure_schema_valid(schema_f1, "financial"), "financial", "fin_p1", llm_call, identity=identity)
        fin_p1 = extract_stage(obj_f1, "financial")
        snap_fin = {**snap, "financial": fin_p1}
        sys_f2, _, schema_f2 = await get_fin_part2_schema(1, snap_fin)
        obj_f2, _ = await _gen(sys_f2, "Generate Financial Part 2: Spending habits & Strategy.", ensure_schema_valid(schema_f2, "financial"), "financial", "fin_p2", llm_call, identity=identity)
        fin_p2 = extract_stage(obj_f2, "financial")
        fin_p1 = await _consensus(fin_p1, "financial_part1", schema_f1, sys_f1, snap["agent_id"], json.dumps(snap["demographics"], ensure_ascii=False))
        fin_p2 = await _consensus(fin_p2, "financial_part2", schema_f2, sys_f2, snap["agent_id"], json.dumps(snap["demographics"], ensure_ascii=False))
        merged = {**fin_p1, **fin_p2}
        await _index_fragment(snap["agent_id"], "financial", merged)
        if stage_callback: await stage_callback("financial", "done", data=merged)
        return merged

    # Take a snapshot of identity at this point (biography done) for parallel stages
    identity_snap = dict(identity)
    for s in ["experience", "behavioral", "sociology", "voice", "financial"]:
        if stage_callback: await stage_callback(s, "running")

    results = await asyncio.gather(
        _gen_experience(identity_snap),
        _gen_behavioral(identity_snap),
        _gen_sociology(identity_snap),
        _gen_voice(identity_snap),
        _gen_financial(identity_snap),
        return_exceptions=True,  # Don't let one failed stage kill the whole generation
    )
    
    stage_names = ["experience", "behavioral", "sociology", "voice", "financial"]
    for stage_name, result in zip(stage_names, results):
        if isinstance(result, Exception):
            logger.error(f"Parallel stage '{stage_name}' failed: {result}. Using empty fallback.")
            if stage_callback: await stage_callback(stage_name, "error")
            identity[stage_name] = {}
        else:
            identity[stage_name] = result

    experience = identity["experience"]
    behavioral = identity["behavioral"]
    sociology = identity["sociology"]
    voice = identity["voice"]
    financial = identity["financial"]
    identity["financial"] = financial

    # for s in ["experience", "behavioral", "sociology", "voice", "financial"]:
    #     if stage_callback: await stage_callback(s, "done")

    logger.info("Parallel stages 6-10 complete")

    # --- STAGE 11: MEMORY (Core Semantic only for DNA) ---
    if stage_callback: await stage_callback("memory", "running")
    identity["memory"] = await _generate_core_memory(identity, llm_call, stage_callback=stage_callback)

    # --- STAGE 12: PRIVATE DATA ---
    if stage_callback: await stage_callback("private", "running")
    rag_priv = await _rag_context(identity["agent_id"], "private")
    sys_priv, _, schema_priv = await get_private_schema(1, identity)
    prompt_priv = f"Generate personal secrets and private motivations.{rag_priv}"
    obj_priv, _ = await _gen(sys_priv, prompt_priv, ensure_schema_valid(schema_priv, "private"), "private", "private", llm_call, identity=identity)
    private_data = extract_stage(obj_priv, "private")
    private_data = await _consensus(private_data, "private", schema_priv, sys_priv, identity["agent_id"], json.dumps({"psychology": psychology, "biography": identity.get("biography", {})}, ensure_ascii=False))
    identity["private"] = private_data
    await _index_fragment(identity["agent_id"], "private", private_data)
    if stage_callback: await stage_callback("private", "done", data=private_data)

    # --- STAGED PLANNING REMOVED (now strictly in lifecycle phase) ---

    # --- STAGE 13: CONSISTENCY EDITOR (FINAL POLISH) ---
    if stage_callback: await stage_callback("editor", "running")
    logger.info("Running Consistency Editor (Final Polish)")
    try:
        from app.services.utils import normalize_llm_json_text
        sys_ed, _, schema_ed = await get_consistency_editor_schema(identity)
        profile_json_str = json.dumps(identity, ensure_ascii=False)
        prompt_ed = f"Review the full following profile and fix any chronological or psychological inconsistencies. Return corrected JSON.\n\nPROFILE:\n{profile_json_str}"
        temp_ed = STAGE_TEMPERATURES.get("editor", 0.3)
        # Increase max_tokens significantly for the editor as it must return a huge full profile
        fixed_res = await llm_call(sys_ed, prompt_ed, None, "editor", temperature=temp_ed, max_tokens=16000)
        if fixed_res.get("ok") and fixed_res.get("output_text"):
            txt = fixed_res["output_text"]
            # Use normalize_llm_json_text which handles markdown blocks + truncation repair
            normalized = normalize_llm_json_text(txt)
            try:
                fixed_json = json.loads(normalized)
                parsed_identity = fixed_json.get("agent_data") or fixed_json
                if isinstance(parsed_identity, dict) and "demographics" in parsed_identity and "psychology" in parsed_identity:
                    # Carefully update identity to avoid losing system fields like agent_id
                    for k, v in parsed_identity.items():
                        if k not in ["agent_id", "created_at", "user_id", "status"]:
                            identity[k] = v
                    logger.info("Consistency Editor successfully polished the profile while preserving system fields.")
                else:
                    logger.warning("Consistency Editor returned invalid structure. Falling back to original identity.")
            except json.JSONDecodeError as je:
                logger.warning(f"Consistency Editor JSON parse failed: {je}. Falling back to original identity.")
    except Exception as ee:
        logger.warning("- [FALLBACK] Consistency Editor failed (skipping): %s", ee)


    if stage_callback: await stage_callback("editor", "done", data=identity)

    # --- FINAL: QUALITY AUDIT ---
    identity["quality_audit"] = await _rate_agent_quality(identity, provider)
    logger.info(f"AGENT QUALITY SCORE: {identity['quality_audit'].get('score')}/10 - {identity['quality_audit'].get('review')}")

    return identity


async def manifest_vivida_vessel(
    identity: Dict[str, Any],
    provider: str = settings.generator_provider,
    stage_callback = None
) -> Dict[str, Any]:
    """
    Phase 2: Generates the 'Vessel' (Stage 14: Appearance).
    Manifests the physical representation based on the soul.
    """
    logger.info("Manifesting Vessel for Identity: %s", identity.get("agent_id"))

    async def llm_call(sys, prompt, w_schema, w_name, temperature=0.7, **kwargs):
        target_provider = kwargs.pop("provider", provider)
        return await call_with_retries(
            sys, prompt, w_schema, wrapper_name=w_name,
            attempts=3, timeout=600, provider=target_provider,
            temperature=temperature, **kwargs
        )

    # --- STAGE 14: APPEARANCE DETAILS (Structured Visual spec) ---
    if stage_callback: await stage_callback("appearance", "running")
    logger.info("Generating Structured Appearance Details")
    try:
        app_sys, _, app_schema = await get_appearance_schema(1, identity)
        app_prompt = "Generate a detailed visual specification based on the agent's full identity."
        obj_app, _ = await _gen(app_sys, app_prompt, ensure_schema_valid(app_schema, "appearance_details"), "appearance_details", "appearance", llm_call, identity=identity)
        identity["appearance"] = extract_stage(obj_app, "appearance_details")
        identity["appearance_descriptor"] = identity["appearance"].get("aesthetic_vibe", "")
        if stage_callback: await stage_callback("appearance", "done", data=identity["appearance"])
    except Exception as ae:
        logger.warning(f"Appearance generation failed: {ae}")
        if stage_callback: await stage_callback("appearance", "error")

    return identity


async def generate_vivida_identity(
    name_hint: Optional[str] = None,
    role_hint: Optional[str] = None,
    personality_hint: Optional[str] = None,
    criteria: Optional[Dict[str, Any]] = None,
    provider: str = settings.generator_provider,
    stage_callback = None
) -> Dict[str, Any]:
    """
    Full pipeline wrapper for backward compatibility.
    Runs Soul generation followed by Vessel manifestation.
    """
    identity = await generate_vivida_soul(
        name_hint=name_hint,
        role_hint=role_hint,
        personality_hint=personality_hint,
        country_hint=None,
        city_hint=None,
        criteria=criteria,
        provider=provider,
        stage_callback=stage_callback
    )
    return await manifest_vivida_vessel(identity, provider, stage_callback=stage_callback)


async def generate_agent_lifecycle(identity, llm_call, stage_callback=None):
    """
    Generates the dynamic lifecycle data (Strategy, Routine, Schedule, Episodic Memory).
    This can be called separately from the core DNA generation.
    """
    # Parallelize independent generation stacks
    planning_task = _generate_planning_stack(identity, llm_call, stage_callback=stage_callback)
    memory_task = _generate_dynamic_memory_stack(identity, llm_call, stage_callback=stage_callback)
    
    results = await asyncio.gather(planning_task, memory_task, return_exceptions=True)
    
    planning = {} if isinstance(results[0], Exception) else results[0]
    memory_extension = {} if isinstance(results[1], Exception) else results[1]
    
    if isinstance(results[0], Exception):
        logger.error(f"Planning generation failed: {results[0]}")
    if isinstance(results[1], Exception):
        logger.error(f"Memory extension generation failed: {results[1]}")
    
    lifecycle = {
        "planning": planning,
        "memory_extension": memory_extension
    }
    return lifecycle


async def _generate_core_memory(identity, llm_call, stage_callback=None):
    """Generates the static core semantic memory layer for the DNA."""
    rag_m1 = await _rag_context(identity["agent_id"], "memory")
    sys_m1, _, schema_m1 = await get_mem_part1_schema(1, identity)
    obj_m1, _ = await _gen(sys_m1, f"Generate Core Semantic knowledge.{rag_m1}", ensure_schema_valid(schema_m1, "memory"), "memory", "mem_p1", llm_call, identity=identity)
    core_mem = extract_stage(obj_m1, "memory")
    await _index_fragment(identity["agent_id"], "memory_core", core_mem)
    if stage_callback: await stage_callback("memory", "done", data=core_mem)
    return {"core": core_mem}


async def _generate_planning_stack(identity, llm_call, stage_callback=None):
    """Generates the strategy, routine, and schedule for the agent."""
    planning = {}
    identity["planning"] = planning  # Inject for context of next stages
    
    # Part 1: Strategy
    if stage_callback: await stage_callback("planning_strategy", "running")
    sys_p1, _, schema_p1 = await get_planning_strategy_schema(1, identity)
    obj_p1, _ = await _gen(sys_p1, "Generate Long-term Strategy.", ensure_schema_valid(schema_p1, "planning_strategy"), "planning_strategy", "plan_p1", llm_call, identity=identity)
    planning["strategy"] = extract_stage(obj_p1, "planning_strategy")
    if stage_callback: await stage_callback("planning_strategy", "done", data=planning["strategy"])

    # Part 2: Routine
    if stage_callback: await stage_callback("planning_routine", "running")
    sys_p2, _, schema_p2 = await get_planning_routine_schema(1, identity)
    obj_p2, _ = await _gen(sys_p2, "Generate Weekly Routine.", ensure_schema_valid(schema_p2, "planning_routine"), "planning_routine", "plan_p2", llm_call, identity=identity)
    planning["routine"] = extract_stage(obj_p2, "planning_routine")
    if stage_callback: await stage_callback("planning_routine", "done", data=planning["routine"])

    # Part 3: Day Schedule
    if stage_callback: await stage_callback("planning_day", "running")
    sys_p3, _, schema_p3 = await get_planning_day_schema(1, identity)
    obj_p3, _ = await _gen(sys_p3, "Generate Today's Schedule.", ensure_schema_valid(schema_p3, "planning_day"), "planning_day", "plan_p3", llm_call, identity=identity)
    day_plan_list = obj_p3.get("planning_day") if isinstance(obj_p3, dict) else obj_p3
    planning["schedule"] = day_plan_list
    if stage_callback: await stage_callback("planning_day", "done", data=day_plan_list)

    return planning


async def _generate_dynamic_memory_stack(identity, llm_call, stage_callback=None):
    """Generates episodic and narrative memory layers (Dynamic)."""
    if "memory" not in identity:
        identity["memory"] = {}
    memory = identity["memory"]
    col_name = f"agent_memory_{identity['agent_id']}"

    # Part 2: Episodic
    if stage_callback: await stage_callback("episodic_memory", "running")
    sys_m2, _, schema_m2 = await get_mem_part2_schema(1, identity)
    obj_m2, _ = await _gen(sys_m2, "Generate Episodic events.", ensure_schema_valid(schema_m2, "memory"), "memory", "mem_p2", llm_call, identity=identity)
    mem_p2 = extract_stage(obj_m2, "memory")
    memory["episodic"] = mem_p2
    if stage_callback: await stage_callback("episodic_memory", "done", data=mem_p2)

    # Vector Seeding
    try:
        events = mem_p2.get("events", {}).get("major_events", []) if isinstance(mem_p2, dict) else []
        for ev in events:
            if not isinstance(ev, dict): continue
            text = f"[{ev.get('date')}] {ev.get('title')}: {ev.get('description')}"
            vector = await gemini_client.generate_embedding(text)
            if vector:  # Guard: don't try to store None vector
                await memory_service.add_memory(col_name, text, vector, {"type": "episodic"})
    except Exception as me:
        logger.warning(f"Vector seeding failed: {me}")

    # Part 3: Narrative
    if stage_callback: await stage_callback("narrative_memory", "running")
    sys_m3, _, schema_m3 = await get_mem_part3_schema(1, identity)
    obj_m3, _ = await _gen(sys_m3, "Generate Narrative & Goals.", ensure_schema_valid(schema_m3, "memory"), "memory", "mem_p3", llm_call, identity=identity)
    narrative = extract_stage(obj_m3, "memory")

    narrative = await _consensus(narrative, "memory_part3", schema_m3, sys_m3, identity["agent_id"], json.dumps(identity.get("demographics", {}), ensure_ascii=False))
    memory["narrative"] = narrative
    if stage_callback: await stage_callback("narrative_memory", "done", data=narrative)

    await _index_fragment(identity["agent_id"], "memory_narrative", narrative)
    return memory
