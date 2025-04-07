import pandas as pd
import neo4j
from neo4j import GraphDatabase
import os
import dotenv
import pprint
import yaml


dotenv.load_dotenv()


# data model
    #     elements = {
    #         "nodes": [
    #             {"data": {"id": "joe", "label": "PERSON", "name": "Streamlit"}},
    #             {"data": {"id": 2, "label": "PERSON", "name": "Hello"}},
    #             {"data": {"id": 3, "label": "PERSON", "name": "World"}},
    #             {"data": {"id": 4, "label": "POST", "content": "x", "other": 4000}},
    #             {"data": {"id": 5, "label": "POST", "content": "y"}},
    #         ],
    #         "edges": [
    #             {"data": {"id": 6, "label": "FOLLOWS", "source": "joe", "target": 2}},
    #             {"data": {"id": "alex", "label": "FOLLOWS", "source": 2, "target": 3}},
    #             {"data": {"id": 8, "label": "POSTED", "source": 3, "target": 4}},
    #             {"data": {"id": 9, "label": "POSTED", "source": "joe", "target": 5}},
    #             {"data": {"id": 10, "label": "QUOTES", "source": 5, "target": 4}},
    #         ],
    #     }


def process_neo4j_result(result):
    if not result:
        return {"type": "error", "data": "No result from Neo4j query."}
    
    # PROBLEM TODO: for some reason this query doesn't result in edge data, even though it's very obviously in the result set
    # please run this query exactly: MATCH (parent:biolink_Disease {id: 'MONDO:0020066'}) OPTIONAL MATCH (subD:biolink_Disease)-[r:biolink_subclass_of*]->(parent) RETURN parent, r, subD
    
    # maybe this one too? it triggers an error about missing edge info, but that's just because it really does need to return just a single node
    # MATCH (g:biolink_Gene)-[:biolink_gene_associated_with_condition]->(d:biolink_Disease) WITH g, count(d) as disease_count RETURN g ORDER BY disease_count DESC LIMIT 5
    
    # and this, for "How many different kinds of edges are there?"
    # MATCH ()-[r]->() RETURN DISTINCT type(r) AS relationship_type
    try:
        table_data = []
        graph_data = {"nodes": [], "edges": []}
        data_type = "table"  # default
        # Optionally track nodes/edges we've already added to avoid duplicates
        known_node_ids = set()
        known_edge_ids = set()
        
        for record in result:
            record_data = {}
            
            for key, value in record.items():
                print(f"key: {key}, value: {value}")
                
                # 1. If it's a Node
                if isinstance(value, neo4j.graph.Node):
                    data_type = "graph"
                    _add_node(graph_data, value, known_node_ids)
                
                # 2. If it's a Relationship
                elif isinstance(value, neo4j.graph.Relationship):
                    data_type = "graph"
                    _add_relationship(graph_data, value, known_edge_ids, known_node_ids)
                
                # 3. If it's a Path
                elif isinstance(value, neo4j.graph.Path):
                    data_type = "graph"
                    for node in value.nodes:
                        _add_node(graph_data, node, known_node_ids)
                    for rel in value.relationships:
                        _add_relationship(graph_data, rel, known_edge_ids, known_node_ids)
                
                # 4. Otherwise treat as scalar/table data
                else:
                    record_data[key] = value
            
            # If the record had purely table data (no nodes/relationships/paths),
            # it gets appended as a row to table_data
            table_data.append(record_data)

        # Decide final output format based on whether we found graph data
        if data_type == "graph":
            result = {"type": data_type, "data": graph_data}

        else:
            # if it's table data or a scalar, return it in the LLM-readable format 
            result = {"type": "table", "data": table_data}
            
        import pprint
        print("\n\n\n\n\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        pprint.pprint(result["data"]["edges"])
        return result
    
        
    except Exception as e:
        return {"type": "error", "data": str(e)}
 

def _add_node(graph_data, node, known_node_ids):
    """
    Helper to add a node to graph_data if it's not already known.
    """
    # We can use either the Neo4j internal ID or a property-based ID
    node_props = dict(node)
    node_internal_id = node.get("id")  # The numeric internal id
    # Or use the 'id' property if you prefer:
    # node_id = node_props.get("id", str(node_internal_id))
    
    if node_internal_id in known_node_ids:
        return  # skip duplicates
    known_node_ids.add(node_internal_id)
    
    # Choose a caption
    caption = node_props.get("name") or node_props.get("symbol") or f"{node_internal_id}"
    
    # Build node data
    node_data = {
        "id": str(node_internal_id),  # or node_props.get("id", str(node_internal_id))
        "caption": caption
    }
    
    # Merge remaining props
    for k, v in node_props.items():
        node_data[k] = v


    graph_data["nodes"].append({"data": node_data})


def _add_relationship(graph_data, relationship, known_edge_ids, known_node_ids):
    """
    Helper to add a relationship to graph_data if it's not already known.
    Also ensures the relationship's start and end nodes exist in graph_data.
    """

    # 1) Ensure the start and end nodes exist in the graph data
    _add_node(graph_data, relationship.start_node, known_node_ids)
    _add_node(graph_data, relationship.end_node, known_node_ids)

    # 2) Check if we've seen this relationship before
    rel_id = relationship.get("id")
    if rel_id in known_edge_ids:
        return
    known_edge_ids.add(rel_id)

    # 3) Build the edge data
    rel_props = dict(relationship)
    edge_data = {
        "id": str(rel_id),
        "caption": relationship.type,  # relationship type as the "caption"
        "source": str(relationship.start_node.get("id")),
        "target": str(relationship.end_node.get("id")),
        "label": relationship.type,  # relationship type as the "label"
    }
    
    # 4) Include any additional relationship properties
    for k, v in rel_props.items():
        if k not in ["id", "type"]:
            edge_data[k] = v

    # 5) Append the edge
    graph_data["edges"].append({"data": edge_data})




# neo4j_uri = os.environ["NEO4J_URI"]  # default bolt protocol port

# neo4j_driver = GraphDatabase.driver(neo4j_uri)


# with neo4j_driver.session() as session:

#     # Example usage with a Neo4j query result
#     #result = session.run("MATCH path = (a)-[r]->(b)-[r2]->(c) RETURN path LIMIT 1")
#     #result = session.run("MATCH path = (a)-[r]->(b) RETURN a, r, b LIMIT 1")
#     result = session.run("MATCH path = (a)-[r]->(b) RETURN r LIMIT 1")
#     #result = session.run("MATCH path = (a)-[r]->(b) RETURN a.id, b.id LIMIT 5")
#     #result = session.run("RETURN 4")
#     processed_result = process_neo4j_result(result)
#     pprint.pprint(processed_result)
    