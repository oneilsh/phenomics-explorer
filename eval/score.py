# for reading API keys from .env file
import os
import dotenv # pip install python-dotenv
import json
import glob
import isodate
from neo4j import GraphDatabase
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# kani imports
from kani.engines.openai import OpenAIEngine
from typing_extensions import Annotated
from typing import Optional
from kani import AIParam, ai_function, ChatMessage, ChatRole


# read API keys .env file (e.g. set OPENAI_API_KEY=.... in .env and gitignore .env)
import dotenv
dotenv.load_dotenv(override=True) 

from kani_utils.utils import full_round_sync

from kani_utils.base_kanis import EnhancedKani


class ScoringAgent(EnhancedKani):
    """Agent for scoring results in the results/ directory. To be used once."""
    
    def __init__(self, *args, correct_diagnosis = None, **kwargs):
        super().__init__(*args, **kwargs)        

        self.correct_diagnosis = correct_diagnosis
        self.score = None

        self.update_system_prompt("""
You are a data extraction agent, tasked with extracting for further processing an ordered list of MONDO IDs from a given result text describing a differential diagnosis for a disease. When prompted, process the given input and call your process_candidates() function, being sure to submit IDs in the order specified. Example:
                               
Input:
"Based on the provided information, the differential diagnosis includes the following conditions:
1. Mondo:0001234 - Example Disease A
2. Mondo:0005678 - Example Disease B
3. Mondo:0009101 - Example Disease C"
                               
Call: process_candidates(["MONDO:0001234", "MONDO:0005678", "MONDO:0009101"])
                               
Input: 
"This patient may have one of the following conditions:
1. Mondo:0001111 - Example Disease D
2. Mondo:0002222 - Example Disease E"
                               
Call: process_candidates(["MONDO:0001111", "MONDO:0002222"])
                               
Input:
"Based on the provided information, there is no clear differential diagnosis. We can rule out MONDO:0003333 given the presence of phenotype X, but no more specific conditions can be identified at this time."

Call: process_candidates([])  # No candidates to extract 
""".strip())

    @ai_function(after=ChatRole.USER)
    def process_candidates(self, candidates: Annotated[list[str], AIParam(desc="A list of MONDO IDs extracted from the input text. The IDs should be in the order they were specified in the input text.")]):
        """Process a set of candidate MONDO disease IDs extracted from input text."""
        # first let's make sure they all match the MONDO ID format, MONDO: followed by digits
        if not all(isinstance(c, str) and c.startswith("MONDO:") and c[6:].isdigit() for c in candidates):
            raise ValueError("All candidates must be valid MONDO IDs in the format 'MONDO:1234567'. Please try again, and if no MONDO IDs are identified as candidates, call this function with an empty list.")

        # top_1_score is 1 if the first candidate is the correct diagnosis, 0 otherwise
        top_1_score = 1 if (len(candidates) > 0 and candidates[0] == self.correct_diagnosis) else 0
        # top_3_score is 1 if the correct diagnosis is in the top 3 candidates, 0 otherwise
        top_3_score = 1 if (self.correct_diagnosis in candidates[:3]) else 0
        # top_10_score is 1 if the correct diagnosis is in the top 10 candidates, 0 otherwise
        top_10_score = 1 if (self.correct_diagnosis in candidates[:10]) else 0

        res = {
            "candidates": candidates,
            "top_1_score": top_1_score,
            "top_3_score": top_3_score,
            "top_10_score": top_10_score,
        }

        self.score = res
        return res


def gen_score_row(file, score_dict, expected_diagnosis):
    """Generate a row for the scores DataFrame."""
    return {
        "file": os.path.basename(file),  # just the file name, not the full path
        "top_1_score": score_dict["top_1_score"],
        "top_3_score": score_dict["top_3_score"],
        "top_10_score": score_dict["top_10_score"],
        "expected_diagnosis": expected_diagnosis,
        #"candidates": score_dict["candidates"],
        "base_agent": file.split(os.sep)[-3],  # extract base agent name from file path
        "eval_agent": file.split(os.sep)[-2],  # extract eval agent name from file path
    }

