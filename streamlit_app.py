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

from agent_monarch import *

########################
##### 1 - Configuration
########################

# read API keys .env file (e.g. set OPENAI_API_KEY=.... in .env and gitignore .env)
import dotenv
dotenv.load_dotenv() 



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

# define an engine to use (see Kani documentation for more info)
base_engine = CostAwareEngine(OpenAIEngine(os.environ["OPENAI_API_KEY"], 
                                           model="gpt-4.1-2025-04-14", 
                                           temperature=0.0, 
                                           max_tokens=10000), 
                              prompt_tokens_cost = 2, 
                              completion_tokens_cost = 8)


#engine = AnthropicEngine(model="claude-3-5-haiku-latest")

# We also have to define a function that returns a dictionary of agents to serve
# Agents are keyed by their name, which is what the user will see in the UI
def get_agents():
    base_agent = MonarchKGAgent(engine = base_engine, retry_attempts = 3)
    return {
            "Phenomics Explorer (GPT 4.1)": base_agent
            #"Phenomics Explorer (Experimental, Haiku)": MonarchKGAgent(engine, prompt_tokens_cost = 0.008, completion_tokens_cost = 0.4, retry_attempts = 3)
           }


# tell the app to use that function to create agents when needed
ks.set_app_agents(get_agents)


########################
##### 3 - Serve App
########################

ks.serve_app()
