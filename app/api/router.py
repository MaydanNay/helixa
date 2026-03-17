import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, HttpUrl
from arq.connections import create_pool

from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.models import AgentModel, UserModel, TuringSessionModel, TuringParticipantModel, TuringMessageModel, TuringVoteModel

from app.services.utils import STAGE_ORDER
from app.services.qdrant_client import memory_service
from app.services.neo4j_client import graph_memory_service
from app.services.kg_extractor import extract_knowledge_graph
from app.services.auth_service import decode_access_token, check_generation_quota, get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])

from app.api import auth
router.include_router(auth.router)

from app.api import integrations
router.include_router(integrations.router)

class GenerateSoulRequest(BaseModel):
    name_hint: Optional[str] = None
    role_hint: Optional[str] = None
    personality_hint: Optional[str] = None
    country_hint: Optional[str] = None
    city_hint: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None
    provider: str = "gpt-oss"
    webhook_url: Optional[HttpUrl] = None
    client_reference_id: Optional[str] = None

class ManifestVesselRequest(BaseModel):
    identity: Dict[str, Any]
    provider: str = "gpt-oss"
    webhook_url: Optional[HttpUrl] = None
    client_reference_id: Optional[str] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    role: str
    avatar_url: Optional[str] = None
    generation_mode: str
    agent_data: Dict[str, Any]
    created_at: Optional[str] = None
    ci_score: Optional[int] = None
    ci_passed: Optional[bool] = None
    ci_report: Optional[Dict[str, Any]] = None
    
class MemoryStreamRequest(BaseModel):
    event_text: str
    event_type: str = "observation" # observation, conversation, action
    timestamp: Optional[str] = None
    
class AgentActionRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    
class StagedSoulRequest(BaseModel):
    name_hint: Optional[str] = None
    role_hint: Optional[str] = None
    personality_hint: Optional[str] = None
    country_hint: Optional[str] = None
    city_hint: Optional[str] = None
    provider: str = "gpt-oss"
    webhook_url: Optional[HttpUrl] = None
    client_reference_id: Optional[str] = None

class LifecycleRequest(BaseModel):
    agent_id: str
    provider: str = "gpt-oss"
    webhook_url: Optional[HttpUrl] = None
    client_reference_id: Optional[str] = None

class TuringChatRequest(BaseModel):
    agent_id: str
    entity: str
    message: str
    is_soul_a: bool
    history: List[Dict[str, Any]]

class CreateArenaSessionRequest(BaseModel):
    agent_ids: List[str]
    max_participants: int = 5

class JoinArenaSessionRequest(BaseModel):
    session_id: str

class ArenaMessageRequest(BaseModel):
    content: str
    participant_id: str

class ArenaVoteRequest(BaseModel):
    target_participant_id: str
    vote_is_ai: bool
    voter_participant_id: str

from app.services.utils import STAGE_ORDER

@router.post("/generate/soul")
async def start_soul_generation(req: GenerateSoulRequest, request: Request, current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_generation_quota(current_user, db, 1)
    
    job_id = str(uuid.uuid4())
    req_data = req.model_dump()
    req_data["webhook_url"] = str(req.webhook_url) if req.webhook_url else None
    
    # Pass owner_id so the worker assigns it
    req_data["owner_id"] = current_user.id
    
    redis_pool = await create_pool(settings.redis_settings)
    await redis_pool.enqueue_job(
        "run_soul_generation", 
        job_id=job_id, 
        req_data=req_data,
        _job_id=job_id
    )
    await redis_pool.close()
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Soul generation queued."
    }

class BatchSoulRequest(BaseModel):
    count: int = 5
    theme: Optional[str] = None
    personality_hint: Optional[str] = None
    visual_dna: Optional[str] = None
    country_hint: Optional[str] = None
    city_hint: Optional[str] = None
    provider: str = "gpt-oss"
    mode: str = "staged" # "staged" or "fast"

