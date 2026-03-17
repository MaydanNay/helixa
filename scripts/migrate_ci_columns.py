import asyncio
import logging
from sqlalchemy import text
from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    async with engine.begin() as conn:
        logger.info("Starting migration for Auto-CI columns...")
        
        # We use a simple approach: try to add the column, catch if it already exists
        columns = [
            ("ci_score", "INTEGER"),
            ("ci_passed", "BOOLEAN DEFAULT FALSE"),
            ("ci_report", "JSONB")
        ]
        
        for col_name, col_type in columns:
            try:
                await conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type};"))
                logger.info(f"Successfully added column: {col_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"Column {col_name} already exists, skipping.")
                else:
                    logger.error(f"Error adding column {col_name}: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
