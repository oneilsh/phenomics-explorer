from kani_utils.base_kanis import StreamlitKani
from kani import AIParam, ai_function, ChatMessage, ChatRole
from kani.exceptions import WrappedCallException
from typing import Annotated, List
from neo4j import AsyncGraphDatabase
from collections import OrderedDict
import seaborn as sns
from monarch_utils import graph_summary, example_queries_str


# for reading API keys from .env file
import os
import json
import httpx
from st_link_analysis import NodeStyle

from monarch_utils import fix_biolink_labels, graph_summary, munge_monarch_graph_result, categories
from agent_kg_base import BaseKGAgent
import streamlit as st



class MonarchKGAgent(BaseKGAgent):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, *args, max_response_tokens = 10000, **kwargs):

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
        self.name = "Phenomics Explorer (Experimental)"

        # dev instance of
        self.neo4j_uri = os.environ["NEO4J_URI"]  # default bolt protocol port
        self.neo4j_driver = AsyncGraphDatabase.driver(self.neo4j_uri)

        self.max_response_tokens = max_response_tokens

        self.evaluator_system_prompt = ('''You are the Phenomics Evaluator, designed to evaluate cypher queries against the biomedical knowledge graph known as Monarch.\n\n''' + 
"# Graph Summary\n\n" + graph_summary + "\n\n" + 
"# Example queries\n\n" + example_queries_str + "\n\n" +
'''# Instructions

- When asked, use your report_evaluation() function to evaluate a given query and its results. Follow the instructions exactly.'''
)

    ## called on button click
    def edit_system_prompt(self):

        # this is streamlit, see the documentation for @st.dialog()
        # calling this function renders a modal dialog, with the contents
        # of the function definding the contents of the modal
        @st.dialog(title = "Edit System Prompt", width = "large")
        def edit_system_prompt():
            """Edit the system prompt."""
            new_prompt = st.text_area("System Prompt", value=self.system_prompt, height=600, max_chars=20000)
            if st.button("Save"):
                self.update_system_prompt(new_prompt)

                ## If we set it in the session state, it will be saved when a chat is shared
                ## and reloaded during rendering (though, at this time this doesn't really do anything)
                st.session_state['system_prompt'] = new_prompt
                st.success("System prompt updated.")

        edit_system_prompt()

    def edit_evaluator_system_prompt(self):
        # this is streamlit, see the documentation for @st.dialog()
        # calling this function renders a modal dialog, with the contents
        # of the function definding the contents of the modal
        @st.dialog(title = "Edit Evaluator System Prompt", width = "large")
        def edit_evaluator_system_prompt():
            """Edit the evaluator system prompt."""
            new_prompt = st.text_area("Evaluator System Prompt", value=self.evaluator_system_prompt, height=600, max_chars=20000)
            if st.button("Save"):
                self.evaluator_system_prompt = new_prompt

                ## If we set it in the session state, it will be saved when a chat is shared
                ## and reloaded during rendering (though, at this time this doesn't really do anything)
                st.session_state['evaluator_system_prompt'] = new_prompt
                st.success("Evaluator system prompt updated.")

        edit_evaluator_system_prompt()

    def edit_eval_query_template(self):
        # this is streamlit, see the documentation for @st.dialog()
        # calling this function renders a modal dialog, with the contents
        # of the function definding the contents of the modal
        @st.dialog(title = "Edit Evaluator Evaluation Prompt", width = "large")
        def edit_eval_query_template():
            """Edit the evaluator system prompt."""
            st.markdown("In the prompt, %QUERY% and %QUERY_RESULT% will be replaced with the query and result, respectively. %MESSAGES_HISTORY% will be replaced with the recent chat history (last 3 messages).")
            new_prompt = st.text_area("Evaluator Query Prompt Template", value=self.eval_query_template, height=600, max_chars=20000)
            if st.button("Save"):
                self.eval_query_template = new_prompt

                ## If we set it in the session state, it will be saved when a chat is shared
                ## and reloaded during rendering (though, at this time this doesn't really do anything)
                st.session_state['eval_query_template'] = new_prompt
                st.success("Evaluator system prompt updated.")


        edit_eval_query_template()

    def render_sidebar(self):
        super().render_sidebar()

        st.divider()

        st.button("Edit System Prompt", on_click=self.edit_system_prompt, disabled=st.session_state.lock_widgets, use_container_width=True)
        st.button("Edit Evaluator System Prompt", on_click=self.edit_evaluator_system_prompt, disabled=st.session_state.lock_widgets, use_container_width=True)
        st.button("Edit Evaluator Query Prompt Template", on_click=self.edit_eval_query_template, disabled=st.session_state.lock_widgets, use_container_width=True)

        # TODO: 1) add button for editing the eval prompt template
        # 2) put this info in the eval_chain for provenance, but deeply somewhere so it's out of the way
        # 4) add an "attempt number" for the eval loop
        # 3) clean up the eval chain a bit to make it more readable and limited expansion, using the attempt number


    # override the basic neo4j call to fix and munge the result for monarch biolink labels
    async def _call_neo4j(self, query, parameters = None, timeout = 6):
        query = fix_biolink_labels(query)
        res = await super()._call_neo4j(query, parameters = parameters, timeout = timeout)
        res['result_as_graph']['data'] = munge_monarch_graph_result(res['result_as_graph']['data'])
        return res


    def get_monarch_greeting(self):
        return """I'm the Phenomics Explorer, an experimental AI with knowledge of the Monarch Initiative's knowledge graph structure and contents. I can answer questions via complex graph queries. Some things you can ask:

- What phenotypes are associated with more than one subtype of EDS?
- What phenotypes are associated with Wilson disease or any of its subtypes, either directly or though connected genes?
- Which gene is directly or indirectly associated with the largest number of diseases?

**Please note that as an experimental work in progress I frequently make mistakes.** More information is available in my [implementation notes](https://github.com/monarch-initiative/phenomics-assistant/blob/new_backend/pe_notes.md).
""".strip()

    def _gen_monarch_instructions(self):
        return f"""
- Consider that the user may not be familiar with the graph structure or the specific terms used in the query.
- Provide non-specialist descriptions of biomedical results.
- Use the -[r:biolink_subclass_of*0..]-> pattern liberally to find all subclasses of a class.
- Use `LIMIT`, `ORDER BY` and `SKIP` clauses to manage the size of your results.
- Default to 10 results unless otherwise asked.
- Alert the user if there may be more results, and provide total count information when possible.
- Include links in the format `[Entity Name](https://monarchinitiative.org/entity_id)`.""".strip()



    # ALSO TODO: pull query eval out into a separate function for use in visualize_graph_query and run_query
    # TODO report more in the user-facing query evaluation, including the result and pass check result. Display the eval in the 
    #      chat before raising the exception (eventually the agent will give up). Might be nice to include a "query counter"
    #      so that if we see a series of evals they are distinguished. Showing multiple evals in the chat is a bit of a mess, 
    #      so even better would be to generate an eval datastructure and then show that at the end somewhere?


    # we also need to override display_report to fix the query
    def display_report(self, report):
        query = fix_biolink_labels(query)
        super().display_report(report)

    def get_node_styles(self):
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

        return node_styles


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