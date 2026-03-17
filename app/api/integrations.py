import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Security, Query
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl
from arq.connections import create_pool

from app.database import get_db
from app.models import UserModel, AgentModel
from app.config import settings
from app.services.auth_service import check_generation_quota

router = APIRouter(prefix="/external", tags=["integrations"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_user_by_api_key(api_key: str = Security(api_key_header), db: AsyncSession = Depends(get_db)):
    if not api_key:
        raise HTTPException(status_code=401, detail="API Key missing")
    
    result = await db.execute(select(UserModel).where(UserModel.api_key == api_key))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    return user

class CreateExternalAgentRequest(BaseModel):
    name_hint: Optional[str] = None
    role_hint: Optional[str] = None
    personality_hint: Optional[str] = None
    country_hint: Optional[str] = None
    city_hint: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None
    provider: str = "gpt-oss"
    webhook_url: Optional[HttpUrl] = None
    client_reference_id: Optional[str] = None

class CreateFromTARequest(BaseModel):
    ta_description: str
    count: int = 10
    visual_hints: Optional[str] = None
    webhook_url: Optional[HttpUrl] = None

@router.post("/agents")
async def create_external_agent(
    req: CreateExternalAgentRequest, 
    user: UserModel = Depends(get_user_by_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger agent generation for external platforms.
    """
    await check_generation_quota(user, db, 1)
    
    job_id = str(uuid.uuid4())
    req_data = req.model_dump()
    req_data["webhook_url"] = str(req.webhook_url) if req.webhook_url else None
    req_data["owner_id"] = user.id
    
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
        "message": "External agent generation queued."
    }

@router.post("/batch-agents")
async def create_external_batch_agents(
    reqs: List[CreateExternalAgentRequest], 
    user: UserModel = Depends(get_user_by_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger multiple agent generations in batch.
    """
    count = len(reqs)
    await check_generation_quota(user, db, count)
    
    job_ids = []
    redis_pool = await create_pool(settings.redis_settings)
    
    for req in reqs:
        job_id = str(uuid.uuid4())
        req_data = req.model_dump()
        req_data["webhook_url"] = str(req.webhook_url) if req.webhook_url else None
        req_data["owner_id"] = user.id
        
        await redis_pool.enqueue_job(
            "run_soul_generation", 
            job_id=job_id, 
            req_data=req_data,
            _job_id=job_id
        )
        job_ids.append(job_id)
        
    await redis_pool.close()
    
    return {
        "job_ids": job_ids,
        "status": "queued",
        "message": f"{len(job_ids)} external agent generations queued."
    }

@router.post("/create-from-ta")
async def create_external_agents_from_ta(
    req: CreateFromTARequest, 
    user: UserModel = Depends(get_user_by_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Brainstorm seeds from a TA description and trigger batch generation.
    """
    await check_generation_quota(user, db, req.count)
    
    # Brainstorming happens in a separate background job to keep API responsive
    batch_job_id = str(uuid.uuid4())
    redis_pool = await create_pool(settings.redis_settings)
    
    await redis_pool.enqueue_job(
        "run_ta_brainstorm_and_generate",
        ta_description=req.ta_description,
        count=req.count,
        visual_hints=req.visual_hints,
        owner_id=user.id,
        webhook_url=str(req.webhook_url) if req.webhook_url else None,
        job_id=batch_job_id
    )
    await redis_pool.close()
    
    return {
        "batch_job_id": batch_job_id,
        "status": "brainstorming",
        "message": f"Brainstorming {req.count} agents from TA launched."
    }

@router.get("/agents")
async def list_external_agents(
    user: UserModel = Depends(get_user_by_api_key), 
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve list of agents belonging to the user.
    """
    stmt = select(AgentModel).offset(offset).limit(limit).order_by(AgentModel.created_at.desc())
    if user.role != "admin":
        stmt = stmt.where(AgentModel.owner_id == user.id)
    
    result = await db.execute(stmt)
    agents = result.scalars().all()
    
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "avatar_url": agent.avatar_url,
            "ci_score": agent.ci_score,
            "criteria": agent.agent_data.get("criteria") if agent.agent_data else {},
            "created_at": agent.created_at.isoformat() if agent.created_at else None
        }
        for agent in agents
    ]

@router.get("/agents/{agent_id}")
async def get_external_agent(
    agent_id: str, 
    user: UserModel = Depends(get_user_by_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve agent data.
    """
    stmt = select(AgentModel).where(AgentModel.id == agent_id)
    if user.role != "admin":
        stmt = stmt.where(AgentModel.owner_id == user.id)
    
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "agent_data": agent.agent_data,
        "created_at": agent.created_at.isoformat() if agent.created_at else None
    }

@router.get("/jobs/{job_id}")
async def get_external_job_status(
    job_id: str,
    user: UserModel = Depends(get_user_by_api_key)
):
    """
    Check the status of a generation job.
    """
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
