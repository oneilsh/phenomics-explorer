from typing_extensions import Annotated
from typing import Optional
from kani import AIParam, ai_function, ChatMessage, ChatRole
from phenomics_explorer.utils import messages_dump
import json
from kani_utils.base_kanis import StreamlitKani
from kani_utils.utils import full_round_sync
from phenomics_explorer.agent_kgbase_evaluator import EvaluatorAgent
import phenomics_explorer.monarch_constants as C

class MonarchEvaluatorAgent(EvaluatorAgent):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.update_system_prompt(C.monarch_evaluator_system_prompt)



    @ai_function(after = ChatRole.USER)
    def report_evaluation(self, 
                          query_summary: Annotated[str, AIParam(desc="A summary of how the query works, allowing a non-technical user to understand the cypher syntax. Also describe how the query relates to the user question, thinking step-by-step.")],
                          accept_query: Annotated[bool, AIParam(desc="Set to True if the query and results are acceptable according to the summary information, False otherwise.")],
                          suggestion: Annotated[str, AIParam(desc="Suggestions for improving the query, if any.")]
                          ):
        """Report on the evaluation of a query. If accept_query is True, the query result will be reported back to the user. If False, the query will be rejected and a suggestion will be provided. The query_summary should be a non-technical summary of the query, allowing a non-technical user to understand the cypher syntax."""

        # if it passes, we clear out the suggestion so that the model doesn't get confused
        # EDIT: this may not be necessary any more - needs testing
        # if accept_query:
        #    suggestion = "None."

        # we return json string here and reparse it later, rather than trying to fit a dictionary
        # in the resulting ChatMessage.content
        return json.dumps({"query_summary": query_summary,
                "accept_query": accept_query,
                "suggestion": suggestion
                })
    
 
    def evaluate_query(self,
                       query: Annotated[str, AIParam(desc="The cypher query to evaluate.")], 
                       result_dict: Annotated[dict, AIParam(desc="The result of the cypher query, in dictionary format.")], 
                       context_history: Optional[Annotated[list[ChatMessage], AIParam(desc="The chat history, which is a list of ChatMessage objects. This is used to provide context for the evaluation.")]] = None):
        """Evaluate a query in the context of its result and the context history (the agent's .history) using the evaluator agent. This can be called externally (it is not available for the agent to call), which will trigger this agent to evaluate """

        prompt = self.get_eval_query_prompt(query, result_dict, context_history)

        # this method is called externally but belongs to to the agent, which chats with itself
        # to trigger running report_evaluation() with structured input enforced; the last
        # message will be the result of the function call for extraction
        # (this is how pydandic.ai implements structured tool output interally: https://ai.pydantic.dev/output/#tool-output)
        eval_chat_log = full_round_sync(self, prompt)
        eval_chat_log = [m.content for m in eval_chat_log]

        # if eval_chat_log has 2 or more elements, the eval agent called a tool and the second element is the result
        if len(eval_chat_log) > 1:
            result = json.loads(eval_chat_log[1])
        else:
            # if it didn't call a tool, the result is in the first element
            result = {"accept_query": False, "evaluator_message": eval_chat_log[0]}

        return result
    

    def get_eval_query_prompt(self, query, result_dict, messages_history):
        """Generate a prompt for evaluating a query result."""
        # we use the same evaluation message template as the base EvaluatorAgent class, doesn't need customizing
        template = self.eval_message_template

        cleaned_history = []
        for m in messages_history:
            # truncate function results to 1000 characters; providing the entirety of all function results is too much.
            if m.role == ChatRole.FUNCTION and len(m.content) > 4000: # ~ 1000 tokens
                m.content = m.content[:2000] + " ... [result trimmed] ..." + m.content[-2000:]  # keep the first and last 2000 characters
            
            cleaned_history.append(m)

        cleaned_history_strings = [json.dumps(messages_dump(m)) for m in cleaned_history]
        cleaned_history_strings = cleaned_history_strings[-10:]  # only keep the last 10 messages for context

        res = (template.replace("%QUERY%", query)
               .replace("%QUERY_RESULT%", json.dumps(result_dict, indent=2))
               .replace("%MESSAGES_HISTORY%", "\n".join(cleaned_history_strings))
               )

        return res
    
