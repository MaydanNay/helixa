import asyncio
import logging
from app.database import AsyncSessionLocal
from app.models import AgentModel
from app.worker import run_auto_ci
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_ci():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AgentModel).where(AgentModel.ci_score == None))
        agents = result.scalars().all()
        
        logger.info(f"Found {len(agents)} agents without CI scores.")
        
        for agent in agents:
            logger.info(f"Running Auto-CI for agent {agent.id} ({agent.name})...")
            try:
                # We need to run this outside the session to avoid nested transactions if the worker uses session
                # But run_auto_ci creates its own session, so it's fine.
                await run_auto_ci(agent.id)
            except Exception as e:
                logger.error(f"Failed to run CI for {agent.id}: {e}")

if __name__ == "__main__":
    asyncio.run(backfill_ci())
