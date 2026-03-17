import asyncio
import os
import sys
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.neo4j_client import graph_memory_service
from app.config import settings

async def verify_fix():
    print("--- Starting Graph Fix Verification ---")
    
    agent_id = "test_agent_123"
    agent_name = "Test Agent"
    
    # 1. Connect
    print("Connecting to Neo4j...")
    await graph_memory_service.connect()
    
    # 2. Cleanup old test data
    print("Cleaning up old test data...")
    async with graph_memory_service.driver.session() as session:
        await session.run("MATCH (n) WHERE n.id = $id OR $id IN coalesce(n.agent_ids, []) DETACH DELETE n", id=agent_id)
    
    # 3. Create Agent Node
    print(f"Creating agent node for {agent_id}...")
    await graph_memory_service.create_agent_node(agent_id, agent_name, "Tester")
    
    # 4. Create an Orpaned Knowledge Node (linked via agent_ids but no edge)
    print("Creating orphaned knowledge node...")
    async with graph_memory_service.driver.session() as session:
        await session.run("""
            MERGE (n:LOCATION {id: 'Secret_Base'})
            SET n.name = 'Secret Base', n.agent_ids = [$agent_id]
        """, agent_id=agent_id)
        
    # 5. Retrieve Full Graph
    print("Retrieving full graph...")
    graph = await graph_memory_service.retrieve_full_graph(agent_id)
    
    nodes = graph.get("nodes", [])
    print(f"Nodes found: {[n['name'] for n in nodes]}")
    
    # 6. Assertion
    has_agent = any(n['id'] == agent_id for n in nodes)
    has_location = any(n['id'] == 'Secret_Base' for n in nodes)
    
    if has_agent and has_location:
        print("\n✅ SUCCESS: Both agent and orphaned location node were retrieved!")
    else:
        print("\n❌ FAILURE: Missing nodes.")
        if not has_agent: print("- Agent node missing")
        if not has_location: print("- Orphaned location node missing")
        
    # Cleanup
    print("\nCleaning up...")
    async with graph_memory_service.driver.session() as session:
        await session.run("MATCH (n) WHERE n.id = $id OR $id IN coalesce(n.agent_ids, []) DETACH DELETE n", id=agent_id)
    
    await graph_memory_service.close()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(verify_fix())
