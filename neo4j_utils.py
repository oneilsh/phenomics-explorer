import json
import yaml

# internal graph data model
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


async def _parse_neo4j_result(result, expected_type = "graph"):
    # ok, we can get a graph with result.graph(), but this might have 0 nodes; if so we 
    if not result:
        return {"type": "error", "data": "No result from Neo4j query."}
    
    if expected_type == "table":
        # looks like [{}]
        parsed = await result.to_df()
        parsed = parsed.to_dict(orient="records")

        return {"type": "table", "data": parsed}

    elif expected_type == "graph":
        parsed = await result.graph()

        node_list = [node for node in parsed.nodes]
        edge_list = [edge for edge in parsed.relationships]

        graph_data = {"nodes": [], "edges": []}
        known_node_ids = set()
        known_edge_ids = set()

        for node in node_list:
            add_node_to_graph_data(graph_data, node, known_node_ids)

        for edge in edge_list:
            add_relationship_to_graph_data(graph_data, edge, known_edge_ids, known_node_ids)

        return {"type": "graph", "data": graph_data}
    else:
        raise ValueError(f"Unknown expected type: {expected_type}. Expected 'graph' or 'table'.")

 

def add_node_to_graph_data(graph_data, node, known_node_ids):
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


def add_relationship_to_graph_data(graph_data, relationship, known_edge_ids, known_node_ids):
    """
    Helper to add a relationship to graph_data if it's not already known.
    Also ensures the relationship's start and end nodes exist in graph_data.
    """

    # 1) Ensure the start and end nodes exist in the graph data
    add_node_to_graph_data(graph_data, relationship.start_node, known_node_ids)
    add_node_to_graph_data(graph_data, relationship.end_node, known_node_ids)

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


def summarize_structure(d):
    """Given a potentially deeply nested list or dictionary, returns only the first couple of elements of each contained list, with the rest replaced by ellipses."""
    if isinstance(d, dict):
        return {k: summarize_structure(v) for k, v in d.items()}
    elif isinstance(d, list) and len(d) > 3:
        return [summarize_structure(v) for v in d[:3]] + ["..."]
    else:
        return d


