import asyncio
import time
import logging
import uuid as _uuid
import json
from typing import Any, Dict, Optional
from arq import cron
from arq.connections import RedisSettings
from app.config import settings
from app.services.pipeline import generate_vivida_soul, manifest_vivida_vessel, generate_agent_lifecycle
import httpx
from app.database import AsyncSessionLocal
from app.models import AgentModel
from sqlalchemy import select, update, text

logger = logging.getLogger(__name__)

from app.services.utils import STAGE_ORDER
from app.services.neo4j_client import graph_memory_service
from app.services.kg_extractor import extract_knowledge_graph
from app.services.audit_service import run_psychological_audit
from app.services.knowledge_exam_service import run_knowledge_exam
from app.services.stress_test_service import run_stress_test
from app.services.refinement_service import run_agent_refinement
from app.services.qdrant_client import memory_service

async def notify_webhook(url: str, job_id: str, status: str, result: dict = None, error: str = None, client_reference_id: str = None):
    """Sends HTTP POST to the client's webhook URL."""
    if not url:
        return
    payload = {
        "job_id": job_id,
        "status": status,
        "result": result,
        "error": error,
        "client_reference_id": client_reference_id
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=5.0)
    except Exception as e:
        logger.error(f"Failed to notify webhook {url}: {e}")

async def update_agent_stage(agent_id: str, stage: str, status: str, data: Any = None):
    """Atomic JSON merge update for agent stage status and data."""
    try:
        async with AsyncSessionLocal() as session:
            if status == "done" and data is not None:
                # If stage is 'editor', it provides the full corrected identity
                data_patch = json.dumps(data if stage == "editor" else {stage: data}, ensure_ascii=False)
                await session.execute(
                    text("""
                        UPDATE agents
                        SET 
                            stages_status = CAST(COALESCE(CAST(stages_status AS jsonb), '{}'::jsonb) || CAST(:status_patch AS jsonb) AS json),
                            agent_data = CAST(COALESCE(CAST(agent_data AS jsonb), '{}'::jsonb) || CAST(:data_patch AS jsonb) AS json)
                        WHERE id = :agent_id
                    """),
                    {
                        "status_patch": json.dumps({stage: status}), 
                        "data_patch": data_patch,
                        "agent_id": agent_id
                    }
                )
            else:
                await session.execute(
                    text("""
                        UPDATE agents
                        SET stages_status = CAST(COALESCE(CAST(stages_status AS jsonb), '{}'::jsonb) || CAST(:patch AS jsonb) AS json)
                        WHERE id = :agent_id
                    """),
                    {"patch": json.dumps({stage: status}), "agent_id": agent_id}
                )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update stage {stage} for agent {agent_id}: {e}")

