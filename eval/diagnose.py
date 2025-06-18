# for reading API keys from .env file
import os
import dotenv # pip install python-dotenv
import json
import glob
import isodate
from neo4j import GraphDatabase

# kani imports
from kani.engines.openai import OpenAIEngine

# read API keys .env file (e.g. set OPENAI_API_KEY=.... in .env and gitignore .env)
import dotenv
dotenv.load_dotenv() 

from kani_utils.utils import full_round_sync
from phenomics_explorer.agent_monarch import MonarchKGAgent
from phenomics_explorer.utils import messages_dump


neo4j_driver = GraphDatabase.driver(os.environ["NEO4J_URI"])


def iso8601_duration_to_human_readable(age):
    """Convert an ISO 8601 duration to a human-readable format."""
    duration = isodate.parse_duration(age, as_timedelta_if_possible = False)
    years = duration.years
    months = duration.months
    age_human_readable = age
    if years > 0:
        age_human_readable = f"{years} year{'s' if years > 1 else ''}"
    if months > 0:
        if years > 0:
            age_human_readable += f", {months} month{'s' if months > 1 else ''}"
    if years == 0 and months > 0:
        age_human_readable = f"{months} month{'s' if months > 1 else ''}"

    if years == 0 and months == 0:
        age_human_readable = "newborn"

    return age_human_readable

def phenopacket_to_prompt(phenopacket, include_ids = False):
    """Convert a phenopacket to a prompt string."""
    age_human_readable = "Unknown"
    if "subject" in phenopacket and "timeAtLastEncounter" in phenopacket["subject"] and "age" in phenopacket["subject"]["timeAtLastEncounter"]:
        if "iso8601duration" in phenopacket["subject"]["timeAtLastEncounter"]["age"]:
            age = phenopacket["subject"]["timeAtLastEncounter"]["age"]["iso8601duration"]
            age_human_readable = iso8601_duration_to_human_readable(age)

    sex_human_readable = "Unknown"
    if "subject" in phenopacket and "sex" in phenopacket["subject"]:
        sex = phenopacket["subject"]["sex"]
        sex_human_readable = sex.capitalize()

    subject_id = phenopacket.get("subject", {}).get("id", "Unknown")

    include_features = []
    exclude_features = []
    for feature in phenopacket["phenotypicFeatures"]:
        if "onset" in feature and "age" in feature["onset"] and "iso8601duration" in feature["onset"]["age"]:
            onset_age = "onset " + iso8601_duration_to_human_readable(feature["onset"]["age"]["iso8601duration"])
        elif "onset" in feature and "ontologyClass" in feature["onset"]:
            onset_age = feature["onset"]["ontologyClass"]["label"]
        else:
            onset_age = ""

        if "excluded" not in feature or not feature["excluded"]:
            if include_ids:
                if onset_age != "":
                    include_features.append(f"{feature['type']['label']} ({feature['type']['id']}, {onset_age})")
                else:
                    include_features.append(f"{feature['type']['label']} ({feature['type']['id']})")
            else:
                if onset_age != "":
                    include_features.append(f"{feature['type']['label']} ({onset_age})")
                else:
                    include_features.append(feature['type']['label'])
        else:
            if include_ids:
                exclude_features.append(f"{feature['type']['label']} ({feature['type']['id']})")
            else:
                exclude_features.append(feature['type']['label'])


    if len(include_features) == 0:
        include_features = ["None"]
    if len(exclude_features) == 0:
        exclude_features = ["None"]
    include_features_str = ", ".join(include_features) + "."
    exclude_features_str = ", ".join(exclude_features) + "."
    prompt = f"""
From the following patient information, what is the most likely diagnosis? Use multiple queries or reasoning steps as necessary, and provide a rank-ordered list of up to 10 diagnoses, even if there is insufficient information to make a definitive diagnosis. If you are unsure, provide a list of possible diagnoses with the most likely one first.

Patient ID: {subject_id}
Patient age: {age_human_readable}
Patient sex: {sex_human_readable}
Patient features: {include_features_str}
Excluded patient features: {exclude_features_str}
"""
    return prompt.strip()


