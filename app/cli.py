import asyncio
import argparse
import json
import os
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import AgentModel
import sys

async def dump_agents(output_dir: str, agent_id: str = None):
    os.makedirs(output_dir, exist_ok=True)
    
    async with AsyncSessionLocal() as session:
        stmt = select(AgentModel)
        if agent_id:
            stmt = stmt.where(AgentModel.id == agent_id)
            
        result = await session.execute(stmt)
        agents = result.scalars().all()
        
        if not agents:
            print("No agents found to export.")
            return

        print(f"Found {len(agents)} agent(s). Exporting to {output_dir}...")
        
        for agent in agents:
            filename_clean = "".join([c if c.isalnum() else "_" for c in (agent.name or "agent")])
            filename = f"{filename_clean}_{agent.id[:8]}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(agent.agent_data, f, ensure_ascii=False, indent=2)
                
            print(f"Exported: {filename}")
            
        print("Export complete.")

def main():
    parser = argparse.ArgumentParser(description="Export agent data to JSON files.")
    parser.add_argument(
        "output_dir", 
        type=str, 
        nargs="?", 
        default="./exports",
        help="Directory to save the JSON files (default: ./exports)"
    )
    parser.add_argument(
        "--id", 
        type=str, 
        help="Export a specific agent by ID instead of all agents"
    )
    
    args = parser.parse_args()
    
    # Run the async dump function
    asyncio.run(dump_agents(args.output_dir, args.id))

if __name__ == "__main__":
    main()
