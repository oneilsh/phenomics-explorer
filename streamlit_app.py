# Example usage of StreamlitKani

########################
##### 0 - load libs
########################


# kani_streamlit imports
import kani_utils.kani_streamlit_server as ks
from kani_utils.base_engines import CostAwareEngine

# for reading API keys from .env file
import os
import dotenv # pip install python-dotenv

# kani imports
from kani.engines.openai import OpenAIEngine
#from kani.engines.anthropic import AnthropicEngine

from phenomics_explorer.agent_monarch import MonarchKGAgent
from phenomics_explorer.agent_evaluator import EvaluatorAgent
from phenomics_explorer.agent_kg_base import BaseKGAgent

########################
##### 1 - Configuration
########################

# read API keys .env file (e.g. set OPENAI_API_KEY=.... in .env and gitignore .env)
import dotenv
dotenv.load_dotenv(override=True)



# initialize the application and set some page settings
# parameters here are passed to streamlit.set_page_config, 
# see more at https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
# this function MUST be run first
ks.initialize_app_config(
    show_function_calls = False,
    show_function_calls_status = False,
    page_title = "Phenomics Assistant",
    page_icon = "🧬", # can also be a URL
    initial_sidebar_state = "collapsed", # "collapsed" or "expanded"
    menu_items = {
            "Get Help": "https://github.com/monarch-initiative/phenomics-assistant",
            "Report a Bug": "https://github.com/monarch-initiative/phenomics-assistant/issues",
            "About": "Phenomics Assistant is built on GPT-4, Streamlit, zhudotexe/kani, hourfu/redlines, and oneilsh/kani-utils.",
        },
    share_chat_ttl_seconds = 60 * 60 * 24 * 60, # 60 days
)


def get_agents():
    # 4.1 isn't yet supported by Kani, so we need to explicitly set the max context size otherwise we get the default of 8k tokens (4.1 can support up to 1M tokens technically)
    baseEngine = CostAwareEngine(OpenAIEngine(os.environ["OPENAI_API_KEY"], 
                                            model="gpt-4.1-2025-04-14", 
                                            temperature=0.0, 
                                            max_tokens=16000,
                                             max_context_size= 128000),
                               prompt_tokens_cost = 2, 
                               completion_tokens_cost = 8)
    evalEngine = CostAwareEngine(OpenAIEngine(os.environ["OPENAI_API_KEY"],
                                            model="gpt-4.1-2025-04-14", 
                                            temperature=0.0, 
                                            max_tokens=16000,
                                             max_context_size= 128000),
                               prompt_tokens_cost = 2, 
                               completion_tokens_cost = 8)
    
    eval_agent = EvaluatorAgent(engine = evalEngine)
    base_agent = BaseKGAgent(engine = baseEngine, eval_agent = eval_agent, retry_attempts = 3)
    
    return {
            "Phenomics Explorer (GPT 4.1)": base_agent,
            #"Phenomics Explorer (GPT 4.1, No Eval)": MonarchKGAgent(engine = engine41, eval_agent_engine = None, prompt_tokens_cost = 2, completion_tokens_cost = 8, retry_attempts = 3)
           }


# tell the app to use that function to create agents when needed
ks.set_app_agents(get_agents)


########################
##### 3 - Serve App
########################

ks.serve_app()
