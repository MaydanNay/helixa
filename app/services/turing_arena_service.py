import logging
import random
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import AgentModel, TuringSessionModel, TuringParticipantModel, TuringMessageModel, TuringVoteModel, UserModel
from app.services.utils import call_llm_with_retries
from app.config import settings
from app.services.audit_service import _get_agent_response

logger = logging.getLogger(__name__)

async def create_turing_session(host_id: str, agent_ids: List[str], db: AsyncSession, max_participants: int = 5) -> Dict[str, Any]:
    """
    Creates a new Turing Arena session with specified agents and host.
    """
    session = TuringSessionModel(
        host_id=host_id,
        settings={"max_participants": max_participants, "agent_ids": agent_ids}
    )
    db.add(session)
    await db.flush() # Get session ID
    
    # Add agents as participants
    for idx, agent_id in enumerate(agent_ids):
        result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            continue
            
        participant = TuringParticipantModel(
            session_id=session.id,
            agent_id=agent_id,
            assigned_alias=f"Entity {chr(65 + idx)}", # Entity A, B, C...
            is_ai=True
        )
        db.add(participant)
    
    await db.commit()
    return {"session_id": session.id, "status": session.status}

async def join_turing_session(session_id: str, user_id: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Adds a human user to the session.
    """
    # Check session exists and is waiting
    result = await db.execute(select(TuringSessionModel).where(TuringSessionModel.id == session_id))
    session = result.scalar_one_or_none()
    if not session or session.status != "waiting":
        return {"error": "Session not found or unavailable"}
    
    # Check if already joined
    participant_check = await db.execute(
        select(TuringParticipantModel).where(
            TuringParticipantModel.session_id == session_id,
            TuringParticipantModel.user_id == user_id
        )
    )
    if participant_check.scalar_one_or_none():
        return {"message": "Already joined"}

    # Determine next alias index for humans
    participants_result = await db.execute(
        select(TuringParticipantModel).where(TuringParticipantModel.session_id == session_id)
    )
    count = len(participants_result.scalars().all())
    
    participant = TuringParticipantModel(
        session_id=session_id,
        user_id=user_id,
        assigned_alias=f"Participant {count + 1}",
        is_ai=False
    )
    db.add(participant)
    await db.commit()
    
    return {"participant_id": participant.id, "alias": participant.assigned_alias}

async def start_turing_session(session_id: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Marks session as active.
    """
    stmt = update(TuringSessionModel).where(TuringSessionModel.id == session_id).values(
        status="active",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "active"}

async def send_turing_message(session_id: str, participant_id: str, content: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Handles user message and triggers AI responses.
    """
    # 1. Save user message
    msg = TuringMessageModel(
        session_id=session_id,
        participant_id=participant_id,
        content=content
    )
    db.add(msg)
    await db.commit()
    
    # 2. Trigger AI agents to respond in background
    # Note: Using AsyncSessionLocal to created a fresh session for background tasks
    from app.database import AsyncSessionLocal
    async def bg_trigger():
        async with AsyncSessionLocal() as bg_db:
            await trigger_ai_responses(session_id, content, bg_db)
            
    asyncio.create_task(bg_trigger())
    
    return {"status": "sent"}

async def trigger_ai_responses(session_id: str, last_message: str, db: AsyncSession):
    """
    Background task to make AI participants respond to the chat.
    """
    # 1. Fetch AI participants
    stmt = select(TuringParticipantModel).where(
        TuringParticipantModel.session_id == session_id,
        TuringParticipantModel.is_ai == True
    )
    result = await db.execute(stmt)
    ais = result.scalars().all()
    
    # 2. Fetch transcript
    transcript_msgs = await get_session_messages(session_id, db)
    history = []
    for m in transcript_msgs:
        history.append({
            "role": "agent" if "Entity" in m["alias"] else "user",
            "content": m["content"]
        })

    # 3. For each AI, decided if it wants to respond
    for ai in ais:
        # Simple logic: 40% chance to respond to any message
        if random.random() > 0.4:
            continue
            
        # Get agent model
        agent_result = await db.execute(select(AgentModel).where(AgentModel.id == ai.agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            continue
            
        # Get AI response
        resp_data = await _get_agent_response(agent, last_message, transcript=history)
        ai_msg_content = resp_data.get("action", "...")
        
        # Save AI message
        ai_msg = TuringMessageModel(
            session_id=session_id,
            participant_id=ai.id,
            content=ai_msg_content
        )
        db.add(ai_msg)
        await db.commit()
        
        # Update history for next AI in loop
        history.append({"role": "agent", "content": ai_msg_content})
        
        # Small delay between AI responses for realism
        await asyncio.sleep(random.uniform(1.0, 3.0))

async def get_session_messages(session_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    stmt = select(TuringMessageModel, TuringParticipantModel.assigned_alias)\
        .join(TuringParticipantModel, TuringMessageModel.participant_id == TuringParticipantModel.id)\
        .where(TuringMessageModel.session_id == session_id)\
        .order_by(TuringMessageModel.created_at)
    
    result = await db.execute(stmt)
    messages = []
    for msg, alias in result:
        messages.append({
            "id": msg.id,
            "alias": alias,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        })
    return messages

async def submit_turing_vote(session_id: str, voter_participant_id: str, target_participant_id: str, is_ai: bool, db: AsyncSession):
    vote = TuringVoteModel(
        session_id=session_id,
        voter_id=voter_participant_id,
        target_id=target_participant_id,
        vote_is_ai=is_ai
    )
    db.add(vote)
    await db.commit()
    return {"status": "voted"}

async def get_session_results(session_id: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Calculates final results for a session.
    """
    # 1. Fetch session and check status
    session_result = await db.execute(select(TuringSessionModel).where(TuringSessionModel.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        return {"error": "Session not found"}
    
    # Optional: If already completed, just return results if they were stored logic?
    # For now, let's just allow recalculation if needed, but mark as completed.

    # 2. Fetch all participants
    participants_result = await db.execute(
        select(TuringParticipantModel).where(TuringParticipantModel.session_id == session_id)
    )
    participants = participants_result.scalars().all()
    participant_map = {p.id: p for p in participants}
    
    # 2. Fetch all votes
    votes_result = await db.execute(
        select(TuringVoteModel).where(TuringVoteModel.session_id == session_id)
    )
    votes = votes_result.scalars().all()
    
    results = {}
    for p in participants:
        results[p.id] = {
            "alias": p.assigned_alias,
            "is_ai": p.is_ai,
            "total_votes_as_ai": 0,
            "total_votes_as_human": 0,
            "correct_guesses": 0,
            "incorrect_guesses": 0
        }
    
    for vote in votes:
        # Update target's stats
        target_stats = results.get(vote.target_id)
        if target_stats:
            if vote.vote_is_ai:
                target_stats["total_votes_as_ai"] += 1
            else:
                target_stats["total_votes_as_human"] += 1
        
        # Update voter's stats
        voter_stats = results.get(vote.voter_id)
        if voter_stats:
            target_is_actually_ai = participant_map[vote.target_id].is_ai
            if vote.vote_is_ai == target_is_actually_ai:
                voter_stats["correct_guesses"] += 1
            else:
                voter_stats["incorrect_guesses"] += 1
                
    # Complete session
    await db.execute(
        update(TuringSessionModel)
        .where(TuringSessionModel.id == session_id)
        .values(status="completed", completed_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    await db.commit()
    
    return {
        "session_id": session_id,
        "participants": list(results.values())
    }
