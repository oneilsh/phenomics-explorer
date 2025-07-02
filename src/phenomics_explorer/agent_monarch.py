from kani_utils.base_kanis import StreamlitKani
from kani import AIParam, ai_function, ChatMessage, ChatRole
from kani.exceptions import WrappedCallException
from typing import Annotated, List
from neo4j import AsyncGraphDatabase
from collections import OrderedDict
from phenomics_explorer.monarch_constants import graph_summary, example_queries_str, categories
from phenomics_explorer.monarch_utils import fix_biolink_labels, munge_monarch_data
from phenomics_explorer.agent_kg_base import BaseKGAgent
import streamlit as st


# for reading API keys from .env file
import os
import json
import httpx

class MonarchKGAgent(BaseKGAgent):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, *args, eval_agent = None, max_response_tokens = 30000, **kwargs):

        kwargs['system_prompt'] = ('''You are the Phenomics Assistant, designed to assist users in exploring and intepreting a biomedical knowledge graph known as Monarch.\n\n''' + 
#self._gen_monarch_instructions() + "\n\n" + 
"# Graph Summary\n\n" + graph_summary + "\n\n" + 
"# Example queries\n\n" + example_queries_str + "\n\n" +
"# Instructions\n\n" + self._gen_monarch_instructions()
)

        super().__init__(*args, **kwargs)

        self.greeting = self.get_monarch_greeting()

        self.description = "Queries the Monarch KG with graph queries and contextual information."
        self.avatar = "🕷️"
        self.user_avatar = "👤"
        self.name = "Phenomics Explorer"

        # dev instance of

        self.max_response_tokens = max_response_tokens
        self.eval_agent = eval_agent

#         self.evaluator_system_prompt = ('''You are the Phenomics Evaluator, designed to evaluate cypher queries against the biomedical knowledge graph known as Monarch.\n\n''' + 
# "# Graph Summary\n\n" + graph_summary + "\n\n" + 
# "# Example queries\n\n" + example_queries_str + "\n\n" +
# '''# Instructions

# - When asked, use your report_evaluation() function to evaluate a given query and its results. Follow the instructions exactly.'''
# )

    @ai_function()
    async def get_entity_types(self):
        """Get the types of entities in the graph. If displaying the result to the user, format them as a multi-column table organized by theme."""
        
        query = "CALL db.labels() YIELD label RETURN label"
        res = await self._call_neo4j(query)

        return res

    @ai_function()
    async def get_relationship_types(self):
        """Get the types of relationships in the graph. If displaying the result to the user, format them as a multi-column table organized by theme."""
        
        query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        res = await self._call_neo4j(query)

        return res
        


    # override the basic neo4j call to fix and munge the result for monarch biolink labels
    async def _call_neo4j(self, query, parameters = None, timeout = 6):
        query = fix_biolink_labels(query)
        res = await super()._call_neo4j(query, parameters = parameters, timeout = timeout)
        res = munge_monarch_data(res)
        return res


    def get_monarch_greeting(self):
        return \
"""
I'm the Phenomics Explorer, an AI with knowledge of the [Monarch Initiative knowledge 
graph](https://monarchinitiative.org/). I can answer questions via complex graph queries. Some things you can ask:

- What genes are associated with Wilson disease? 
- How many phenotypes (traits or symptoms) are associated with the gene that causes CF?
- What phenotypes are associated with more than one subtype of Niemann-Pick disease?
- What kinds of entities do you know about?
- What kinds of relationships do you know about?

*Note that as an AI I occasionally make mistakes. An overview of my operation is available in my [implementation notes](https://github.com/monarch-initiative/phenomics-assistant/blob/phenomics_assistant2/pe_notes.md).*
""".strip()

    def _gen_monarch_instructions(self):
        return f"""
- Consider that the user may not be familiar with the graph structure or the specific terms used in the query.
- Provide non-specialist descriptions of biomedical results.
- Consider relevant relationship qualifiers, especially negated, percentage, onset, and frequency qualifiers when designing queries.
- Use the -[r:biolink_subclass_of*0..]-> pattern liberally to find all subclasses of a class.
- Use `LIMIT`, `ORDER BY` and `SKIP` clauses to manage the size of your results.
- Default to 10 results unless otherwise asked.
- Alert the user if there may be more results, and provide total count information when possible.
- Only answer biomedical questions, using the tools available to you as your primary information source.
- Avoid answers that may be construed as medical advice or diagnoses.
- ALWAYS include links for nodes in the format `[Node Name](https://monarchinitiative.org/nodeid)`.""".strip()


    # we also need to override display_report to fix the query
    def display_report(self, report):
        query = fix_biolink_labels(query)
        super().display_report(report)

    # def get_node_styles(self):
    #     node_category_map = OrderedDict()

    #     # we need a list of colors to use for the categories, which should be a palette
    #     # that is colorblind-friendly and also looks good in a dark theme
    #     # we can use the 'color_palette' function from seaborn to get a list of colors
    #     # that we can use for the categories
    #     # we need hex strings for the colors
    #     colors = sns.color_palette("colorblind", len(categories))
    #     colors = [f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}" for r, g, b in colors]
    #     for cat, color in zip(categories, colors):
    #         node_category_map[cat] = color


    #     # there is going to be a nodestyle assocated with each category; which will be of the form:
    #     # nodestyles = [
    #     # NodeStyle(label="biolink:LifeStage", color=node_category_map["biolink:LifeStage"], caption="caption"),
    #     # ... 
    #     # ]

    #     node_styles = []
    #     for cat, color in node_category_map.items():
    #         node_styles.append(NodeStyle(cat, color, caption="caption"))

    #     return node_styles


    @ai_function()
    async def search(self, 
               search_terms: Annotated[List[str], AIParam(desc="Search terms to look up in the database.")],):
        """Search for nodes matching one or more terms. Each term is searched separately, returning a list of dictionaries."""

        self._status(f"Searching for terms {search_terms}...")

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
            raise WrappedCallException(retry = True, original = ValueError(f"The search result contained {tokens} tokens, greater than the maximum allowable of {self.max_response_tokens}. Please try a smaller search."))
        else:
            return results