# we're going to modify-in-place the .json files in the results/ directory, which will be in deeper subdirectories
def add_scores_to_results():
    """Add scores to the results in the eval/results/diagnoses directory and subdirectories. We only want files, not directories (even if they have a .json extension)."""
    results_files = glob.glob("eval/results/diagnoses/**/*.json", recursive=True)
    results_files = [f for f in results_files if os.path.isfile(f)]
    results_rows = []

    total_files = len(results_files)
    num_processed = 0
    
    for results_file in results_files:
        num_processed += 1

        with open(results_file, "r") as f:
            results = json.load(f)

        # if a correct diagnosis exists, if will be at results["expected_diagnosis_mondo"][0]["mondo_id"]
        # if it isn't there, is the wrong format, OR if there is more than one, we skip the file and log a big warning to stderr
        if "expected_diagnosis_mondo" not in results or len(results["expected_diagnosis_mondo"]) != 1:
            sys.stderr.write(f"WARNING: Skipping {results_file}, REASON: expected_diagnosis_mondo is missing or has more than one entry.\n")
            continue

        expected_diagnosis = results["expected_diagnosis_mondo"][0]["mondo_id"]
        
        if not expected_diagnosis.startswith("MONDO:") or not expected_diagnosis[6:].isdigit():
            sys.stderr.write(f"WARNING: Skipping {results_file}, REASON: expected_diagnosis_mondo is not a valid MONDO ID: {expected_diagnosis}\n")
            continue

        if "score" in results:
            print(f"Skipping already score {results_file}.")
            # we still need to save the score to the results_rows, so we can later save it to a CSV
            scores_str = f"t1: {results['score']['top_1_score']}, t3: {results['score']['top_3_score']}, t10: {results['score']['top_10_score']}"
            results_rows.append(gen_score_row(results_file, results["score"], expected_diagnosis))
            continue  # skip files that already have a score

        # the answer we want to score is in the last message of the results
        if len(results["messages"]) == 0 or results["messages"][-1]["role"] != "assistant":
            sys.stderr.write(f"WARNING: Skipping {results_file}, REASON: last message is not from the assistant or there are no messages.\n")
            continue

        answer_text = results["messages"][-1]["content"]

        # calculate the score
        engine4 = OpenAIEngine(os.environ["OPENAI_API_KEY"], model="gpt-4o-2024-11-20", temperature=0.0, max_tokens=16000)
        agent = ScoringAgent(engine=engine4, correct_diagnosis = expected_diagnosis)
        result = full_round_sync(agent, "Please process candidate diagnoses from the following answer:\n\n" + answer_text)

        # the score is in the agent's score attribute (and the last message of the result)
        score = agent.score
        
        # add the score to the results
        results["score"] = score
        
        # save the updated results
        with open(results_file, "w") as f:
            json.dump(results, f, indent=4)
        
        scores_str = f"t1: {score['top_1_score']}, t3: {score['top_3_score']}, t10: {score['top_10_score']}"
        print(f"Score: {scores_str}\tProcessed {num_processed}/{total_files}: {results_file} ({num_processed / total_files * 100:.2f}%).")

        results_rows.append(gen_score_row(results_file, score, expected_diagnosis))
    
    print(f"Scores added to {len(results_files)} files.")
    # conver to pandas DataFrame and return
    df = pd.DataFrame(results_rows)
    return df


if __name__ == "__main__":
    # run the scoring on the results/ directory
    df = add_scores_to_results()
    # save the results to eval/results/scores.csv

    output_file = "eval/results/scores.csv"
    df.to_csv(output_file, index=False)

    # make a quick faceted histogram of the scores, broken down by base agent, eval agent, and top N score
    print(f"Scores saved to {output_file}.")

    df['agent_combo'] = df['base_agent'] + ' + ' + df['eval_agent']

    summary = df.groupby('agent_combo').agg(
        top_1_score_mean=('top_1_score', 'mean'),
        top_3_score_mean=('top_3_score', 'mean'),
        top_10_score_mean=('top_10_score', 'mean')
    ).reset_index()

    plot_df = summary.melt(
        id_vars='agent_combo',
        value_vars=['top_1_score_mean', 'top_3_score_mean', 'top_10_score_mean'],
        var_name='Top-N',
        value_name='Accuracy'
    )

    plot_df['Top-N'] = plot_df['Top-N'].str.extract(r'top_(\d+)_score_mean').iloc[:,0].astype(str)
    plt.figure(figsize=(10,6))
    sns.barplot(
        data=plot_df,
        x='Top-N',
        y='Accuracy',
        hue='agent_combo'
    )

    plt.ylabel("Percentage of correct diagnoses (%)")
    plt.xlabel("")
    plt.title("Model Performance by Agent Combination")
    plt.ylim(0, 1)  # Since your scores are in [0,1]; multiply by 100 if you want percentage
    plt.legend(title='Model')
    plt.tight_layout()
    plt.savefig("eval/results/scores_plot.png")


    print("Scoring completed.")