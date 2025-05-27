from typing_extensions import Annotated
from kani import AIParam, ai_function, ChatRole, ChatMessage
from kani_utils.base_kanis import StreamlitKani
import random
import streamlit as st
from st_link_analysis import EdgeStyle, st_link_analysis
from kani.exceptions import WrappedCallException
import asyncio
from neo4j_utils import _parse_neo4j_result
from agent_evaluator import MonarchEvaluatorAgent
import yaml
from neo4j_utils import summarize_structure
import json


class BaseKGAgent(StreamlitKani):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, 
                 *args,
                 **kwargs):

        kwargs['system_prompt'] = kwargs.get(
            'system_prompt',
            'You are an expert-level Neo4j analyst, designed to query a knowledge graph with cypher and interpret the result.'
        )

        super().__init__(*args, **kwargs)
        self.eval_chain = []

        self.eval_query_template = """\
Please evaluate the following cypher query in the context of the conversation and query result:

Conversation context:
```
- ...
%MESSAGES_HISTORY%
```
      
Query:
```
%QUERY%
```

Result (possibly truncated):
```
%QUERY_RESULT%
```

Instructions given to the agent:
```
%INSTRUCTIONS%
```

Report your answer using your report_evaluation() function, considering the following:
- Whether the result aligns with expectations based on the query.
- Whether an ORDER BY clause should be applied.
- Whether relationships are oriented correctly in the query.
- Whether the query should allow for OPTIONAL matches.
- Whether the query passes a 'sanity check' if the results are not as expected.

Think step-by-step.
"""

    #######################
    #### Status display
    #######################
    #     

    def _status(self, label):
        if not hasattr(self, 'status'):
            self.status = st.status(label = label)
        else:
            self.status.update(label = label)

    def _clear_status(self):
        if hasattr(self, 'status'):
            del self.status

    
    def _display_report(self, report):
        def render_query_eval():
            with st.expander("Query Evaluation"):
                st.json(report)
        
        self.render_in_streamlit_chat(render_query_eval)

    # we override this so that we can clear the status box after each user-entered message;
    async def add_to_history(self, message, *args, **kwargs):
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
                "query": query,
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

        # print("\n\n\n\n\n\n\n\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        # print("ABOUT TO RUN QUERY:")
        # print(query)
        # print("\n\nSYSTEM PROMPT:")
        # print(self.system_prompt)

        self._status("Running query...")
        try:
            neo4j_result = await self._call_neo4j(query, parameters = parameters)
        except Exception as e:
            self._status("Query failed.")
            report = {
                "query": query,
                "accept_query": False,
                "suggestion": "The query generated an error:\n\n"  + str(e)
                }
            self.eval_chain.append(report)
            raise WrappedCallException(retry = True, original = e)

        context_history = [message for message in self.chat_history if message.role == ChatRole.USER or message.role == ChatRole.ASSISTANT][-3:]

        eval_agent = MonarchEvaluatorAgent(engine = self.engine)
        eval_agent.update_system_prompt(self.evaluator_system_prompt)

        self._status("Evaluating query and result...")
        result_summary = summarize_structure(neo4j_result)
        eval_result = await eval_agent.evaluate_query(self.eval_query_template, query, result_summary, context_history, self._gen_monarch_instructions())

        # need to add the evaluator's token usage to ours
        self.tokens_used_prompt += eval_agent.tokens_used_prompt
        self.tokens_used_completion += eval_agent.tokens_used_completion

        report = {
            "query": query,
            **eval_result
        }
        self.eval_chain.append(report)

        if not eval_result['accept_query']:
            self._status("Query did not pass evaluation.")
            raise WrappedCallException(retry = True, original = ValueError("The query did not pass evaluation; please review the suggestions and try again. Evaluation:\n\n" + yaml.dump(eval_result)))

        self._status("Generating Answer...")

        tokens = self.message_token_len(ChatMessage.user(json.dumps(neo4j_result)))
        if tokens > self.max_response_tokens:
            raise WrappedCallException(retry = True, original = ValueError(f"The search result contained {tokens} tokens, greater than the maximum allowable of {self.max_response_tokens}. Please try a smaller search."))
        else:
            return neo4j_result    