base_engines = ["gpt-4.1-2025-04-14", "gpt-4o-2024-11-20"]
eval_engines = ["gpt-4.1-2025-04-14", "None"]

total_experiments = len(base_engines) * len(eval_engines) * len(glob.glob("phenopackets/*.json"))

phenopackets_dir = "phenopackets"
phenopackets_files = glob.glob(os.path.join(phenopackets_dir, "*.json"))

for phenopacket_file in phenopackets_files:
    with open(phenopacket_file, "r") as f:
        phenopacket = json.load(f)
    
    for base_engine_str in base_engines:
        for eval_engine_str in eval_engines:
            if eval_engine_str == "None":
                eval_engine = None
            else:
                # 4o has a max context size of 128k; this is built into kani, but 4.1 is not built-in, so we set it to the same as 4o (even though technically it has up to 1M context)
                # 4os max completion tokens is 16384
                eval_engine = OpenAIEngine(os.environ["OPENAI_API_KEY"], model=eval_engine_str, temperature=0.0, max_tokens=16000, max_context_size = 128000)
            
            engine = OpenAIEngine(os.environ["OPENAI_API_KEY"], model=base_engine_str, temperature=0.0, max_tokens=16000, max_context_size = 128000)

            # define output and skip if already done
            output_file = f"results/diagnoses/{os.path.basename(phenopacket_file)}/{base_engine_str}/{eval_engine_str if eval_engine else 'None'}/{os.path.basename(phenopacket_file)}"
            if os.path.exists(output_file):
                print(f"Skipping {output_file} as it already exists.")
                continue
            
            # create agent and prompt
            agent = MonarchKGAgent(engine = engine, eval_agent_engine = eval_engine, prompt_tokens_cost = 2, completion_tokens_cost = 8, retry_attempts = 3, interactive = False)
            prompt = phenopacket_to_prompt(phenopacket, include_ids = False)

            # extract diagnosis and lookup the MONDO ID and name for the diagnosis for later scoring
            # (I do this here rather than in scoring so we can spot-check results by hand during processing)
            diagnosis = phenopacket["interpretations"][0]["diagnosis"]["disease"]["id"] if len(phenopacket["interpretations"]) > 0 else None
            diagnosis_mondo = None

            mondo_query = f"MATCH (d:`biolink:Disease`) WHERE '{diagnosis}' IN d.xref RETURN d.id AS mondo_id, d.name AS disease_name"
            with neo4j_driver.session() as session:
                result = session.run(mondo_query)
                res = result.to_df().to_dict(orient="records")
            if len(res) > 0:
                diagnosis_mondo = res

            # run the diagnosis
            print(f"Running, base: {base_engine_str}, eval: {eval_engine_str}, input: {phenopacket_file}")
            result_messages = full_round_sync(agent, prompt)
            result_messages_as_json = [messages_dump(message) for message in result_messages]


            # format and output results
            result_eval_chain = agent.eval_chain
            result_cost = agent.get_convo_cost()
            result_tokens_used_prompt = agent.tokens_used_prompt
            result_tokens_used_completion = agent.tokens_used_completion
            result_dict = {
                "phenopacket": phenopacket,
                "cost_est_base_rate": result_cost,
                "tokens_used_prompt": result_tokens_used_prompt,
                "tokens_used_completion": result_tokens_used_completion,
                "query": prompt,
                "phenopacket_file": phenopacket_file,
                "expected_diagnosis": diagnosis,
                "base_engine": base_engine_str,
                "eval_engine": eval_engine_str if eval_engine else "None",
                "eval_chain": result_eval_chain,
                "messages": result_messages_as_json,
                "expected_diagnosis_mondo": diagnosis_mondo,
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