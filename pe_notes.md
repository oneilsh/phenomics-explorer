## Implementation Notes - Phenomics Explorer

The Phenomics "Explorer" agent implemented in this branch uses LLMs to
generate Cypher queries against the Monarch Initiative Neo4J database. Many LLMs (including GPT-4, 
extensive testing has not been done with GPT 4.1) struggle with accurate generation of Cypher queries, 
and need sufficient context about the graph to generate effective queries. 
This implementation attempts addresses these with 
system-prompt information, including a [summary](kg_summary.md) of KG contents and a set of
[example competency questions and queries](monarch_competency_questions_1.json). (These were generated
interactively via trial-and-error with a similar query-generating agent.) Queries are also modified
to mutate biolink labels; rather than queries like ```MATCH (n:`biolink:Disease`)```, the agent can 
forgo the uncommon backtics and query `MATCH (n:biolink_Disease)`.

When the agent wishes to run a query, an evaluator agent is inserted in the process, which checks the query and
result against the user question. The evaluator is given specific criteria to evaluate and prompted to think
step-by-step. It registers a summary of the query and suggestions for improvement (via tool call), as well as 
pass/fail grade. If the evaluation fails, an error is thrown to the parent agent with a
suggestion for improvement. Malformed queries are captured as errors, with the syntax error message
provided back to the agent for trying again. Queries that return more than 10k tokens also result in an error
and suggestion for the agent to try again with a smaller query. In all cases of error, the main agent
my try again (up to 3 times).

Results with the recent GPT 4.1 are significantly improved over earlier results with 4o and even 4. 
The agent has a tendency to be literal, for example "Which genes are associated with CF?" for example may use only
`biolink:gene_associated_with_condition` links due to the "associated" keyword when
`biolink:causes` and other relationships may be important.

NOTE: The code structure in this branch is terrible, currently. (A result of a poor attempt to abstract
Neo4j KG agents generally from the Monarch agent specifically.)