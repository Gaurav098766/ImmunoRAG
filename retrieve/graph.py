# retrieve/graph.py
"""
L6 — Query the Neo4j knowledge graph for entity relationships.

Given an entity name (drug, target, condition, or cell type), finds all
relationships connected to it in either direction, with source paper
traceability via the source_pmcid property on each relationship.

Requires Neo4j running: docker compose up -d neo4j

Run interactively:
    uv run python -m retrieve.graph
"""

from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def find_entity_connections(entity_name: str, limit: int = 20) -> list[dict]:
    """
    Find all relationships connected to entities matching entity_name
    (case-insensitive partial match), in either direction.

    Returns a list of dicts: {entity, relation, direction, connected_to,
    connected_type, source_pmcid}
    """
    driver = get_driver()
    query = """
    MATCH (a)-[r]-(b)
    WHERE toLower(a.name) CONTAINS toLower($entity_name)
    RETURN
        a.name AS entity,
        type(r) AS relation,
        CASE WHEN startNode(r) = a THEN 'outgoing' ELSE 'incoming' END AS direction,
        b.name AS connected_to,
        labels(b)[0] AS connected_type,
        r.source_pmcid AS source_pmcid
    LIMIT $limit
    """

    with driver.session() as session:
        result = session.run(query, entity_name=entity_name, limit=limit)
        return [dict(record) for record in result]


def find_entities_by_type(entity_type: str, limit: int = 20) -> list[str]:
    """
    List entity names of a given type (Drug, Target, CellType, Condition).
    Useful for exploring what's actually in the graph.
    """
    driver = get_driver()
    query = f"""
    MATCH (n:{entity_type})
    RETURN DISTINCT n.name AS name
    LIMIT $limit
    """

    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [record["name"] for record in result]


def main():
    print("ImmunoRAG — Knowledge Graph Query")
    print("Enter an entity name to find its connections, or 'quit' to exit.")
    print("Example: pembrolizumab\n")

    while True:
        entity = input("Entity> ").strip()
        if entity.lower() in ("quit", "exit"):
            break
        if not entity:
            continue

        connections = find_entity_connections(entity)
        if not connections:
            print(f"No connections found for '{entity}'.\n")
            continue

        print(f"\nFound {len(connections)} connection(s):")
        for c in connections:
            arrow = "->" if c["direction"] == "outgoing" else "<-"
            print(f"  {c['entity']} {arrow}[{c['relation']}]{arrow} {c['connected_to']} "
                  f"({c['connected_type']}) [source: {c['source_pmcid']}]")
        print()


if __name__ == "__main__":
    main()