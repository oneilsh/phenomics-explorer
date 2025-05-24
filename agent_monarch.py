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
        self.name = "Phenomics Explorer"

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
    def get_tour_instructions(self):
        """Get the instructions for showing the user a tour of the app."""

        instructions = """


Tour Part 1: Graph Overview

First, explain to the user that you provide an interface to the Monarch knowledge graph, 
a large biomedical database that contains information about genes, diseases, phenotypes, 
and other biological entities, and relationships between them. Describe what is meant by
graph, nodes, and edges, in case they are not familiar. Ask them if have any questions.

After you have completed an intial overview of the graph, display a visualization for
the query `MATCH (g:biolink_Gene {id: "HGNC:1884"}) -[r:biolink_causes]-> (n:biolink_Disease {id: "MONDO:0009061"}) RETURN g, r, n`. 
After the graph has been displayed, ask the user to click on the nodes and edges, and 
describe the information in the nodes in particular. 

[ASIDE: while you format queries with labels like "biolink_Gene",  the actual labels 
in the graph are of the form `biolink:Gene`, and this is what the user sees.]

Next, address their observations. Explain that the `id` property is a unique identifier 
for the node, and `category` is a label that describes the type of entity it represents.
The IDs will be of the form `HGNC:1884` or `MONDO:0009061`, and the categories will be of 
the form `biolink:Gene` or `biolink:Disease`. Explain what the `biolink` prefix means, 
and the `HGNC` and `MONDO` prefixes mean. Link to https://biolink.github.io/biolink-model/ 
and https://monarch-initiative.github.io/monarch-ingest/Sources/ in this explanation 
as references. 

Follow this line of questioning by asking the user to click on the edge and review its 
properties, reporting what they see.

After recognizing their answer, explain the `biolink:causes` edge, noting again the use 
of the biolink data model, and that `predicate` describes the type of the edge. Mention 
that nodes of different categories and edges of different predicates have different sets 
of other properties, such as, name, description, and so on. As the user if they
have any further questions about the graph before moving on to part 2 of the tour.

Tour Part 2: Hierarchical Relationships

The next part of the tour covers the concept of hierarchical relationships in the graph. 
Begin by describing ontologies, and how they are used to represent knowledge in a structured 
way, particularly "subtype" or "subclass" relationships. Follow this up by visualizing
the query `MATCH path = (n:biolink_Disease {id: "MONDO:0001982"})  <-[:biolink_subclass_of*]- (s:biolink_Disease) RETURN path`.

Ask the user to try making the view fullscreen, zooming, and dragging the nodes around 
to see the hierarchy more clearly. Ask them to let you know whey they are ready to move on.

After they've had a chance to explore the graph, explain how the Monarch KG is composed 
of entities from a variety of different ontologies, with relationships like `biolink_causes` 
connecting them together into a vast web of knowledge. Follow this by running this query, 
to demonstrate the various categories that are available: `CALL db.labels() YIELD label RETURN label`. 
Format the results in a table with 3 columns to save space, and organize them according 
to theme.

Ask them if they'd like to see all of the different relationships in the graph, and if 
so, visualize the query `CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType`.
Again format the result in a multi-column table, organized by theme. Ask them if they'd 
like to see the properties of a specific relationship or entity, and if so, run the query, 
otherwise, continue on to part 3 of the tour.

Tour Part 3: Searching the Graph

In this part of the tour you flex you querying muscles, demonstrating the kinds of
multi-step, sophisticated queries you can perform. Start by describing that you are 
going to investigate phenotypes associated with the subtyptes of Niemmann-Pick disease, 
and genes that associated with those phenotypes. Since there may be many such phenotypes 
and genes, explain that you'll start by looking at the top 10 phenotypes, ordered by 
the number of subtypes they are associated with. Run this search and query, and display 
the results in a table. Let the user know that when they are done reviewing the results, 
they can ask you to continue.

Explain to the user that now you'll look for genes associated with these top 10 phenotypes, 
as well as any genes that are directly connected to any of the Niemann-Pick disease 
subtypes. In order to keep the result small, you'll pick the top 10, ordered by the 
number of subtypes and/or phenotypes they are associated with. Run this query, and 
display the results in a table, with columns for the Gene Name, Number of connected 
Phenotypes, and Number of connected Subtypes. Remember that you don't need to limit
the number of intermediary phenotypes in this version of the query, just the number 
of genes.

INSTRUCTIONS:

 - Walk through the tour step-by-step, letting the user discover gradually
 - Use markdown section headers to separate the parts of the tour
 - Be concise, yet informative
""".strip()
        
        return instructions

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

    def sidebar(self):
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
        return \
"""
I'm the Phenomics Explorer, an AI with knowledge of the Monarch Initiative knowledge 
graph. I can answer questions via complex graph queries. Some things you can ask:

- What genes are associated with Wilson disease? 
- How many phenotypes (traits or symptoms) are associated with the gene that causes CF?
- What kinds of entities do you know about?
- How kinds of relationships do you know about?

But if you really want to get to know me and the graph, I suggest you request the tour! 🌎

*Please note that as an experimental work in progress may make mistakes. An overview of my operation is available in my [implementation notes](https://github.com/monarch-initiative/phenomics-assistant/blob/phenomics_assistant2/pe_notes.md).*
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