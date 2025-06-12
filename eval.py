# kani_streamlit imports
import kani_utils.kani_streamlit_server as ks
from kani_utils.utils import full_round_sync

# for reading API keys from .env file
import os
import dotenv # pip install python-dotenv

# kani imports
from kani.engines.openai import OpenAIEngine
#from kani.engines.anthropic import AnthropicEngine

from phenomics_explorer.agent_monarch import MonarchKGAgent

########################
##### 1 - Configuration
########################

# read API keys .env file (e.g. set OPENAI_API_KEY=.... in .env and gitignore .env)
import dotenv
dotenv.load_dotenv() 


engine = OpenAIEngine(os.environ["OPENAI_API_KEY"], model="gpt-4.1-2025-04-14", temperature=0.0, max_tokens=10000)

agent = MonarchKGAgent(engine, prompt_tokens_cost = 2, completion_tokens_cost = 8, retry_attempts = 3, interactive = False)

res = full_round_sync(agent, "What is the relationship between the gene BRCA1 and breast cancer?")
print("Response from MonarchKGAgent:")
for message in res:
    print(message)

print("\nEvaluations from MonarchKGAgent:")
for eval in agent.eval_chain:
    print(eval)

print("\nCosts:")
print(f"Prompt tokens used: {agent.tokens_used_prompt}")
print(f"Completion tokens used: {agent.tokens_used_completion}")
print(f"Total cost: ${agent.get_convo_cost():.4f}")