async def run_auto_ci(agent_id: str, max_refinements: int = 3) -> Optional[int]:
    """Runs the Automated CI Pipeline (Audit, Exam, Stress).
    If the result is below IDEAL_THRESHOLD (80), triggers the Refinement Loop.
    """
    IDEAL_THRESHOLD = 80
    refinement_count = 0
    
    async def set_stage(stage: str, status: str, data: Any = None):
        await update_agent_stage(agent_id, stage, status, data)

    await set_stage("quality_control", "running")
    while refinement_count <= max_refinements:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
                agent = result.scalar_one_or_none()
                if not agent:
                    return None
                    
                data = agent.agent_data or {}
                required_sections = ["demographics", "psychology", "biography"]
                missing = [s for s in required_sections if s not in data]
                
                if missing:
                    logger.warning(f"== [AUTO-CI] Skipped for {agent_id}: missing sections {missing} ==")
                    await session.execute(
                        update(AgentModel)
                        .where(AgentModel.id == agent_id)
                        .values(
                            ci_passed=False,
                            ci_report={"error": f"Incomplete agent data. Missing: {', '.join(missing)}"}
                        )
                    )
                    await session.commit()
                    return None

                # 1. Run Psychological Audit
                await set_stage("ci_audit", "running")
                audit_data = await run_psychological_audit(agent_id, session)
                audit_score = audit_data.get("report", {}).get("score", 0)
                await set_stage("ci_audit", "done", data=audit_data)
                
                # 2. Run Knowledge Exam
                await set_stage("ci_exam", "running")
                exam_data = await run_knowledge_exam(agent_id, session)
                exam_score = exam_data.get("score", 0)
                await set_stage("ci_exam", "done", data=exam_data)
                
                # 3. Run Stress Test
                await set_stage("ci_stress", "running")
                stress_data = await run_stress_test(agent_id, session)
                stress_score = stress_data.get("report", {}).get("resilience_score", 0)
                await set_stage("ci_stress", "done", data=stress_data)
                
                # 4. Calculate Final CI Score
                # Audit returns score on 0-10 scale (see audit prompt). Normalize to 0-100.
                def to_100(val):
                    """Normalize a value to 0-100 range, handling both 0-10 and 0-100 scales."""
                    try:
                        if val is None: return 0.0
                        val = float(val)
                        return min(100.0, val * 10 if val <= 10 else val)
                    except: return 0.0
                
                normalized_audit = to_100(audit_score)
                safe_exam = to_100(exam_score)
                safe_stress = to_100(stress_score)
                
                ci_score = int(
                    (normalized_audit * 0.4) + 
                    (safe_exam * 0.3) + 
                    (safe_stress * 0.3)
                )
                
                # Granular metrics for the UI
                audit_metrics = audit_data.get("report", {}).get("metrics", {})
                
                ci_report = {
                    "audit": audit_data,
                    "exam": exam_data,
                    "stress": stress_data,
                    "metrics": {
                        "audit_score": normalized_audit,
                        "knowledge_score": min(100.0, float(exam_score)),
                        "stress_score": min(100.0, float(stress_score)),
                        "consistency": to_100(audit_metrics.get("consistency", 0)),
                        "depth": to_100(audit_metrics.get("depth", 0)),
                        "style": to_100(audit_metrics.get("style", 0))
                    },
                    "refinement_iteration": refinement_count
                }
                
                ci_passed = ci_score >= IDEAL_THRESHOLD
                
                # 5. Check if Refinement is needed
                if not ci_passed and refinement_count < max_refinements:
                    logger.info(f"== [AUTO-CI] Score {ci_score} < {IDEAL_THRESHOLD}. Launching Refinement iteration {refinement_count+1} ==")
                    await set_stage("refinement", "running")
                    refinement_result = await run_agent_refinement(agent_id, session, ci_report)
                    if "error" not in refinement_result:
                        refinement_count += 1
                        await set_stage("refinement", "done", data=refinement_result)
                        continue # Re-run CI with refined data
                    else:
                        await set_stage("refinement", "error")
                        logger.warning(f"Refinement failed for {agent_id}: {refinement_result.get('error')}")

                # 6. Final Update (Either passed or reached max retries)
                await session.execute(
                    update(AgentModel)
                    .where(AgentModel.id == agent_id)
                    .values(
                        ci_score=ci_score,
                        ci_passed=ci_passed,
                        ci_report=ci_report
                    )
                )
                await session.commit()
                
                if ci_passed:
                    logger.info(f"== [AUTO-CI] Goal Reached! Final Score: {ci_score}, Refinements: {refinement_count} ==")
                    await set_stage("quality_control", "done", data=ci_report)
                    return ci_score
                
                # If we're here and not ci_passed, it means we hit max_refinements
                logger.warning(f"== [AUTO-CI] Reached max refinements ({max_refinements}). Final Score: {ci_score} ==")
                await set_stage("quality_control", "done", data=ci_report)
                return ci_score
                
        except Exception as e:
            logger.exception(f"Auto-CI failed for agent {agent_id}: {e}")
            return None

