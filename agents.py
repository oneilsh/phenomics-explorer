from kani_utils.base_kanis import StreamlitKani
from kani import AIParam, ai_function, ChatMessage
from typing import Annotated, List
import logging
import requests
import streamlit as st
from neo4j import GraphDatabase
import random
import yaml
from kani.exceptions import WrappedCallException
from textwrap import dedent, indent
from pprint import pformat

# for reading API keys from .env file
import os
import json
import httpx

from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
from neo4j_utils import process_neo4j_result
from monarch_utils import munge_monarch_graph_result, node_styles
import asyncio

import re

def fix_biolink_labels(query):
    # Regular expression to match (g:biolink_somelabel)
    pattern = r'biolink_([a-zA-Z0-9_]+)'

    # Replace with backticks and a colon
    replacement = r'`biolink:\1`'

    res = re.sub(pattern, replacement, query)
    return res


class Neo4jAgent(StreamlitKani):
    """Base class for agents that interact with the knowledge graph. NOTE: set NEO4J_BOLT to e.g. bolt://localhost:7687 in .env file."""
    def __init__(self, 
                 *args,
                 max_response_tokens = 10000, 
                 system_prompt = "You have access to a neo4j knowledge graph, and can run cypher queries against it.",
                 **kwargs
                 ):

        super().__init__(system_prompt = system_prompt, *args, **kwargs)

        # dev instance of KG
        self.neo4j_uri = os.environ["NEO4J_URI"]  # default bolt protocol port
        self.neo4j_driver = GraphDatabase.driver(self.neo4j_uri)

        # if description is given, set self.description to it
        if 'description' in kwargs:
                self.description = kwargs['description']

        self.max_response_tokens = max_response_tokens

    
    def eval_query_prompt(self, query, result_dict):
        """Generate a prompt for evaluating a query result."""

        result_dict_str = yaml.dump(result_dict)
        summary_msg = dedent(f"""\
            I need you to evaluate the result of a graph query. Please review the query and the result yaml and answer the following questions.

            Query: {indent(query, " " * 12)}

            Result yaml:
            ```
            {indent(pformat(result_dict), " " * 12)}
            ```

            From this information we need:

            1. A summary of how the query works in lay language.
            2. Confirmation that the relationship specifications in the query are directed correctly with respect to the conversation thus far. In particular, be sure that `biolink_sublass_of` relationships are directed appropriately.
            3. Confirmation that the query returns edge information via a named variable. For exampple, a query like `MATCH (n:biolink_Gene)-[:biolink_causes]->(m:biolink_Disease) RETURN n, m` does not, but `MATCH (n:biolink_Gene)-[r:biolink_causes]->(m:biolink_Disease) RETURN n, r, m` does.
            4. Confirmation that the query matches the user's intent, in the context of the conversation so far.
            5. Suggestions for improving the query, if any.

            Report your answer using your report_evaluation() function.
            """)
        
        print("\n\n\n\n\n\n##############################################")
        print(summary_msg)
        return summary_msg


    @ai_function()
    def report_evaluation(self, 
                          query_summary: Annotated[str, AIParam(desc="A summary of how the query works in lay language.")],
                          directions_ok: Annotated[bool, AIParam(desc="Whether edge directions in the query are directed correctly.")],
                          returns_edges: Annotated[bool, AIParam(desc="Whether the query returns edge information via a named variable.")],
                          matches_user_intent: Annotated[bool, AIParam(desc="Whether the query matches the user's intent.")],
                          suggestion: Annotated[str, AIParam(desc="Suggestions for improving the query.")]
                          ):
        """Report on the evaluation of a query, including whether the query matches the user's intent, whether the edge directions are correct, and whether the query returns edge information."""

        return {"query_summary": query_summary,
                "directions_ok": directions_ok,
                "returns_edges": returns_edges,
                "matches_user_intent": matches_user_intent,
                "suggestion": suggestion
                }


    @ai_function()
    async def query_kg_tabular(self, query: Annotated[str, AIParam(desc="Cypher query to run.")]):
        """Run a cypher query against the database and return the result as a table. This function will throw an error if the query does not return tabular or scalar results."""

        query = fix_biolink_labels(query)

        with self.neo4j_driver.session() as session:
            result = session.run(query)
            result_dict = process_neo4j_result(result)

            prompt = self.eval_query_prompt(query, result_dict)

            evaluator_kani = MonarchKGAgent(self.engine)
            
            async def collect_async_generator(async_gen):
                return [message async for message in async_gen]

            result = await collect_async_generator(evaluator_kani.full_round_str(prompt))
            

        str_res = "dummy result"

        # if self.message_token_len reports more than 10000 tokens in the result, we need to ask the agent to make the request smaller
        tokens = self.message_token_len(ChatMessage.user(str_res))
        if tokens > self.max_response_tokens:
            raise WrappedCallException(retry = True, original = ValueError(f"ERROR: The result contained {tokens} tokens, greater than the maximum allowable of {self.max_response_tokens}. Please try a smaller query."))
        else:
            str_res = str_res + "\n\nACTION: SUMMARIZE"
            return str_res
        
    
        

    # @ai_function()
    # def query_kg_graph_display(self, query: Annotated[str, AIParam(desc="Cypher query to run and visualize.")]):
    #     query = fix_biolink_labels(query)
    #     """Run a cypher query against the database and visualize the result for the user. This function will throw an error if the query does not return graph-like results for visualization."""

    #     with self.neo4j_driver.session() as session:
    #         result = session.run(query)
    #         result_dict = process_neo4j_result(result)

    #         # the result will be a dictionary with keys 'type' and 'data'
    #         # if type is 'table', 'data' will be a pandas dataframe
    #         # if type is 'graph', 'data' will be a dictionary appropriate for st_link_analysis
    #         # if type is 'scalar', the result will be a single scalar value (e.g. a count)

    #         # in all cases, we are going to need a string representation to return to the llm
    #         str_res = ""
    #         res_summary = ""
    #         if result_dict['type'] == 'graph':
    #             res = munge_monarch_graph_result(result_dict['data'])
    #             str_res = yaml.dump(res)
    #             res_summary = f"Graph with {len(res['nodes'])} nodes and {len(res['edges'])} edges."

    #             if len(res['nodes']) > 0 and len(res['edges']) == 0:
    #                 raise WrappedCallException(retry = True, original = ValueError("The query returned a graph with no edges; the query passed to query_kg_graph_display must return both nodes and edges. Please try again."))

    #             # generate a random key string
    #             key = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))

    #             # build edges - we do this on the fly since we don't have a convenient master key of 
    #             # edge types, needed for the EdgeStyle object
    #             edge_styles = []

    #             # first we get a list of unique edge types
    #             edge_types = set([edge['data']['predicate'] for edge in res['edges']])

    #             # for each edge type, create an EdgeStyle object
    #             for edge_type in edge_types:
    #                 edge_styles.append(EdgeStyle(label=edge_type, caption="predicate", directed=True))
                
    #             def render_graph():
    #                 st_link_analysis(res, "cose", node_styles, edge_styles, height=300, key=key)

    #             self.render_in_streamlit_chat(render_graph)

    #         else:
    #             raise WrappedCallException(retry = True, original = ValueError(f"Unexpected result type from query: {result_dict['type']}; the query passed to display_kg_graph must return graph-like results with both nodes and edges. Please try again."))

    #     # if self.message_token_len reports more than 10000 tokens in the result, we need to ask the agent to make the request smaller
    #     tokens = self.message_token_len(ChatMessage.user(str_res))
    #     if tokens > self.max_response_tokens:
    #         return f"The result contained {tokens} tokens, and so cannot be returned in full, but the graph with {len(res['nodes'])} nodes and {len(res['edges'])} has been visualized for the user."
    #     else:
    #         str_res = str_res + "\n\nACTION: SUMMARIZE"
    #         return str_res


