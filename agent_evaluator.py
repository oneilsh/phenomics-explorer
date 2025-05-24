from typing_extensions import Annotated
from typing import Optional
from kani import AIParam, ai_function, ChatMessage, ChatRole
from monarch_utils import graph_summary, example_queries_str
import json
import yaml
from kani_utils.base_kanis import StreamlitKani

class MonarchEvaluatorAgent(StreamlitKani):
    """Agent for interacting with the Monarch knowledge graph; extends KGAgent with keyword search (using Monarch API) system prompt with cypher examples."""
    def __init__(self, *args, engine = None, max_response_tokens = 10000, **kwargs):
        super().__init__(engine = engine, *args, **kwargs)



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
    
 
    async def evaluate_query(self, template: Annotated[str, AIParam(desc="The template to use to build the query.")],
                                   query: Annotated[str, AIParam(desc="The cypher query to evaluate.")], 
                                   result_dict: Annotated[dict, AIParam(desc="The result of the cypher query, in dictionary format.")], 
                                   context_history: Optional[Annotated[list[ChatMessage], AIParam(desc="The chat history, which is a list of ChatMessage objects. This is used to provide context for the evaluation.")]] = None,
                                   instructions: Optional[Annotated[str, AIParam(desc="Instructions given to the main agent. This is used to provide context for the evaluation.")]] = None):
        """Evaluate a query result using the evaluator agent. This can be called externally (it is not available for the agent to call), which will trigger this agent to evaluate """

        prompt = self.get_eval_query_prompt(template, query, result_dict, context_history, instructions)

        # print("\n\n\n\n\n\n&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        # print("MonarchEvaluatorAgent: prompt")
        # print(prompt)

        async def collect_async_generator(async_gen):
            messages = []
            async for message in async_gen:
                messages.append(message.content)
            return messages
        
        eval_chat_log = await collect_async_generator(self.full_round(prompt))
        # print("EVAL CHAT LOG")
        # print(eval_chat_log)

        # if eval_chat_log has 2 or more elements, the eval agent called a tool and the second element is the result
        if len(eval_chat_log) > 1:
            result = json.loads(eval_chat_log[1])
        else:
            # if it didn't call a tool, the result is in the first element
            result = {"accept_query": False, "evaluator_message": eval_chat_log[0]}
        # print("EVAL RESULT")
        # import pprint
        # pprint.pprint(result)

        return result
    

    def get_eval_query_prompt(self, template, query, result_dict, messages_history, instructions):
        """Generate a prompt for evaluating a query result."""

        # messages_history is a list of ChatMessage objects, which have role and content attributes'
        messages_history = [f"{m.role}: {m.content}" for m in messages_history]

        res = (template.replace("%QUERY%", query)
               .replace("%QUERY_RESULT%", json.dumps(result_dict, indent=2))
               .replace("%MESSAGES_HISTORY%", "\n".join(messages_history))
               .replace("%INSTRUCTIONS%", instructions)
               )
        # print("EVAL QUERY")
        # print(res)
        return res
    
# What phenotypes are associated with more than one subtype of EDS?

# How many subtypes are associated with both blue sclerae and scoliosis?

# And how many genes are connected to more than one of those subtypes?

# I see. Presumably there are genes associated with individual subtypes? How many are there, and can we visualize this network of the two phenotypes, connected subtypes, and connected genes?

# That is just lovely. Thank you!


