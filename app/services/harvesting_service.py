import logging
import httpx
from typing import Dict, Any, List, Optional
from app.config import settings
from app.services.kg_extractor import extract_knowledge_graph
from app.services.neo4j_client import graph_memory_service
from app.services.alem_client import alem_client

logger = logging.getLogger(__name__)

async def tavily_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Performs a web search using Tavily API."""
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set. Cannot perform web search. Returning empty results.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "smart",
        "max_results": limit
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Tavily search failed for query '{query}': {e}")
            return []

async def perform_web_harvest(agent_id: str, agent_name: str, topic: str):
    """
    Autonomously researches a topic on the web and updates the agent's Knowledge Graph.
    """
    logger.info(f"Agent {agent_name} ({agent_id}) is harvesting web knowledge about: {topic}")
    
    # 1. Search
    results = await tavily_search(topic)
    if not results:
        logger.warning(f"No search results for topic: {topic}")
        return {"ok": False, "reason": "no_results"}
    
    # Format search results for LLM
    search_context = "\n\n".join([f"Source: {r.get('url')}\nContent: {r.get('content')}" for r in results])
    
    # 2. Summarize findings
    sys_inst = (
        f"You are the Knowledge Harvester for AI agent {agent_name}. "
        f"Your goal is to extract factual, objective information about '{topic}' that would enrich the agent's world-view."
    )
    user_prompt = (
        f"WEB SEARCH RESULTS FOR '{topic}':\n\n{search_context}\n\n"
        f"TASK: Summarize the key facts found. Focus on entities (people, places, organizations), "
        f"their relationships, and significant events or properties. Write a concise narrative."
    )
    
    summary_resp = await alem_client.create_chat_completion(
        system_instruction=sys_inst,
        user_prompt=user_prompt,
        temperature=0.3
    )
    
    if not summary_resp.get("ok"):
        logger.error(f"LLM Summary failed: {summary_resp.get('error')}")
        return {"ok": False, "error": "llm_summary_failed"}
        
    summary_text = summary_resp.get("output_text", "")
    if not summary_text:
        logger.warning("Empty summary from harvester LLM.")
        return {"ok": False, "reason": "empty_summary"}
    
    # 3. Extract Knowledge Graph
    kg_data = await extract_knowledge_graph(summary_text, agent_id=agent_id, agent_name=agent_name)
    
    # 4. Ingest into Neo4j
    await graph_memory_service.ingest_knowledge_graph(kg_data, source_agent_id=agent_id)
    
    logger.info(f"Web harvest complete for {agent_name} on topic: {topic}")
    return {
        "ok": True,
        "topic": topic,
        "summary": summary_text,
        "nodes_added": len(kg_data.get("nodes", [])),
        "edges_added": len(kg_data.get("edges", []))
    }

async def perform_social_harvest(agent_id: str, agent_name: str, chat_history: str):
    """
    Extracts knowledge from a social interaction and updates the agent's Knowledge Graph.
    """
    logger.info(f"Agent {agent_name} ({agent_id}) is harvesting social knowledge from interaction.")
    
    # 1. Extract Knowledge Graph directly from chat history
    # The extractor is designed to handle this context.
    kg_data = await extract_knowledge_graph(chat_history, agent_id=agent_id, agent_name=agent_name)
    
    # 2. Ingest
    await graph_memory_service.ingest_knowledge_graph(kg_data, source_agent_id=agent_id)
    
    logger.info(f"Social harvest complete for {agent_name}")
    return {
        "ok": True,
        "nodes_added": len(kg_data.get("nodes", [])),
        "edges_added": len(kg_data.get("edges", []))
    }
