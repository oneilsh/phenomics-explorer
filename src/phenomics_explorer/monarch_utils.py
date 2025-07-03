# we need an ordered dict
from collections import OrderedDict
from st_link_analysis import NodeStyle, EdgeStyle
import dotenv
import re
import yaml
import json
import importlib.resources
import os

from phenomics_explorer.monarch_constants import categories


def munge_monarch_data(data):
    """Takes the result of parse_neo4j_result and selects and replaces some fields and values specifically of interest for the Monarch KG."""
    data['result_as_graph']['data'] = munge_monarch_graph_result(data['result_as_graph']['data'])

    # if theres a ['result_as_table']['data']['nodes'] key, we munge it
    if 'result_as_table' in data and 'data' in data['result_as_table'] and 'nodes' in data['result_as_table']['data']:
        data['result_as_table']['data'] = munge_monarch_table_result(data['result_as_table']['data'])
    return data


def munge_monarch_table_result(result_data):
    # there's not anything to do, but leaving this temporarily in case we want to do something later
    return result_data


def munge_monarch_graph_result(result_data):
    """Takes a graph result from a neo4j query selects specific properties of interest, reducing the size and making it more interpretable for the LLM."""
    # ... we don't want to keep all of the node and edge properties - it's too much info
    import pprint
    pprint.pprint(result_data, indent=2)
    for node in result_data['nodes']:
        node['data'] = {k: v for k, v in node['data'].items() if k in ['id', 'name', 'symbol', 'description', 'full_name', 'in_taxon_label', 'caption', 'category']}
    for edge in result_data['edges']:
        edge['data'] = {k: v for k, v in edge['data'].items() if k in ['id', 'subject', 'predicate', 'object', 'primary_knowledge_source', 'publications', 'has_evidence', 'caption', 'source', 'target', 'label'] or 'negated' in k or 'qualifier' in k}

    # we want to keep *one* category to represent each node, from the ordered list of categories above
    for node in result_data['nodes']:
        for cat in categories:
            if 'category' in node['data'] and node['data']['category'] is not None:
                if cat in node['data']['category']:
                    node['data']['category'] = cat
                    break

    # set each nodes' label attribute to be the category
    for node in result_data['nodes']:
        if 'category' in node['data'] and node['data']['category'] is not None:
            node['data']['label'] = node['data']['category']

    return result_data


def fix_biolink_labels(query):
    # Regular expression to match (g:biolink_somelabel)
    pattern = r'biolink_([a-zA-Z0-9_]+)'

    # Replace with backticks and a colon
    replacement = r'`biolink:\1`'

    res = re.sub(pattern, replacement, query)
    return res