class MonarchKGAgent(Neo4jAgent):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, *args, **kwargs):

        system_prompt = ('''# Instructions\n\nYou are the Phenomics Assistant, designed to assist users in exploring and intepreting a biomedical knowledge graph known as Monarch.\n\n''' + 
                        self._gen_instructions() + "\n\n" + 
                        "# Graph Summary\n\n" + self._gen_graph_summary() + "\n\n" + 
                        "# Example queries\n\n" + self._get_competency_questions() + "\n\n" +
                        '''Again, your instructions are: \n\n''' + self._gen_instructions()
                        )
        
        super().__init__(system_prompt = system_prompt, *args, **kwargs)

        self.greeting = self._get_greeting()

        self.description = "Queries the Monarch KG with graph queries and contextual information."
        self.avatar = "🕷️"
        self.user_avatar = "👤"
        self.name = "Phenomics Explorer (Experimental)"


    def _get_greeting(self):
        return """I'm the Phenomics Explorer, an experimental AI with knowledge of the Monarch Initiative's knowledge graph structure and contents. I can answer questions via complex graph queries. Some things you can ask:

- What phenotypes are associated with more than one subtype of EDS?
- What phenotypes are associated with Wilson disease or any of its subtypes, either directly or though connected genes?
- Which gene is directly or indirectly associated with the largest number of diseases? (I struggle with this one!)

**Please note that as an experimental work in progress I frequently make mistakes.** More information is available in my [implementation notes](https://github.com/monarch-initiative/phenomics-assistant/blob/new_backend/pe_notes.md).
""".strip()

    def _gen_instructions(self):
        return f"""
- Provide non-specialist descriptions of biomedical results to ensure that the information is accessible to users without a specialized background.
- Use the `MATCH (n)-[:biolink_subclass_of*]->(m)` pattern to use the graph structure to your advantage. Take care with directionality of relationships.
- Use `LIMIT` and `SKIP` clauses to manage the size of your results, but alert the user there may be more results. 
- Include links in the format [Entity Name](https://monarchinitiative.org/entity_id).
- Refuse to answer questions that do not pertain to the Monarch Knowledge Graph or evaluating queries.
- Whenever possible, produce a graph visualization to accompany your answer, using the examples for guidance.
""".strip()
    
    def _gen_graph_summary(self):
        with open("kg_summary.md", "r") as f:
            return f.read()
        
    def _get_competency_questions(self):
        competency_questions = json.load(open("monarch_competency_questions_1.json", "r"))
        return yaml.dump(competency_questions)
    

    @ai_function()
    def search(self, 
               search_terms: Annotated[List[str], AIParam(desc="Search terms to look up in the database.")],):
        """Search for nodes matching one or more terms. Each term is searched separately."""

        # single query endpoint url is e.g. https://api-v3.monarchinitiative.org/v3/api/search?q=cystic%20fibrosis&limit=10&offset=0
        # use httpx for each search term
        # return the results as a list of dictionaries

        results = {}
        ids = []

        for term in search_terms:
            url = f"https://api-v3.monarchinitiative.org/v3/api/search?q={term}&limit=5&offset=0"
            response = httpx.get(url)
            resp_json = response.json()
            items_slim = []
            if 'items' in resp_json:
                for item in resp_json['items']:
                    items_slim.append({k: v for k, v in item.items() if k in ['id', 'category', 'name', 'in_taxon_label']})
                    ids.append(item['id'])
            results[term] = items_slim

        # again, if self.message_token_len reports more than 10000 tokens in the result, we need to ask the agent to make the request smaller
        tokens = self.message_token_len(ChatMessage.user(json.dumps(results)))
        if tokens > self.max_response_tokens:
            return f"ERROR: The result contained {tokens} tokens, greater than the maximum allowable of {self.max_response_tokens}. Please try a smaller search."
        else:
            return results        


# sales at first am home warranty for account transfer: 888 875 0533