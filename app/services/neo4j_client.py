import os
import logging
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

from app.config import settings

class GraphMemoryService:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", settings.neo4j_uri)
        self.password = os.getenv("NEO4J_PASSWORD", settings.neo4j_password)
        self.user = "neo4j"
        self.driver = None

    async def connect(self):
        if not self.driver:
            logger.info("Connecting to Neo4j...")
            self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))
            try:
                await self.driver.verify_connectivity()
                logger.info("Successfully connected to Neo4j.")
                await self._create_indexes()
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise e

    async def _create_indexes(self):
        """Creates indexes to optimize graph queries."""
        labels = ["AGENT", "LOCATION", "ORGANIZATION", "ITEM", "GOAL", "ENTITY"]
        try:
            async with self.driver.session() as session:
                for label in labels:
                    await session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id)")
            logger.info("Ensured Neo4j indexes are created.")
        except Exception as e:
            logger.warning(f"Failed to create Neo4j indexes (Neo4j Community might not support all index types silently): {e}")

    async def close(self):
        if self.driver:
            await self.driver.close()
            logger.info("Closed Neo4j connection.")

    async def create_agent_node(self, agent_id: str, name: str, role: str):
        """Creates a primary node for the agent in the graph upon generation."""
        query = """
        MERGE (a:AGENT {id: $agent_id})
        SET a.name = $name, a.role = $role
        RETURN a
        """
        async def _create_node(tx):
            result = await tx.run(query, agent_id=agent_id, name=name, role=role)
            return await result.single()

        try:
            await self.connect()
            async with self.driver.session() as session:
                record = await session.execute_write(_create_node)
                logger.info(f"Created/Updated Agent Node in Neo4j: {name} ({agent_id})")
                return record
        except Exception as e:
            logger.error(f"Error creating agent node in Neo4j: {e}")

    async def ingest_knowledge_graph(self, kg_data: dict, source_agent_id: str = None):
        """
        Ingests the extracted Knowledge Graph (nodes and edges) into Neo4j.
        kg_data format: {"nodes": [...], "edges": [...]}

        Important: node IDs are text-based (e.g. "Москва_Город"), not UUIDs,
        so multiple agents can share the same node via MERGE. We track ownership
        via the `agent_ids` list property, which is never overwritten — only appended to.
        """
        if not kg_data or ("nodes" not in kg_data and "edges" not in kg_data):
            return

        nodes = kg_data.get("nodes", [])
        edges = kg_data.get("edges", [])
        
        try:
            await self.connect()
            async with self.driver.session() as session:
                
                # 1. Create/Merge Nodes — append to agent_ids list (never overwrite)
                for node in nodes:
                    node_id = node.get("id")
                    name = node.get("name", node_id)
                    n_type = node.get("type", "ENTITY")
                    
                    safe_type = ''.join(c for c in n_type if c.isalnum() or c == '_').upper()
                    if not safe_type: safe_type = "ENTITY"

                    if source_agent_id:
                        # Use list to support multiple agents owning the same node
                        query = f"""
                        MERGE (n:{safe_type} {{id: $node_id}})
                        SET n.name = $name
                        WITH n
                        WHERE NOT $agent_id IN coalesce(n.agent_ids, [])
                        SET n.agent_ids = coalesce(n.agent_ids, []) + [$agent_id]
                        """
                        await session.run(query, node_id=node_id, name=name, agent_id=source_agent_id)
                    else:
                        query = f"""
                        MERGE (n:{safe_type} {{id: $node_id}})
                        SET n.name = $name
                        """
                        await session.run(query, node_id=node_id, name=name)

                # 2. Create/Merge Edges
                for edge in edges:
                    source_id = edge.get("source")
                    target_id = edge.get("target")
                    e_type = edge.get("type", "RELATED_TO")
                    props = edge.get("properties", {})
                    
                    if not source_id or not target_id:
                        continue

                    safe_e_type = ''.join(c for c in e_type if c.isalnum() or c == '_').upper()
                    if not safe_e_type: safe_e_type = "RELATED_TO"

                    query = f"""
                    MATCH (source {{id: $source_id}})
                    MATCH (target {{id: $target_id}})
                    MERGE (source)-[r:{safe_e_type}]->(target)
                    SET r += $props
                    """
                    await session.run(query, source_id=source_id, target_id=target_id, props=props)

            logger.info(f"Ingested {len(nodes)} nodes and {len(edges)} edges into Neo4j Graph.")
        except Exception as e:
            logger.error(f"Error ingesting knowledge graph into Neo4j: {e}")

    async def retrieve_agent_context(self, agent_id: str, limit: int = 15) -> str:
        """
        Retrieves the 1-hop neighborhood for the given agent from Neo4j
        and formats it as a list of readable semantic facts.
        """
        query = """
        MATCH (n)
        WHERE n.id = $agent_id OR $agent_id IN coalesce(n.agent_ids, [])
        WITH n
        OPTIONAL MATCH (n)-[r]->(target)
        RETURN n.id as node_id, labels(n)[0] AS node_label, n.name AS node_name, 
               type(r) AS rel_type, properties(r) AS rel_props,
               labels(target)[0] AS target_label, target.name AS target_name
        LIMIT $limit
        """
        facts = []
        try:
            await self.connect()
            async with self.driver.session() as session:
                result = await session.run(query, agent_id=agent_id, limit=limit)
                records = await result.data()
                
                for rec in records:
                    node_id = rec.get("node_id")
                    node_name = rec.get("node_name", "Unknown")
                    node_label = rec.get("node_label", "ENTITY")
                    rel = rec.get("rel_type")
                    t_name = rec.get("target_name")
                    t_label = rec.get("target_label", "ENTITY")
                    
                    if node_id == agent_id:
                        if rel and t_name:
                            facts.append(f"{node_name} {rel} {t_name} ({t_label})")
                    else:
                        # This is a knowledge node owned by the agent
                        if rel and t_name:
                            facts.append(f"{node_name} {rel} {t_name} ({t_label})")
                        else:
                            facts.append(f"Fact about {node_label}: {node_name}")
                    
        except Exception as e:
            logger.error(f"Error retrieving agent context from Neo4j: {e}")
            
        return "\n".join(facts) if facts else "No strict semantic facts found."

    async def retrieve_full_graph(self, agent_id: str):
        """
        Retrieves nodes and relationships for visualization centered around an agent.
        Returns format: {"nodes": [], "links": []}
        """
        # Purge Cypher to get everything within 2 hops
        query = """
        MATCH (n)
        WHERE n.id = $agent_id OR $agent_id IN coalesce(n.agent_ids, [])
        WITH n
        OPTIONAL MATCH (n)-[r]-(m)
        WITH collect(distinct n) + collect(distinct m) as all_nodes, 
             collect(distinct r) as all_rels
        RETURN [x IN all_nodes WHERE x IS NOT NULL] as all_nodes,
               [x IN all_rels WHERE x IS NOT NULL] as all_rels
        """

        try:
            await self.connect()
            async with self.driver.session() as session:
                result = await session.run(query, agent_id=agent_id)
                record = await result.single()
                
                if not record or not record["all_nodes"]:
                    return {"nodes": [], "links": []}
                
                # Use internal IDs for mapping
                internal_to_uuid = {}
                nodes = []
                
                for node in record["all_nodes"]:
                    if node:
                        # Standardize name and type
                        node_labels = list(node.labels)
                        label = node_labels[0] if node_labels else "ENTITY"
                        
                        uuid = node.get("id") or str(node.id)
                        internal_to_uuid[node.id] = uuid
                        
                        nodes.append({
                            "id": uuid,
                            "name": node.get("name") or node.get("agent_name") or "Unknown",
                            "label": label,
                            "properties": dict(node)
                        })
                
                links = []
                for rel in record["all_rels"]:
                    if rel:
                        s_uuid = internal_to_uuid.get(rel.start_node.id)
                        t_uuid = internal_to_uuid.get(rel.end_node.id)
                        if s_uuid and t_uuid:
                            links.append({
                                "source": s_uuid,
                                "target": t_uuid,
                                "type": rel.type
                            })
                
                return {"nodes": nodes, "links": links}
        except Exception as e:
            logger.error(f"Error retrieving full graph from Neo4j: {e}")
            return {"nodes": [], "links": []}

    async def delete_agent_node(self, agent_id: str):
        """Fully purges an agent from Neo4j with correct isolation:

        Step 1: Remove this agent from all knowledge nodes' agent_ids lists.
        Step 2: Delete knowledge nodes that are now exclusively orphaned:
                - agent_ids list is empty (no other agent owns them), AND
                - no remaining relationships (safe guard against shared nodes)
        Step 3: Delete the AGENT node itself (DETACH to clean up its edges).

        Guarantee: nodes still referenced by another agent (agent_ids not empty
        after removal, or still have relationships) are NEVER deleted.
        """
        # Step 1: Remove this agent from the agent_ids list on all its knowledge nodes
        query_remove_owner = """
        MATCH (n)
        WHERE NOT n:AGENT AND $agent_id IN coalesce(n.agent_ids, [])
        SET n.agent_ids = [x IN n.agent_ids WHERE x <> $agent_id]
        """
        # Step 2: Delete knowledge nodes now fully orphaned (no owners, no connections)
        query_delete_orphans = """
        MATCH (n)
        WHERE NOT n:AGENT
          AND size(coalesce(n.agent_ids, [])) = 0
          AND NOT (n)--()
        DELETE n
        """
        # Step 3: Delete the AGENT node itself
        query_delete_agent = "MATCH (a:AGENT {id: $agent_id}) DETACH DELETE a"

        try:
            await self.connect()
            async with self.driver.session() as session:
                # 1. Remove ownership
                await session.run(query_remove_owner, agent_id=agent_id)
                
                # 2. Delete AGENT node first (DETACH removes all its relationships)
                await session.run(query_delete_agent, agent_id=agent_id)
                
                # 3. Delete now-ownerless orphan nodes (they no longer have relationships to the deleted agent)
                # Note: We still use NOT (n)--() as a safety catch for shared nodes that might have other relations
                query_delete_final = """
                MATCH (n)
                WHERE NOT n:AGENT
                  AND size(coalesce(n.agent_ids, [])) = 0
                  AND NOT (n)--()
                DELETE n
                """
                result = await session.run(query_delete_final)
                summary = await result.consume()
                orphans_deleted = summary.counters.nodes_deleted

            logger.info(
                "Deleted agent %s from Neo4j: AGENT node + %d exclusive orphan knowledge nodes",
                agent_id, orphans_deleted
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting agent node in Neo4j: {e}")
            return False


    async def wipe_all_data(self):
        """DANGER ZONE: Wipes the entire Neo4j database."""
        query = "MATCH (n) DETACH DELETE n"
        try:
            await self.connect()
            async with self.driver.session() as session:
                await session.run(query)
                logger.warning("Wiped entire Neo4j database.")
        except Exception as e:
            logger.error(f"Error wiping Neo4j database: {e}")

# Singleton instance
graph_memory_service = GraphMemoryService()
