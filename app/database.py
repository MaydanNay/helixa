from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from app.config import settings

DATABASE_URL = os.getenv(
    "HELIXA_DATABASE_URL",
    settings.helixa_database_url
)

engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    pool_size=20,
    max_overflow=40,
    pool_timeout=30.0,
    pool_recycle=1800
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
