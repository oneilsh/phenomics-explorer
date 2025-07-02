from kani import AIParam, ai_function, ChatMessage
from kani.exceptions import WrappedCallException
from typing import Annotated, List
from phenomics_explorer.monarch_utils import fix_biolink_labels, munge_monarch_data
from phenomics_explorer.agent_kgbase import BaseKGAgent
import phenomics_explorer.monarch_constants as C
import json
import httpx

class MonarchKGAgent(BaseKGAgent):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.greeting = C.monarch_greeting

        self.description = "Queries the Monarch KG with graph queries and contextual information."
        self.avatar = "🕷️"
        self.user_avatar = "👤"
        self.name = "Monarch Explorer"

        self.update_system_prompt(C.monarch_system_prompt)


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
        

    @ai_function()
    def implementation_details(self):
        """Get your implmentation details. When responding to queries about your operation, provide information about the graph database, how queries are executed and evaluated, and potential issues and future directions. Suggest some potential followup questions."""
        
        return C.implementation_notes

    # override the basic neo4j call to fix and munge the result for monarch biolink labels
    async def _call_neo4j(self, query, parameters = None, timeout = 6):
        query = fix_biolink_labels(query)
        res = await super()._call_neo4j(query, parameters = parameters, timeout = timeout)
        res = munge_monarch_data(res)
        return res


    # we also need to override display_report to fix the query
    def display_report(self, report):
        query = fix_biolink_labels(query)
        super().display_report(report)


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