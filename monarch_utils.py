# we need an ordered dict
from collections import OrderedDict
from st_link_analysis import NodeStyle, EdgeStyle
import dotenv
import re
import yaml
import json

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





def munge_monarch_graph_result(result_data):
    """Takes a graph result from a neo4j query and munges it into a format that can be used by the streamlit app"""
    # ... we don't want to keep all of the node and edge properties - it's too much info
    # for nodes, we will keep (if they exist): 'id', 'name', 'symbol', 'description', 'full_name', 'in_taxon_label', 'synonyms', and 'category'
    # for edges, we will keep (if they exist): 'subject', 'predicate', 'object', 'primary_knowledge_source', 'publications', and 'has_evidence'
    # we also keep the 'caption' property for both nodes and edges

    for node in result_data['nodes']:
        node['data'] = {k: v for k, v in node['data'].items() if k in ['id', 'name', 'symbol', 'description', 'full_name', 'in_taxon_label', 'caption', 'category']}
    for edge in result_data['edges']:
        edge['data'] = {k: v for k, v in edge['data'].items() if k in ['id', 'subject', 'predicate', 'object', 'primary_knowledge_source', 'publications', 'has_evidence', 'caption', 'source', 'target', 'label']}

    # we want to keep *one* category to represent each node, from the ordered list of categories above

    for node in result_data['nodes']:
        for cat in categories:
            if cat in node['data']['category']:
                node['data']['category'] = cat
                break

    # set each nodes' label attribute to be the category
    for node in result_data['nodes']:
        node['data']['label'] = node['data']['category']

    return result_data


def fix_biolink_labels(query):
    # Regular expression to match (g:biolink_somelabel)
    pattern = r'biolink_([a-zA-Z0-9_]+)'

    # Replace with backticks and a colon
    replacement = r'`biolink:\1`'

    res = re.sub(pattern, replacement, query)
    return res


graph_summary = ""
with open("kg_summary.md", "r") as f:
    graph_summary = f.read()
    
# example_queries_str = ""
# with open("monarch_competency_questions_1.yaml", "r") as f:
#     example_queries_str = f.read()

# these are lines not matching "expected_answer"
example_queries = None
yaml_file = "monarch_competency_questions_1.yaml"
with open(yaml_file, "r") as f:
    example_queries = yaml.safe_load(f)

# we want a string version of the result, with a blank line between each entry
example_queries_str = ""
for query in example_queries:
    # remove the "expected_answer" key from each query
    if "expected_answer" in query:
        del query["expected_answer"]

    # we need the keys to be in the order question, search_terms, query
    example_queries_str += f"question: {query['question']}\n"
    example_queries_str += f"search_terms: {query['search_terms']}\n"
    example_queries_str += f"query: {query['query']}"
    # add a blank line between each query
    example_queries_str += "\n\n"

    # add the query dictionary to the string using yaml.dump
# remove the last two newlines
example_queries_str = example_queries_str[:-2]