async def run_soul_generation(ctx, job_id: str, req_data: dict):
    webhook_url = req_data.get("webhook_url")
    client_ref = req_data.get("client_reference_id")
    logger.info(f"Starting soul generation for job {job_id}")
    await notify_webhook(webhook_url, job_id, "processing", client_reference_id=client_ref)
    
    try:
        # Pre-generate the DB UUID so pipeline uses it for Qdrant collection name
        # This ensures agent_memory_{agent_id} matches what delete_agent will look for
        agent_id = str(_uuid.uuid4())

        identity = await generate_vivida_soul(
            name_hint=req_data.get("name_hint"),
            role_hint=req_data.get("role_hint"),
            personality_hint=req_data.get("personality_hint"),
            country_hint=req_data.get("country_hint"),
            city_hint=req_data.get("city_hint"),
            criteria=req_data.get("criteria"),
            provider=req_data.get("provider", settings.llm_provider),
            agent_id=agent_id,
        )
        
        # Save to DB
        async with AsyncSessionLocal() as session:
            agent_name = (
                identity.get("agent_name") or 
                identity.get("demographics", {}).get("agent_name") or 
                identity.get("meta", {}).get("name") or 
                "Unknown"
            )
            agent_role = (
                identity.get("agent_role") or 
                identity.get("demographics", {}).get("agent_role") or 
                "AI Agent"
            )
            
            agent = AgentModel(
                id=agent_id,
                owner_id=req_data.get("owner_id"),
                original_job_id=job_id,
                name=agent_name,
                role=agent_role,
                agent_data=identity,
                generation_mode="soul"
            )
            session.add(agent)
            await session.commit()
            
        # --- NEO4J: Create Agent Base Node ---
        try:
            await graph_memory_service.create_agent_node(
                agent_id=agent_id,
                name=agent_name,
                role=agent_role
            )
        except Exception as neo_e:
            logger.error(f"Failed to create graph node for {agent_id}: {neo_e}")
            # Non-fatal for generation, but we should log it
            
        identity["id"] = agent_id
        
        # --- LIFECYCLE GENERATION (Sequential) ---
        # We perform the full lifecycle generation (Planning + Memory + KG + CI)
        # before sending the completion webhook.
        try:
            await run_lifecycle_generation(ctx, agent_id, req_data, suppress_webhook=True)
        except Exception as lf_e:
            # Re-raise so the outer block handles failure notification
            raise ValueError(f"Lifecycle generation failed: {lf_e}")
        
        # Reload identity to get the full profile including lifecycle
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent:
                identity = agent.agent_data

        await notify_webhook(webhook_url, job_id, "completed", result=identity, client_reference_id=client_ref)
        return identity
    except Exception as e:
        logger.exception(f"Soul generation failed for job {job_id}")
        await notify_webhook(webhook_url, job_id, "failed", error=str(e), client_reference_id=client_ref)
        raise e

