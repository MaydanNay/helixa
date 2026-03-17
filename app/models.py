from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Date
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
import uuid
from app.database import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)
    created_at = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Rate Limiting
    generations_today = Column(Integer, default=0)
    last_generation_date = Column(Date, nullable=True)
    
    # Helixa Connect (External API)
    api_key = Column(String, unique=True, index=True, nullable=True)

class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    original_job_id = Column(String, index=True, nullable=True)
    name = Column(String, index=True)
    role = Column(String)
    avatar_url = Column(String, nullable=True)
    agent_data = Column(JSONB)  # The entire generated DNA profile
    stages_status = Column(JSONB, nullable=True)  # { "demographics": "done", "psychology": "running", ... }
    generation_mode = Column(String, default="soul")  # soul | staged

    # Auto-CI Fields
    ci_score = Column(Integer, nullable=True)
    ci_passed = Column(Boolean, default=False)
    ci_report = Column(JSONB, nullable=True)

    created_at = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class TuringSessionModel(Base):
    __tablename__ = "turing_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    host_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="waiting")  # waiting | active | completed
    settings = Column(JSONB, default={})  # max_participants, duration, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class TuringParticipantModel(Base):
    __tablename__ = "turing_participants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("turing_sessions.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    assigned_alias = Column(String)  # Anonymous name like "Participant 1", "Entity A", etc.
    is_ai = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class TuringMessageModel(Base):
    __tablename__ = "turing_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("turing_sessions.id"), index=True, nullable=False)
    participant_id = Column(String, ForeignKey("turing_participants.id"), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class TuringVoteModel(Base):
    __tablename__ = "turing_votes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("turing_sessions.id"), index=True, nullable=False)
    voter_id = Column(String, ForeignKey("turing_participants.id"), nullable=False)
    target_id = Column(String, ForeignKey("turing_participants.id"), nullable=False)
    vote_is_ai = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

