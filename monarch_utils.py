# we need an ordered dict
from collections import OrderedDict
import seaborn as sns
from st_link_analysis import NodeStyle, EdgeStyle
import neo4j
import os
from neo4j import GraphDatabase
import dotenv
from textwrap import dedent, indent
from pprint import pformat

dotenv.load_dotenv()


categories = [
'biolink:LifeStage',
'biolink:MolecularEntity',
'biolink:OrganismTaxon',
'biolink:Cell',
'biolink:CellularComponent',
'biolink:MolecularActivity',
'biolink:SequenceVariant',
'biolink:ChemicalEntity',
'biolink:ChemicalOrDrugOrTreatment',
'biolink:GeneProductMixin',
'biolink:Protein',
'biolink:Polypeptide',
'biolink:Pathway',
'biolink:Disease',
'biolink:ChemicalEntityOrProteinOrPolypeptide',
'biolink:BiologicalProcess',
'biolink:Occurrent',
'biolink:BiologicalProcessOrActivity',
'biolink:AnatomicalEntity',
'biolink:OrganismalEntity',
'biolink:SubjectOfInvestigation',
'biolink:Genotype',
'biolink:PhenotypicFeature',
'biolink:DiseaseOrPhenotypicFeature',
'biolink:Gene',
'biolink:MacromolecularMachineMixin',
'biolink:GeneOrGeneProduct',
'biolink:ChemicalEntityOrGeneOrGeneProduct',
'biolink:GenomicEntity',
'biolink:OntologyClass',
'biolink:PhysicalEssence',
'biolink:PhysicalEssenceOrOccurrent',
'biolink:BiologicalEntity',
'biolink:ThingWithTaxon',
'biolink:NamedThing',
'biolink:Entity',
]


node_category_map = OrderedDict()

# we need a list of colors to use for the categories, which should be a palette
# that is colorblind-friendly and also looks good in a dark theme
# we can use the 'color_palette' function from seaborn to get a list of colors
# that we can use for the categories
# we need hex strings for the colors
colors = sns.color_palette("colorblind", len(categories))
colors = [f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}" for r, g, b in colors]
for cat, color in zip(categories, colors):
    node_category_map[cat] = color


# there is going to be a nodestyle assocated with each category; which will be of the form:
# nodestyles = [
# NodeStyle(label="biolink:LifeStage", color=node_category_map["biolink:LifeStage"], caption="caption"),
# ... 
# ]

node_styles = []
for cat, color in node_category_map.items():
    node_styles.append(NodeStyle(cat, color, caption="caption"))


def eval_query_prompt(query, result_dict, messages_history):
    """Generate a prompt for evaluating a query result."""

    # messages_history is a list of ChatMessage objects, which have role and content attributes'
    messages_history = [f"{m.role}: {m.content}" for m in messages_history]

    summary_msg = dedent(f"""\
        I need you to evaluate the result of a graph query. Please review the query and the result yaml and answer the following questions.

        Prior Messages:
        ```
        {indent(pformat(messages_history), " " * 8)}
        ```
                      
        Query: `{query}`

        Result yaml:
        ```
        {indent(pformat(result_dict), " " * 8)}
        ```

        From this information we need:

        1. A summary of how the query works in lay language.
        2. Confirmation that the relationship specifications in the query are directed correctly with respect to the conversation thus far. In particular, be sure that `biolink_sublass_of` relationships are directed appropriately.
        3. The return type of the query, either `"table"`, `"graph"`, or `"scalar"`.
        4. If the result would be a graph, that the query returns edge information via a named variable. For exampple, a query like `MATCH (n:biolink_Gene)-[:biolink_causes]->(m:biolink_Disease) RETURN n, m` does not, but `MATCH (n:biolink_Gene)-[r:biolink_causes]->(m:biolink_Disease) RETURN n, r, m` does. Use `True` for table results.
        5. Confirmation that the query matches the user's intent, in the context of the conversation so far.
        6. Whether the result should be visualized for the user with a displayed table or graph view, considering the size and complexity of the result.
        7. Suggestions for improving the query, if any.

        Report your answer using your report_evaluation() function.
        """)
    
    return summary_msg


def munge_monarch_graph_result(result_data):
    """Takes a graph result from a neo4j query and munges it into a format that can be used by the streamlit app"""
    # ... we don't want to keep all of the node and edge properties - it's too much info
    # for nodes, we will keep (if they exist): 'id', 'name', 'symbol', 'description', 'full_name', 'in_taxon_label', 'synonyms', and 'category'
    # for edges, we will keep (if they exist): 'subject', 'predicate', 'object', 'primary_knowledge_source', 'publications', and 'has_evidence'
    # we also keep the 'caption' property for both nodes and edges

    # TODO: this doesn't feel like the best place to do this? or it is, but monarch and vis-related functionality is hiding over in neo4j_utils
    for node in result_data['nodes']:
        node['data'] = {k: v for k, v in node['data'].items() if k in ['id', 'name', 'symbol', 'description', 'full_name', 'in_taxon_label', 'synonyms', 'caption', 'category']}
    for edge in result_data['edges']:
        edge['data'] = {k: v for k, v in edge['data'].items() if k in ['id', 'subject', 'predicate', 'object', 'primary_knowledge_source', 'publications', 'has_evidence', 'caption', 'source', 'target', 'label']}

    # we want to keep *one* category to represent each node, from the ordered list of categories above

    for node in result_data['nodes']:
        for cat in node_category_map.keys():
            if cat in node['data']['category']:
                node['data']['category'] = cat
                break

    # set each nodes' label attribute to be the category
    for node in result_data['nodes']:
        node['data']['label'] = node['data']['category']

    return result_data