async def run_staged_soul_generation(ctx, job_id: str, agent_db_id: str, req_data: dict):
    """
    Staged soul generation: pre-creates DB row and updates stages_status live.
    The frontend polls GET /agents/{agent_db_id}/stages to display live progress.
    """
    webhook_url = req_data.get("webhook_url")
    client_ref = req_data.get("client_reference_id")
    provider = req_data.get("provider", settings.llm_provider)
    logger.info(f"Starting STAGED soul generation: job={job_id}, db_agent={agent_db_id}")

    async def set_stage(stage: str, status: str, data: Any = None):
        await update_agent_stage(agent_db_id, stage, status, data)

    try:
        identity = await generate_vivida_soul(
            name_hint=req_data.get("name_hint"),
            role_hint=req_data.get("role_hint"),
            personality_hint=req_data.get("personality_hint"),
            country_hint=req_data.get("country_hint"),
            city_hint=req_data.get("city_hint"),
            criteria=req_data.get("criteria"),
            provider=provider,
            stage_callback=set_stage,
            agent_id=str(agent_db_id),  # Use DB UUID so Qdrant collection name aligns
        )

        # --- SAVE FINAL RESULT ---
        name = (
            identity.get("agent_name") or 
            identity.get("demographics", {}).get("agent_name") or 
            identity.get("meta", {}).get("name") or 
            "Unknown"
        )
        role = (
            identity.get("agent_role") or 
            identity.get("demographics", {}).get("agent_role") or 
            "AI Agent"
        )

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AgentModel).where(AgentModel.id == agent_db_id))
            agent = result.scalar_one_or_none()
            if agent:
                agent.name = name
                agent.role = role
                agent.agent_data = identity
                stages = dict(agent.stages_status or {})
                stages["_complete"] = "true"
                agent.stages_status = stages
                await session.commit()
                
        # --- NEO4J: Create Agent Base Node ---
        try:
            await graph_memory_service.create_agent_node(
                agent_id=str(agent_db_id),
                name=name,
                role=role
            )
        except Exception as neo_e:
            logger.error(f"Failed to create graph node for staged agent {agent_db_id}: {neo_e}")

        # --- LIFECYCLE GENERATION (includes CI) ---
        try:
            await run_lifecycle_generation(ctx, str(agent_db_id), req_data, suppress_webhook=True)
        except Exception as lf_e:
            raise ValueError(f"Lifecycle generation failed: {lf_e}")

        await notify_webhook(webhook_url, job_id, "completed", result={"agent_id": agent_db_id, "name": name}, client_reference_id=client_ref)
        logger.info(f"Staged soul generation complete: agent={agent_db_id}")
        
        return {"agent_id": agent_db_id, "name": name}

    except Exception as e:
        logger.exception(f"Staged soul generation failed: job={job_id}")
        # Mark all pending/running stages as error
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AgentModel).where(AgentModel.id == agent_db_id))
                agent = result.scalar_one_or_none()
                if agent:
                    stages = {k: ("error" if v == "running" else v) for k, v in (agent.stages_status or {}).items()}
                    agent.stages_status = stages
                    await session.commit()
        except Exception: pass
        # Clean up orphaned Qdrant collection created during this failed run
        try:
            await memory_service.delete_collection(f"agent_memory_{agent_db_id}")
        except Exception: pass

        # Clean up orphaned Neo4j node created during this failed run
        try:
            await graph_memory_service.delete_agent_node(str(agent_db_id))
        except Exception: pass
        
        await notify_webhook(webhook_url, job_id, "failed", error=str(e), client_reference_id=client_ref)
        raise


async def run_vessel_manifestation(ctx, job_id: str, req_data: dict):
    webhook_url = req_data.get("webhook_url")
    client_ref = req_data.get("client_reference_id")
    logger.info(f"Starting vessel manifestation for job {job_id}")
    await notify_webhook(webhook_url, job_id, "processing", client_reference_id=client_ref)
    
    try:
        identity = await manifest_vivida_vessel(
            identity=req_data.get("identity"),
            provider=req_data.get("provider", settings.llm_provider)
        )
        
        async with AsyncSessionLocal() as session:
            agent_id = str(_uuid.uuid4())
            agent_name = (
                identity.get("agent_name") or 
                identity.get("demographics", {}).get("agent_name") or 
                identity.get("meta", {}).get("name") or 
                "Unknown"
            )
            agent_role = (
                identity.get("agent_role") or 
                identity.get("demographics", {}).get("agent_role") or 
                "AI Agent"
            )

            # Overwrite internal agent_id so stored agent_data always matches the DB UUID.
            # This ensures lifecycle generation later uses the correct Qdrant collection name.
            identity["agent_id"] = agent_id

            agent = AgentModel(
                id=agent_id,
                owner_id=req_data.get("owner_id"),
                original_job_id=job_id,
                name=agent_name,
                role=agent_role,
                avatar_url=identity.get("appearance_descriptor"),
                agent_data=identity,
                generation_mode="vessel"
            )
            session.add(agent)
            await session.commit()
            
        # --- NEO4J: Create Agent Base Node ---
        try:
            await graph_memory_service.create_agent_node(
                agent_id=agent_id,
                name=agent_name,
                role=agent_role
            )
        except Exception as neo_e:
            logger.error(f"Failed to create graph node for vessel {agent_id}: {neo_e}")
            
        identity["id"] = agent_id
        
        # --- LIFECYCLE GENERATION (includes CI) ---
        try:
            await run_lifecycle_generation(ctx, agent_id, req_data, suppress_webhook=True)
        except Exception as lf_e:
            raise ValueError(f"Lifecycle generation failed: {lf_e}")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent:
                identity = agent.agent_data

        await notify_webhook(webhook_url, job_id, "completed", result=identity, client_reference_id=client_ref)
        return identity
    except Exception as e:
        logger.exception(f"Vessel manifestation failed for job {job_id}")
        await notify_webhook(webhook_url, job_id, "failed", error=str(e), client_reference_id=client_ref)
        raise e

