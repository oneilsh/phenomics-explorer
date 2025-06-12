# kani_streamlit imports
import kani_utils.kani_streamlit_server as ks
from kani_utils.utils import full_round_sync

# for reading API keys from .env file
import os
import dotenv # pip install python-dotenv
import json
import glob
import isodate

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


engine41 = OpenAIEngine(os.environ["OPENAI_API_KEY"], model="gpt-4.1-2025-04-14", temperature=0.0, max_tokens=10000)
engine4o = OpenAIEngine(os.environ["OPENAI_API_KEY"], model="gpt-4o-2024-11-20", temperature=0.0, max_tokens=10000)


base_engines = ["gpt-4.1-2025-04-14", "gpt-4o-2024-11-20"]
eval_engines = ["gpt-4.1-2025-04-14", "None"]
prompt_templates = {
    "basic_prompt": """From the following patient information, what is the most likely diagnosis? Use multiple queries or reasoning steps as necessary, and provide a rank-ordered list of up to 10 diagnoses.

Patient age: <age>
Patient sex: <sex>
Patient features: <include_features>
Excluded patient features: <exclude_features>"""
}
#pheno_formats = {"pheno_labels_and_ids": "<label> (<id>)", "pheno_labels_only": "<label>"}
pheno_formats = {"pheno_labels_only": "<label>"}


total_experiments = len(base_engines) * len(eval_engines) * len(prompt_templates) * len(pheno_formats) * len(glob.glob("phenopackets/*.json"))

phenopackets_dir = "phenopackets"
phenopackets_files = glob.glob(os.path.join(phenopackets_dir, "*.json"))

import enum 

def recursive_model_dump(obj):
    """Recursively convert objects to a JSON-serializable format."""
    if isinstance(obj, dict):
        return {k: recursive_model_dump(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_model_dump(item) for item in obj]
    elif hasattr(obj, 'model_dump'):
        return recursive_model_dump(obj.model_dump())
    # if it's an enum...
    elif isinstance(obj, enum.Enum):
        return recursive_model_dump(obj.value)
    else:
        return obj

for phenopacket_file in phenopackets_files:
    with open(phenopacket_file, "r") as f:
        phenopacket = json.load(f)
    
    for base_engine_str in base_engines:
        for eval_engine_str in eval_engines:
            if eval_engine_str == "None":
                eval_engine = None
            else:
                eval_engine = OpenAIEngine(os.environ["OPENAI_API_KEY"], model=eval_engine_str, temperature=0.0, max_tokens=10000)
            
            engine = OpenAIEngine(os.environ["OPENAI_API_KEY"], model=base_engine_str, temperature=0.0, max_tokens=10000)

            age_human_readable = "Unknown"
            if "subject" in phenopacket and "timeAtLastEncounter" in phenopacket["subject"] and "age" in phenopacket["subject"]["timeAtLastEncounter"]:
                if "iso8601duration" in phenopacket["subject"]["timeAtLastEncounter"]["age"]:
                    age = phenopacket["subject"]["timeAtLastEncounter"]["age"]["iso8601duration"]

                    duration = isodate.parse_duration(age)
                    years = duration.years
                    months = duration.months
                    if years > 0:
                        age_human_readable = f"{years} year{'s' if years > 1 else ''}"
                    if months > 0:
                        if years > 0:
                            age_human_readable += f", {months} month{'s' if months > 1 else ''}"
                    if years == 0 and months == 0:
                        age_human_readable = "newborn"

            
            sex_human_readable = "Unknown"
            if "subject" in phenopacket and "sex" in phenopacket["subject"]:
                sex = phenopacket["subject"]["sex"]
                sex_human_readable = sex.capitalize()
                

            include_features = {feature["type"]["id"]: feature["type"]["label"] for feature in phenopacket["phenotypicFeatures"] if "excluded" not in feature or not feature["excluded"]}
            exclude_features = {feature["type"]["id"]: feature["type"]["label"] for feature in phenopacket["phenotypicFeatures"] if "excluded" in feature and feature["excluded"]}

            if len(include_features) == 0:
                include_features = {"None": "None"}
            if len(exclude_features) == 0:
                exclude_features = {"None": "None"}

            diagnosis = phenopacket["interpretations"][0]["diagnosis"]["disease"]["id"] if len(phenopacket["interpretations"]) > 0 else None

            for prompt_template in prompt_templates:
                for label_format in pheno_formats:
                    include_features_str = ", ".join([pheno_formats[label_format].replace("<label>", label).replace("<id>", id) for id, label in include_features.items()]) + "."
                    exclude_features_str = ", ".join([pheno_formats[label_format].replace("<label>", label).replace("<id>", id) for id, label in exclude_features.items()]) + "."
                
                    prompt = prompt_templates[prompt_template].replace("<age>", age_human_readable)
                    prompt = prompt.replace("<sex>", sex_human_readable)
                    prompt = prompt.replace("<include_features>", include_features_str)
                    prompt = prompt.replace("<exclude_features>", exclude_features_str)

                    output_file = f"results/diagnoses/{os.path.basename(phenopacket_file)}/{base_engine_str}/{eval_engine_str if eval_engine else 'None'}/{prompt_template}/{label_format}.json"

                    # check if the output file already exists
                    if os.path.exists(output_file):
                        print(f"Skipping {output_file} as it already exists.")
                        continue

                    agent = MonarchKGAgent(engine = engine, eval_agent_engine = eval_engine, prompt_tokens_cost = 2, completion_tokens_cost = 8, retry_attempts = 3, interactive = False)

                    print(f"Running, base: {base_engine_str}, eval: {eval_engine_str}, prompt: {prompt_template}, format: {label_format}, input: {phenopacket_file}")
                    result_messages = full_round_sync(agent, prompt)
                    result_messages_as_json = [recursive_model_dump(message) for message in result_messages]

                    result_eval_chain = agent.eval_chain
                    result_cost = agent.get_convo_cost()
                    result_tokens_used_prompt = agent.tokens_used_prompt
                    result_tokens_used_completion = agent.tokens_used_completion
                    result_dict = {
                        "messages": result_messages_as_json,
                        "eval_chain": result_eval_chain,
                        "cost_est_base_rate": result_cost,
                        "tokens_used_prompt": result_tokens_used_prompt,
                        "tokens_used_completion": result_tokens_used_completion,
                        "query": prompt,
                        "phenopacket_file": phenopacket_file,
                        "expected_diagnosis": diagnosis
                    }

                    # make sure the directory exists
                    output_dir = os.path.dirname(output_file)
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    # save the result to a file
                    with open(output_file, "w") as f:
                        json.dump(result_dict, f, indent=4)

                    percent_complete = (len(glob.glob("results/*/*.json")) / total_experiments) * 100
                    print(f"Completed {output_file}. ~Cost: {result_cost} File {len(glob.glob('results/*/*.json'))} of {total_experiments} ({percent_complete:.2f}%) complete.")         
