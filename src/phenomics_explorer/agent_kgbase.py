from typing_extensions import Annotated
from kani import AIParam, ai_function, ChatRole, ChatMessage
from kani_utils.base_kanis import StreamlitKani
import streamlit as st
from kani.exceptions import WrappedCallException
import asyncio
from phenomics_explorer.neo4j_utils import _parse_neo4j_result
from phenomics_explorer.monarch_utils import fix_biolink_labels
import yaml
from phenomics_explorer.neo4j_utils import summarize_structure
import json
from neo4j import AsyncGraphDatabase
import os

class BaseKGAgent(StreamlitKani):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, 
                 *args,
                 eval_agent = None,
                 max_response_tokens = 30000,
                 **kwargs):

        kwargs['system_prompt'] = kwargs.get(
            'system_prompt',
            'You are an expert-level Neo4j analyst, designed to query a knowledge graph with cypher and interpret the result.'
        )

        self.eval_chain = []  # this is a list of evaluation reports, which we will display after each user message

        # if interactive is not set, we set it to True by default
        if 'interactive' not in kwargs:
            self.interactive = True
        else:
            self.interactive = kwargs['interactive']
            del kwargs['interactive']
        
        self.eval_agent = eval_agent
        self.max_response_tokens = max_response_tokens

        self.neo4j_uri = os.environ["NEO4J_URI"]  # default bolt protocol port
        self.neo4j_driver = AsyncGraphDatabase.driver(self.neo4j_uri)

        super().__init__(*args, **kwargs)
        

    #######################
    #### Status display
    #######################

    def _status(self, label):
        if self.interactive:
            if not hasattr(self, 'status'):
                self.status = st.status(label = label)
            else:
                self.status.update(label = label)

    def _clear_status(self):
        if self.interactive:
            if hasattr(self, 'status'):
                del self.status

    
    def _display_report(self, report):
        if self.interactive:
            def render_query_eval():
                with st.expander("Query Evaluation"):
                    st.json(report)
            
            self.render_in_streamlit_chat(render_query_eval)

    # we override this so that we can clear the status box after each user-entered message;
    # this also clears the eval chain; if we're not running interactively, we don't clear this out for later evaluation
    async def add_to_history(self, message, *args, **kwargs):
        if self.interactive:
            if message.role == ChatRole.USER:
                self._clear_status()

            # I see; the add_to_history is called for every assistant message, and there may be multiple in a single full round
            # the one we want is the one that has no tool call; 
            if message.role == ChatRole.ASSISTANT:
                if message.tool_calls is None or len(message.tool_calls) == 0:
                    # we also render the report and reset the eval_chain
                    if len(self.eval_chain) > 0:
                        self._display_report(self.eval_chain)
                        self.eval_chain = []

        await super().add_to_history(message, *args, **kwargs)



    ##############################
    ###### Sidebar components
    ##############################

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
            new_prompt = st.text_area("Evaluator System Prompt", value=self.eval_agent.system_prompt, height=600, max_chars=20000)
            if st.button("Save"):
                self.eval_agent.update_system_prompt(new_prompt)

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
            new_prompt = st.text_area("Evaluator Query Prompt Template", value=self.eval_agent.eval_message_template, height=600, max_chars=20000)
            if st.button("Save"):
                self.eval_agent.eval_query_template = new_prompt

                ## If we set it in the session state, it will be saved when a chat is shared
                ## and reloaded during rendering (though, at this time this doesn't really do anything)
                st.session_state['eval_query_template'] = new_prompt
                st.success("Evaluator system prompt updated.")


        edit_eval_query_template()

    def render_sidebar(self):
        super().render_sidebar()

        st.divider()

        st.button("Edit System Prompt", on_click=self.edit_system_prompt, disabled=st.session_state.lock_widgets, use_container_width=True)
        
        if self.eval_agent is not None:
            st.button("Edit Evaluator System Prompt", on_click=self.edit_evaluator_system_prompt, disabled=st.session_state.lock_widgets, use_container_width=True)
            st.button("Edit Evaluator Query Prompt Template", on_click=self.edit_eval_query_template, disabled=st.session_state.lock_widgets, use_container_width=True)



    #######################
    #### Query execution
    #######################

    # this sync/async stuff to get the timeout working, along with the return type from neo4j is some dark magic stuff
    async def _call_neo4j(self, query, parameters = None, timeout = 6):
        self._status("Running query...")

        async def internal_run_query():
            async with self.neo4j_driver.session() as session:
                # apparently both of these need to be awaited?
                raw_result1 = await session.run(query, parameters = parameters)
                result_graph = await _parse_neo4j_result(raw_result1, expected_type = "graph")
                # if there aren't any nodes, we need to compute the table result
                if len(result_graph['data']['nodes']) == 0:
                    raw_result2 = await session.run(query)
                    result_table = await _parse_neo4j_result(raw_result2, expected_type = "table")
                # if there *are* nodes, the table view should be empty
                else:
                    result_table = {"type": "table", "data": []}

            return {"result_as_graph": result_graph, "result_as_table": result_table}
        
        try:
            result_dict = await asyncio.wait_for(internal_run_query(), timeout=timeout)
        except asyncio.TimeoutError:
            self._status("Query timed out.")
            report = {
                "query": fix_biolink_labels(query),
                "accept_query": False,
                "suggestion": f"The query took longer than the alloted time of f{timeout} seconds and was terminated."
                }
             
            self.eval_chain.append(report)
            raise WrappedCallException(retry = True, original = ValueError("The query timed out. Try again, reducing query computation."))

        return result_dict
    
    @ai_function(after = ChatRole.ASSISTANT)
    async def run_query(self, 
                        query: Annotated[str, AIParam(desc="""Cypher query to evaluate.""")],
                        parameters: Annotated[dict, AIParam(desc="""Parameters to pass to the cypher query. This should be a dictionary of key-value pairs, where the keys are the parameter names and the values are the parameter values.""")] = None):
        """Run a given cypher query against the knowledge graph and return the results. Think step-by-step when calling this function to ensure the query addresses the user question with the appropriate type of query, which may need to return either tabular or graph (nodes, edges, or paths) data."""

        self._status("Running query...")
        display_query = fix_biolink_labels(query)
        try:
            neo4j_result = await self._call_neo4j(query, parameters = parameters)
        except Exception as e:
            self._status("Query failed.")
            report = {
                "query": display_query,
                "accept_query": False,
                "suggestion": "The query generated an error:\n\n"  + str(e)
                }
            self.eval_chain.append(report)
            raise WrappedCallException(retry = True, original = e)

        if self.eval_agent is not None:
            self._status("Evaluating query and result...")
            result_summary = summarize_structure(neo4j_result)
            eval_result = self.eval_agent.evaluate_query(query, result_summary, self.chat_history)

            report = {
                "query": display_query,
                **eval_result
            }
            self.eval_chain.append(report)

            if not eval_result['accept_query']:
                self._status("Query did not pass evaluation.")
                raise WrappedCallException(retry = True, original = ValueError("The query did not pass evaluation; please review the suggestions and try again. Evaluation:\n\n" + yaml.dump(eval_result)))

        tokens = self.message_token_len(ChatMessage.user(json.dumps(neo4j_result)))
        if tokens > self.max_response_tokens:
            error_message = f"The search result contained {tokens} tokens, greater than the maximum allowable of {self.max_response_tokens}. Please try a smaller search."
            report = {
                "query": display_query,
                "accept_query": False,
                "suggestion": error_message
                }
            self.eval_chain.append(report)
            raise WrappedCallException(retry = True, original = ValueError(error_message))
        else:
            self._status("Generating Answer...")
            return neo4j_result    