async def run_lifecycle_generation(ctx, agent_id: str, req_data: dict, suppress_webhook: bool = False):
    job_id = ctx.get('job_id') or str(_uuid.uuid4())
    webhook_url = req_data.get("webhook_url")
    client_ref = req_data.get("client_reference_id")
    provider = req_data.get("provider", settings.llm_provider)

    logger.info(f"Starting lifecycle generation for agent {agent_id}, job {job_id}")
    await notify_webhook(webhook_url, job_id, "processing", client_reference_id=client_ref)

    from app.services.llm.retry import call_with_retries
    from app.services.pipeline import generate_agent_lifecycle

    async def llm_call(sys, prompt, w_schema, w_name):
        return await call_with_retries(sys, prompt, w_schema, wrapper_name=w_name,
                                        attempts=3, timeout=600, provider=provider)

    current_stage = "initializing"
    try:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
                agent = result.scalar_one_or_none()
                if not agent:
                    raise ValueError(f"Agent {agent_id} not found in DB.")

                identity = dict(agent.agent_data)
                identity["agent_id"] = str(agent_id) # Ensure it exists for the pipeline

                async def set_stage(stage: str, status: str, data: Any = None):
                    await update_agent_stage(agent_id, stage, status, data)

                # Initialize stages for the UI
                stages_to_reset = [
                    "lifecycle", "planning_strategy", "planning_routine", "planning_day", 
                    "episodic_memory", "narrative_memory", "knowledge_graph",
                    "quality_control", "ci_audit", "ci_exam", "ci_stress", "refinement"
                ]
                for sname in stages_to_reset:
                    await set_stage(sname, "waiting")

                async def stage_callback(sname, status, data=None):
                    nonlocal current_stage
                    if status == "running":
                        current_stage = sname
                    await set_stage(sname, status, data=data)

                await set_stage("lifecycle", "running")

                # Generate lifecycle (Strategy, Routine, Schedule, Episodic Memory)
                current_stage = "lifecycle_generation"
                lifecycle = await generate_agent_lifecycle(identity, llm_call, stage_callback=stage_callback)

                # Merge lifecycle data back into identity
                identity["planning"] = lifecycle.get("planning")
                if "memory" not in identity:
                    identity["memory"] = {}
                if isinstance(identity["memory"], dict):
                    identity["memory"].update(lifecycle.get("memory_extension", {}))

                # Update DB
                agent.agent_data = identity
                await session.commit()
                
            # --- NEO4J: Extract Knowledge Graph from Biography ---
            current_stage = "knowledge_graph"
            await set_stage("knowledge_graph", "running")
            
            # Collect rich text for KG extraction (try multiple sources for best coverage)
            kg_text_parts = []
            
            # Primary: biography origin_story (always present after soul generation)
            bio = identity.get("biography", {})
            if isinstance(bio, list) and bio:
                bio = bio[0]
            origin_story = bio.get("origin_story", "") if isinstance(bio, dict) else ""
            if origin_story:
                kg_text_parts.append(origin_story)
            
            # Secondary: backstory (legacy field or memory_extension fallback)
            backstory = identity.get("memory", {}).get("backstory", "")
            if not backstory and isinstance(lifecycle.get("memory_extension"), dict):
                backstory = lifecycle.get("memory_extension", {}).get("backstory", "")
            if backstory and backstory not in kg_text_parts:
                kg_text_parts.append(backstory)
            
            # Compose final text
            backstory = "\n\n".join(kg_text_parts)

            if backstory:
                # Construct a richer context for KG extraction to capture traits and values
                data = identity or {}
                bio = data.get("biography", {})
                psych = data.get("psychology", {})
                exp = data.get("experience", {})
                behav = data.get("behavioral_main", {})
                plan = data.get("planning", {})
                
                full_profile_text = f"NAME: {identity.get('agent_name', 'Unknown')}\n\n"
                full_profile_text += f"BIOGRAPHY:\n{bio.get('origin_story', '')}\n\n"
                full_profile_text += f"PSYCHOLOGY:\nCharacter: {psych.get('character', '')}\nTraits: {', '.join(psych.get('personality_traits', []))}\nValues: {', '.join(psych.get('core_values', []))}\n\n"
                full_profile_text += f"BEHAVIORAL HABITS:\n{json.dumps(behav, ensure_ascii=False)}\n\n"
                full_profile_text += f"PLANNING & ROUTINE:\n{json.dumps(plan, ensure_ascii=False)}\n\n"
                full_profile_text += f"EXPERIENCE:\n{json.dumps(exp, ensure_ascii=False)}"

                kg_data = await extract_knowledge_graph(
                    text=full_profile_text, 
                    agent_id=str(agent_id),
                    agent_name=identity.get("agent_name", "Unknown"),
                    provider=provider
                )
                
                # Ensure the primary agent node is in the output array in case LLM missed it
                if not any(n.get("id") == str(agent_id) for n in kg_data.get("nodes", [])):
                    kg_data["nodes"].append({
                        "id": str(agent_id), 
                        "name": identity.get("agent_name", "Unknown"), 
                        "type": "AGENT"
                    })
                    
                await graph_memory_service.ingest_knowledge_graph(kg_data, source_agent_id=str(agent_id))
                await set_stage("knowledge_graph", "done")
            else:
                await set_stage("knowledge_graph", "skipped")

            # --- AUTO-CI PASS ---
            current_stage = "auto_ci"
            # Run CI after lifecycle because it adds significant KG data for the exam
            await run_auto_ci(str(agent_id))
            
            await set_stage("lifecycle", "done", data=lifecycle)

            if not suppress_webhook:
                await notify_webhook(webhook_url, job_id, "completed", result=lifecycle, client_reference_id=client_ref)
            return lifecycle

        except Exception as e:
            logger.exception(f"Lifecycle generation failed for agent {agent_id}, job {job_id} at stage {current_stage}")
            if current_stage and current_stage not in ["initializing", "auto_ci"]:
                await set_stage(current_stage, "failed")
            await notify_webhook(webhook_url, job_id, "failed", error=str(e), client_reference_id=client_ref)
            raise e
    except Exception as outer_e:
        logger.error(f"Outer exception in lifecycle job: {outer_e}")
        raise outer_e

