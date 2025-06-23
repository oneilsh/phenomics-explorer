# we need an ordered dict
from collections import OrderedDict
from st_link_analysis import NodeStyle, EdgeStyle
import dotenv
import re
import yaml
import json
import importlib.resources
import os

dotenv.load_dotenv()


from neo4j import GraphDatabase

neo4j_driver = GraphDatabase.driver(os.environ["NEO4J_URI"])


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


#### QUALIFIERS ####
qualifiers = []

sex_qualifiers = [
    {"id": "PATO:0000383", "label": "Female"},
    {"id": "PATO:0000384", "label": "Male"},
]
qualifiers.extend(sex_qualifiers)

# these are actually more human-friendly synonyms for these qualifier labels
evidence_qualifiers = [
    {"id": "ECO:0000304", "label": "traceable author statement"},
    {"id": "ECO:0006017", "label": "published clinical study evidence"},
    {"id": "ECO:0000501", "label": "inferred from electronic annotation"},
]
qualifiers.extend(evidence_qualifiers)

## onset qualifiers
with neo4j_driver.session() as session:
    result = session.run("MATCH (n:`biolink:PhenotypicFeature` {id: 'HP:0003674'}) <-[r:`biolink:subclass_of`*]- (m:`biolink:PhenotypicFeature`) RETURN m.id AS id, m.name AS name")
    onset_ids = [{"id": record['id'], "label": record['name']} for record in result]
    qualifiers.extend(onset_ids)


## frequency qualifiers
with neo4j_driver.session() as session:
    result = session.run("MATCH (n:`biolink:PhenotypicFeature` {id: 'HP:0040279'}) <-[r*]- (m) RETURN m.id AS id, m.name AS name")
    frequency_ids = [{"id": record['id'], "label": record['name']} for record in result]
    qualifiers.extend(frequency_ids)

import pandas as pd
# print the qualifiers as a table for easy copy/pasting
def print_qualifiers_as_table(qualifiers):
    """Prints the qualifiers as a pandas DataFrame for easy copy/pasting."""
    df = pd.DataFrame(qualifiers)
    df = df.sort_values(by='id')  # sort by id
    print(df.to_markdown(index=False))

print("Sex qualifiers:")
print_qualifiers_as_table(sex_qualifiers)
print("Onset qualifiers:")
print_qualifiers_as_table(onset_ids)
print("Frequency qualifiers:")
print_qualifiers_as_table(frequency_ids)
print("Evidence qualifiers:")
print_qualifiers_as_table(evidence_qualifiers)

def munge_qualifiers(data):
    """Given any structure, looks for values that match keys in the qualifiers dictionary and replaces them with 'ID (Label)'."""
    if isinstance(data, dict):
        return {k: munge_qualifiers(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [munge_qualifiers(item) for item in data]
    elif isinstance(data, str):
        # Check if the string is a key in the qualifiers dictionary
        if data in [q['id'] for q in qualifiers]:
            # Find the corresponding qualifier
            qualifier = next((q for q in qualifiers if q['id'] == data), None)
            if qualifier:
                return f"{qualifier['id']} ({qualifier['label']})"
    else:
        return data


def munge_monarch_data(data):
    """Takes the result of parse_neo4j_result and selects and replaces some fields and values specifically of interest for the Monarch KG."""
    data['result_as_graph']['data'] = munge_monarch_graph_result(data['result_as_graph']['data'])

    # if theres a ['result_as_table']['data']['nodes'] key, we munge it
    if 'result_as_table' in data and 'data' in data['result_as_table'] and 'nodes' in data['result_as_table']['data']:
        data['result_as_table']['data'] = munge_monarch_table_result(data['result_as_table']['data'])
    return data


def munge_monarch_table_result(result_data):
    # there's not really much to do, except munge the qualifiers
    return munge_qualifiers(result_data)


def munge_monarch_graph_result(result_data):
    """Takes a graph result from a neo4j query and munges it into a format that can be used by the streamlit app"""
    # ... we don't want to keep all of the node and edge properties - it's too much info
    for node in result_data['nodes']:
        node['data'] = {k: v for k, v in node['data'].items() if k in ['id', 'name', 'symbol', 'description', 'full_name', 'in_taxon_label', 'caption', 'category']}
    for edge in result_data['edges']:
        edge['data'] = {k: v for k, v in edge['data'].items() if k in ['id', 'subject', 'predicate', 'object', 'primary_knowledge_source', 'publications', 'has_evidence', 'caption', 'source', 'target', 'label'] or 'negated' in k or 'qualifier' in k}

    # we want to keep *one* category to represent each node, from the ordered list of categories above
    for node in result_data['nodes']:
        for cat in categories:
            if cat in node['data']['category']:
                node['data']['category'] = cat
                break

    # set each nodes' label attribute to be the category
    for node in result_data['nodes']:
        node['data']['label'] = node['data']['category']

    return munge_qualifiers(result_data)


def fix_biolink_labels(query):
    # Regular expression to match (g:biolink_somelabel)
    pattern = r'biolink_([a-zA-Z0-9_]+)'

    # Replace with backticks and a colon
    replacement = r'`biolink:\1`'

    res = re.sub(pattern, replacement, query)
    return res


graph_summary = ""
with importlib.resources.files("phenomics_explorer").joinpath("kg_summary.md").open("r") as f:
    graph_summary = f.read()
    
# example_queries_str = ""
# with open("monarch_competency_questions_1.yaml", "r") as f:
#     example_queries_str = f.read()

# these are lines not matching "expected_answer"
example_queries = None
with importlib.resources.files("phenomics_explorer").joinpath("monarch_competency_questions_1.yaml").open("r") as f:
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