@router.post("/generate/batch-soul")
async def start_batch_soul_generation(req: BatchSoulRequest, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Launch N soul generation jobs in parallel. Returns list of job_ids."""
    count = max(1, min(req.count, 20))  # clamp 1..20
    await check_generation_quota(current_user, db, count)
    
    redis_pool = await create_pool(settings.redis_settings)

    job_ids = []
    for i in range(count):
        agent_db_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        if req.mode == "fast":
            # For fast generation, no pre-created DB row needed (worker creates it)
            # But frontend needs job_id to track. We will just enqueue `run_soul_generation`
            req_data = {
                "name_hint": None,
                "role_hint": req.theme,
                "personality_hint": req.personality_hint,
                "country_hint": req.country_hint,
                "city_hint": req.city_hint,
                "criteria": {"visual_dna": req.visual_dna} if req.visual_dna else {},
                "provider": req.provider,
                "webhook_url": None,
                "client_reference_id": f"batch_{job_id}",
            }
            await redis_pool.enqueue_job(
                "run_soul_generation",
                job_id=job_id,
                req_data=req_data,
                _job_id=job_id,
            )
        else:
            # Staged generation logic
            initial_stages = {s: "pending" for s in STAGE_ORDER}
            agent = AgentModel(
                id=agent_db_id,
                owner_id=current_user.id,
                original_job_id=job_id,
                name="Generating…",
                role="Staged Generation",
                stages_status=initial_stages,
                generation_mode="staged",
                agent_data={}
            )
            db.add(agent)

            req_data = {
                "name_hint": None,
                "role_hint": req.theme,
                "personality_hint": req.personality_hint,
                "country_hint": req.country_hint,
                "city_hint": req.city_hint,
                "criteria": {"visual_dna": req.visual_dna} if req.visual_dna else {},
                "provider": req.provider,
                # In staged worker, it uses webhook to notify completion or it pre-creates name from callback
                "webhook_url": None,
                "client_reference_id": f"batch_{job_id}",
            }
            await redis_pool.enqueue_job(
                "run_staged_soul_generation",
                job_id=job_id,
                agent_db_id=agent_db_id,
                req_data=req_data,
                _job_id=job_id,
            )
            
        job_ids.append({
            "job_id": job_id,
            "agent_id": agent_db_id
        })

    if req.mode == "staged":
        await db.commit()
        
    await redis_pool.close()
    return {
        "batch_size": count,
        "jobs": job_ids,
        "status": "queued",
        "message": f"{count} {req.mode} soul generation jobs queued.",
    }

@router.post("/generate/vessel")
async def start_vessel_manifestation(req: ManifestVesselRequest, request: Request, current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_generation_quota(current_user, db, 1)
    
    job_id = str(uuid.uuid4())
    req_data = req.model_dump()
    req_data["webhook_url"] = str(req.webhook_url) if req.webhook_url else None
    
    req_data["owner_id"] = current_user.id
    
    redis_pool = await create_pool(settings.redis_settings)
    await redis_pool.enqueue_job(
        "run_vessel_manifestation", 
        job_id=job_id, 
        req_data=req_data,
        _job_id=job_id
    )
    await redis_pool.close()
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Vessel manifestation queued."
    }

@router.post("/generate/lifecycle")
async def start_lifecycle_generation(req: LifecycleRequest, request: Request, current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Generates the dynamic lifecycle data (Strategy, Routine, Schedule, Episodic Memory) for an existing agent."""
    await check_generation_quota(current_user, db, 1)

    job_id = str(uuid.uuid4())
    req_data = req.model_dump()
    req_data["webhook_url"] = str(req.webhook_url) if req.webhook_url else None

    redis_pool = await create_pool(settings.redis_settings)
    await redis_pool.enqueue_job(
        "run_lifecycle_generation",
        agent_id=req_data["agent_id"],
        req_data=req_data,
        _job_id=job_id
    )
    await redis_pool.close()

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Lifecycle generation queued."
    }

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    from arq.jobs import Job, JobStatus
    redis_pool = await create_pool(settings.redis_settings)
    job = Job(job_id, redis=redis_pool)
    
    try:
        status = await job.status()
    except Exception:
        await redis_pool.close()
        raise HTTPException(status_code=404, detail="Job not found")
    
    if status == JobStatus.not_found:
        await redis_pool.close()
        raise HTTPException(status_code=404, detail="Job not found")
    
    result = None
    if status == JobStatus.complete:
        try:
            result = await job.result(timeout=1)
        except Exception:
            pass
    
    await redis_pool.close()
    
    return {
        "job_id": job_id,
        "status": status.value if hasattr(status, 'value') else str(status),
        "result": result
    }