async def run_maintenance_cycle(ctx):
    """
    Scans all agents hourly to ensure data integrity and verification completeness.
    Triggers missing lifecycle or CI tasks if needed.
    """
    logger.info("Starting hourly maintenance cycle...")
    redis = ctx['redis']

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AgentModel))
            agents = result.scalars().all()

            for agent in agents:
                agent_id = str(agent.id)
                data = agent.agent_data or {}
                stages = agent.stages_status or {}

                # 1. Skip if any core generation or lifecycle is already running
                is_busy = any(status == "running" for status in stages.values())
                if is_busy:
                    logger.debug(f"Skipping maintenance for agent {agent_id}: generation in progress.")
                    continue

                # 2. Check for missing Lifecycle Data (Planning or Memory Extension)
                has_planning = "planning" in data and data["planning"]
                has_memory_ext = isinstance(data.get("memory"), dict) and ("narrative" in data["memory"] or "episodic" in data["memory"])
                
                if not has_planning or not has_memory_ext:
                    logger.info(f"Agent {agent_id} has missing lifecycle data. Enqueueing run_lifecycle_generation.")
                    # Use unique job ID to prevent duplicate execution within the same maintenance cycle
                    m_job_id = f"maint_life_{agent_id}_{int(time.time() // 3600)}"
                    await redis.enqueue_job(
                        "run_lifecycle_generation",
                        agent_id=agent_id,
                        req_data={"agent_id": agent_id, "provider": "gpt-oss"},
                        _job_id=m_job_id,
                    )
                    continue # CI will run automatically after lifecycle generation

                # 2b. Check for missing Knowledge Graph (stage was skipped due to old bug - backstory lookup)
                kg_stage = stages.get("knowledge_graph")
                if kg_stage in (None, "skipped", "failed"):
                    logger.info(f"Agent {agent_id} is missing knowledge graph (stage={kg_stage}). Re-enqueueing lifecycle generation.")
                    m_kg_job_id = f"maint_kg_{agent_id}_{int(time.time() // 3600)}"
                    await redis.enqueue_job(
                        "run_lifecycle_generation",
                        agent_id=agent_id,
                        req_data={"agent_id": agent_id, "provider": "gpt-oss"},
                        _job_id=m_kg_job_id,
                    )
                    continue

                # 3. Check for missing CI Verification
                if agent.ci_score is None or not agent.ci_report:
                    logger.info(f"Agent {agent_id} is missing CI verification. Enqueueing run_maintenance_ci.")
                    m_ci_job_id = f"maint_ci_{agent_id}_{int(time.time() // 3600)}"
                    await redis.enqueue_job("run_maintenance_ci", req_data={"agent_id": agent_id}, _job_id=m_ci_job_id)

    except Exception as e:
        logger.error(f"Maintenance cycle failed: {e}")

async def run_maintenance_ci(ctx, req_data: dict):
    agent_id = req_data.get("agent_id")
    if not agent_id: return
    logger.info(f"Running maintenance CI for agent {agent_id}")
    await run_auto_ci(agent_id)

async def run_ta_brainstorm_and_generate(ctx, ta_description: str, count: int, visual_hints: Optional[str], owner_id: str, webhook_url: Optional[str], job_id: str):
    """
    Worker task to brainstorm agent seeds from TA and launch soul generation.
    """
    logger.info(f"Target Audience Brainstorm launched for job {job_id}")
    
    from app.services.gemini_client import gemini_client
    
    prompt = f"""
    You are an expert sociologist and character designer.
    Goal: Generate exactly {count} unique AI personas that fit the following Target Audience (TA).
    
    TA Description: {ta_description}
    Visual Theme/Hints: {visual_hints or "Realistic personas"}
    
    Return a JSON list of objects.
    """
    
    schema = """
    Array of {
        "name": "Full Name",
        "role": "Specific job title or role",
        "personality_hint": "Personality overview",
        "visual_dna_hint": "Brief physical description hint"
    }
    """

    try:
        seeds = await gemini_client.generate_json(prompt, schema)
        if not seeds or not isinstance(seeds, list):
            raise ValueError("Brainstorming failed to return a list.")
            
        redis_pool = ctx['redis']
        job_ids = []
        
        for seed in seeds[:count]:
            sub_id = str(_uuid.uuid4())
            req_data = {
                "name_hint": seed.get("name"),
                "role_hint": seed.get("role"),
                "personality_hint": seed.get("personality_hint"),
                "visual_hints": seed.get("visual_dna_hint"),
                "owner_id": owner_id,
                "webhook_url": webhook_url,
                "client_reference_id": job_id # Link back to batch job
            }
            await redis_pool.enqueue_job("run_soul_generation", job_id=sub_id, req_data=req_data, _job_id=sub_id)
            job_ids.append(sub_id)
            
        logger.info(f"Brainstormed {len(job_ids)} agents for batch {job_id}")
        # Note: We could notify a batch-complete webhook here if we had one.
        
    except Exception as e:
        logger.exception(f"TA Brainstorm failed for job {job_id}")
        await notify_webhook(webhook_url, job_id, "failed", error=str(e))

class WorkerSettings:
    functions = [
        run_soul_generation, 
        run_staged_soul_generation, 
        run_vessel_manifestation, 
        run_lifecycle_generation,
        run_maintenance_ci,
        run_maintenance_cycle,
        run_ta_brainstorm_and_generate
    ]
    cron_jobs = [
        cron("app.worker.run_maintenance_cycle", hour=None, minute=0, run_at_startup=False)
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 7200  # 120 mins