@router.post("/agents/{agent_id}/memory/stream")
async def stream_agent_memory(agent_id: str, req: MemoryStreamRequest, db: AsyncSession = Depends(get_db)):
    """
    Ingests a new memory stream event from the simulation.
    1. Saves event explicitly into Qdrant (Episodic Memory).
    2. Runs event through Knowledge Extractor to update Neo4j (Semantic Graph).
    """
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    collection_name = f"agent_memory_{agent_id}"
    
    # 1. Store in Qdrant (Episodic)
    await memory_service.create_collection_if_not_exists(collection_name)
    metadata = {
        "type": req.event_type,
        "source": "simulation_stream",
        "timestamp": req.timestamp or "now"
    }
    await memory_service.add_memories(collection_name, [req.event_text], [metadata])
    
    # 2. Extract and Store in Neo4j (Semantic)
    kg_data = await extract_knowledge_graph(
        text=req.event_text,
        agent_id=str(agent_id),
        agent_name=agent.name,
        provider=settings.llm_provider
    )
    
    if kg_data and (kg_data.get("nodes") or kg_data.get("edges")):
        await graph_memory_service.ingest_knowledge_graph(kg_data, source_agent_id=agent_id)
        
    return {
        "status": "success",
        "message": "Memory streamed, episodic vectors saved, and semantic graph updated.",
        "extracted_graph": kg_data
    }

@router.get("/agents")
async def list_agents(
    q: Optional[str] = Query(None, description="Search query: name or role"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """List all generated souls (agents) with optional search and pagination."""
    stmt = select(AgentModel)
    if current_user.role != "admin":
        stmt = stmt.where(AgentModel.owner_id == current_user.id)
        
    stmt = stmt.order_by(desc(AgentModel.created_at))
    if q:
        q_lower = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                AgentModel.name.ilike(q_lower),
                AgentModel.role.ilike(q_lower),
            )
        )
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "avatar_url": a.avatar_url,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "ci_score": a.ci_score,
            "ci_passed": a.ci_passed,
            "ci_report": a.ci_report,
        }
        for a in agents
    ]

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Get a single soul by ID."""
    stmt = select(AgentModel).where(AgentModel.id == agent_id)
    if current_user.role != "admin":
        stmt = stmt.where(AgentModel.owner_id == current_user.id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or unauthorized")
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "avatar_url": agent.avatar_url,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "agent_data": agent.agent_data,
        "ci_score": agent.ci_score,
        "ci_passed": agent.ci_passed,
        "ci_report": agent.ci_report,
    }

@router.get("/agents/export/all")
async def export_all_agents_stream(db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Export all agents as a continuous JSON stream to prevent OOM. (Admin Only)"""
    from fastapi.responses import StreamingResponse
    import json
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")

    async def generate_json_stream():
        yield '[\n'
        
        # Paginated fetch to prevent loading all rows into RAM
        page_size = 100
        offset = 0
        first_record = True
        
        while True:
            stmt = select(AgentModel).order_by(AgentModel.created_at).limit(page_size).offset(offset)
            result = await db.execute(stmt)
            agents = result.scalars().all()
            
            if not agents:
                break
                
            for agent in agents:
                agent_dict = {
                    "id": agent.id,
                    "original_job_id": agent.original_job_id,
                    "name": agent.name,
                    "role": agent.role,
                    "avatar_url": agent.avatar_url,
                    "generation_mode": agent.generation_mode,
                    "stages_status": agent.stages_status,
                    "ci_score": agent.ci_score,
                    "ci_passed": agent.ci_passed,
                    "ci_report": agent.ci_report,
                    "created_at": agent.created_at.isoformat() if agent.created_at else None,
                    "agent_data": agent.agent_data
                }
                
                chunk = json.dumps(agent_dict, ensure_ascii=False)
                
                if not first_record:
                    yield ',\n'
                else:
                    first_record = False
                    
                yield chunk
                
            offset += page_size
            
        yield '\n]'

    return StreamingResponse(
        generate_json_stream(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=agents_export.json"}
    )

@router.get("/agents/{agent_id}/export")
async def export_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Export a single soul's data as a JSON file."""
    from fastapi.responses import Response
    import json
    
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Give the file a nice name based on the agent's name
    filename_clean = "".join([c if c.isalnum() else "_" for c in (agent.name or "agent")])
    filename = f"{filename_clean}_{agent_id[:8]}.json"
    
    # Manually stringify with indent=2 so it's formatted nicely for download
    json_str = json.dumps(agent.agent_data, ensure_ascii=False, indent=2)
    
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/agents/{agent_id}/graph")
async def get_agent_graph(agent_id: str):
    """Retrieves the knowledge graph for a specific agent for visualization."""
    return await graph_memory_service.retrieve_full_graph(agent_id)

@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Delete a single soul by ID (wipes vector + graph memory)."""
    from app.services.qdrant_client import memory_service
    from app.services.neo4j_client import graph_memory_service
    
    stmt = select(AgentModel).where(AgentModel.id == agent_id)
    if current_user.role != "admin":
        stmt = stmt.where(AgentModel.owner_id == current_user.id)
        
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or unauthorized")
    
    # 1. Clean up Qdrant collection
    qdrant_ok = await memory_service.delete_collection(f"agent_memory_{agent_id}")

    # 2. Clean up Neo4j Graph
    neo4j_ok = await graph_memory_service.delete_agent_node(agent_id)
    
    if not qdrant_ok or not neo4j_ok:
        await db.rollback()
        raise HTTPException(
            status_code=500, 
            detail="Failed to clean up external memory services. Agent deletion explicitly aborted to prevent data orphaning."
        )

    # 3. Clean up DB record
    await db.delete(agent)
    await db.commit()
    return {"message": "Agent deleted successfully from DB, Vector, and Graph"}

@router.delete("/agents")
async def delete_all_agents(db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Delete ALL generated souls (agents). Admin Danger Zone."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    from sqlalchemy import delete
    from app.services.qdrant_client import memory_service
    from app.services.neo4j_client import graph_memory_service

    # Clean up all Qdrant agent_memory collections
    try:
        collections = memory_service.client.get_collections().collections
        for col in collections:
            if col.name.startswith("agent_memory_"):
                await memory_service.delete_collection(col.name)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not clean Qdrant collections: %s", e)
        
    # Wipe the entire graph DB
    await graph_memory_service.wipe_all_data()

    await db.execute(delete(AgentModel))
    await db.commit()
    return {"message": "All agents deleted successfully from DB, Vector, and Graph"}

@router.post("/generate/staged-soul")
async def start_staged_soul_generation(req: StagedSoulRequest, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Pre-create agent in DB with pending stages, then enqueue staged generation task."""
    agent_db_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # Pre-create DB row with all stages = pending
    initial_stages = {s: "pending" for s in STAGE_ORDER}
    agent = AgentModel(
        id=agent_db_id,
        owner_id=current_user.id,
        original_job_id=job_id,
        name="Generating…",
        role="Staged Generation",
        stages_status=initial_stages,
        generation_mode="staged",
        agent_data={}
    )
    db.add(agent)
    await db.commit()

    req_data = {
        "name_hint": req.name_hint,
        "role_hint": req.role_hint,
        "personality_hint": req.personality_hint,
        "provider": req.provider,
        "webhook_url": str(req.webhook_url) if req.webhook_url else None,
        "client_reference_id": req.client_reference_id,
    }

    redis_pool = await create_pool(settings.redis_settings)
    await redis_pool.enqueue_job(
        "run_staged_soul_generation",
        job_id=job_id,
        agent_db_id=agent_db_id,
        req_data=req_data,
        _job_id=job_id,
    )
    await redis_pool.close()

    return {
        "job_id": job_id,
        "agent_id": agent_db_id,
        "status": "queued",
        "stages": initial_stages,
        "message": "Staged soul generation queued. Poll GET /agents/{agent_id}/stages for progress."
    }

@router.get("/agents/{agent_id}/stages")
async def get_agent_stages(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Returns live stage status for a staged generation."""
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    stages = agent.stages_status or {s: "pending" for s in STAGE_ORDER}
    complete = stages.get("_complete") == "true"
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "generation_mode": agent.generation_mode,
        "stages": {k: v for k, v in stages.items() if not k.startswith("_")},
        "complete": complete,
    }

@router.post("/agents/{agent_id}/action")
async def agent_action(agent_id: str, req: AgentActionRequest, db: AsyncSession = Depends(get_db)):
    """
    Final Hybrid GraphRAG endpoint.
    1. Fetches semantic facts from Neo4j (Graph).
    2. Fetches past emotional/episodic memories from Qdrant (Vector).
    3. Combines both into a massive prompt.
    4. Generates response using LLM.
    """
    from app.services.utils import call_llm_with_retries
    
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    # 1. Fetch Graph Fact Memory
    graph_context = await graph_memory_service.retrieve_agent_context(agent_id, limit=10)
    
    # 2. Fetch Vector Episodic Memory
    collection_name = f"agent_memory_{agent_id}"
    await memory_service.create_collection_if_not_exists(collection_name)
    vector_results = await memory_service.search_memory(collection_name, req.prompt, limit=3)
    episodic_context = "\n".join([str(res.get("text")) for res in vector_results]) if vector_results else "No relevant past episodes found."
    
    # 3. Construct Hybrid Prompt
    system_prompt = f"""
    You are {agent.name}, an AI agent with the role of {agent.role}.
    Here is some background context about you:
    {agent.agent_data.get('background', 'Unknown background.')}
    
    [SEMANTIC FACTS (Graph Memory)]:
    Below are the absolute facts and relationships you know about your world:
    {graph_context}
    
    [EPISODIC MEMORIES (Vector Memory)]:
    Below are past episodes or events relevant to the current situation:
    {episodic_context}
    
    Respond in character to the following prompt or situation. Use your facts to guide your logic and your episodes to guide your emotions.
    """
    
    user_prompt = f"Situation/Prompt: {req.prompt}\n"
    if req.context:
        user_prompt += f"Additional Context: {req.context}\n"
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 4. Generate LLM Response
    response_text = await call_llm_with_retries(
        messages=messages,
        provider=settings.llm_provider,
        temperature=0.7
    )
    
    return {
        "agent": agent.name,
        "action": response_text,
        "retrieved_nodes": graph_context,
        "retrieved_episodes": episodic_context
    }

@router.post("/agents/{agent_id}/audit")
async def audit_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    try:
        report = await run_psychological_audit(agent_id, db)
        return report
    except Exception as e:
        logger.error(f"Audit failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/{agent_id}/labs/knowledge-exam")
async def knowledge_exam(agent_id: str, db: AsyncSession = Depends(get_db)):
    try:
        report = await run_knowledge_exam(agent_id, db)
        return report
    except Exception as e:
        logger.error(f"Knowledge exam failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/{agent_id}/labs/stress-test")
async def stress_test(agent_id: str, db: AsyncSession = Depends(get_db)):
    try:
        report = await run_stress_test(agent_id, db)
        return report
    except Exception as e:
        logger.error(f"Stress test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/{agent_id}/labs/evolve")
async def evolve_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Triggers the 'Dream State' (Memory Consolidation & Personality Growth)."""
    try:
        from app.services.evolution_service import run_dream_cycle
        result = await run_dream_cycle(agent_id, db)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Evolution failed for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/agents/{agent_id}/labs/turing/init")
async def init_turing(agent_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.turing_lab_service import start_turing_session
    return await start_turing_session(agent_id, db)

@router.post("/agents/{agent_id}/labs/turing/chat")
async def turing_chat(agent_id: str, req: TuringChatRequest, db: AsyncSession = Depends(get_db)):
    from app.services.turing_lab_service import get_turing_response
    return await get_turing_response(
        agent_id=agent_id,
        entity=req.entity,
        user_msg=req.message,
        is_soul_a=req.is_soul_a,
        history=req.history,
        db=db
    )

# --- Turing Arena Endpoints ---

@router.post("/labs/turing/sessions")
async def create_arena_session(req: CreateArenaSessionRequest, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    from app.services.turing_arena_service import create_turing_session
    return await create_turing_session(current_user.id, req.agent_ids, db, req.max_participants)

@router.post("/labs/turing/sessions/{session_id}/join")
async def join_arena_session(session_id: str, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    from app.services.turing_arena_service import join_turing_session
    return await join_turing_session(session_id, current_user.id, db)

@router.post("/labs/turing/sessions/{session_id}/start")
async def start_arena_session(session_id: str, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    from app.services.turing_arena_service import start_turing_session
    # Only host could start, but for simplicity...
    return await start_turing_session(session_id, db)

@router.post("/labs/turing/sessions/{session_id}/messages")
async def send_arena_message(session_id: str, req: ArenaMessageRequest, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    # 1. Validate participant ownership
    result = await db.execute(
        select(TuringParticipantModel).where(
            TuringParticipantModel.id == req.participant_id,
            TuringParticipantModel.session_id == session_id
        )
    )
    participant = result.scalar_one_or_none()
    if not participant or participant.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized participant")
    
    # 2. Validate session status
    session_result = await db.execute(select(TuringSessionModel).where(TuringSessionModel.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session or session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    from app.services.turing_arena_service import send_turing_message
    return await send_turing_message(session_id, req.participant_id, req.content, db)

@router.get("/labs/turing/sessions/{session_id}/messages")
async def list_arena_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.turing_arena_service import get_session_messages
    return await get_session_messages(session_id, db)

@router.post("/labs/turing/sessions/{session_id}/vote")
async def submit_arena_vote(session_id: str, req: ArenaVoteRequest, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    # 1. Validate voter ownership
    result = await db.execute(
        select(TuringParticipantModel).where(
            TuringParticipantModel.id == req.voter_participant_id,
            TuringParticipantModel.session_id == session_id
        )
    )
    participant = result.scalar_one_or_none()
    if not participant or participant.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized voter")

    from app.services.turing_arena_service import submit_turing_vote
    return await submit_turing_vote(session_id, req.voter_participant_id, req.target_participant_id, req.vote_is_ai, db)

@router.get("/labs/turing/sessions/{session_id}/results")
async def get_arena_results(session_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.turing_arena_service import get_session_results
    return await get_session_results(session_id, db)
