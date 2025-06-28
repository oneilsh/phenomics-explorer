# Centralized constants and static resource loading for phenomics_explorer
import importlib.resources
import yaml

# Ordered list of categories for Monarch KG
categories = [
    'biolink:LifeStage',
    'biolink:MolecularEntity',
    'biolink:OrganismTaxon',
    'biolink:Cell',
    'biolink:CellularComponent',
    'biolink:MolecularActivity',
    'biolink:SequenceVariant',
    'biolink:ChemicalEntity',
    'biolink:ChemicalOrDrugOrTreatment',
    'biolink:GeneProductMixin',
    'biolink:Protein',
    'biolink:Polypeptide',
    'biolink:Pathway',
    'biolink:Disease',
    'biolink:ChemicalEntityOrProteinOrPolypeptide',
    'biolink:BiologicalProcess',
    'biolink:Occurrent',
    'biolink:BiologicalProcessOrActivity',
    'biolink:AnatomicalEntity',
    'biolink:OrganismalEntity',
    'biolink:SubjectOfInvestigation',
    'biolink:Genotype',
    'biolink:PhenotypicFeature',
    'biolink:DiseaseOrPhenotypicFeature',
    'biolink:Gene',
    'biolink:MacromolecularMachineMixin',
    'biolink:GeneOrGeneProduct',
    'biolink:ChemicalEntityOrGeneOrGeneProduct',
    'biolink:GenomicEntity',
    'biolink:OntologyClass',
    'biolink:PhysicalEssence',
    'biolink:PhysicalEssenceOrOccurrent',
    'biolink:BiologicalEntity',
    'biolink:ThingWithTaxon',
    'biolink:NamedThing',
    'biolink:Entity',
]

# Load graph summary from kg_summary.md
with importlib.resources.files("phenomics_explorer").joinpath("kg_summary.md").open("r") as f:
    graph_summary = f.read()

# Load example queries from monarch_competency_questions_1.yaml
with importlib.resources.files("phenomics_explorer").joinpath("monarch_competency_questions_1.yaml").open("r") as f:
    example_queries = yaml.safe_load(f)

# Create a string version of the example queries, omitting 'expected_answer'
example_queries_str = ""
for query in example_queries:
    if "expected_answer" in query:
        del query["expected_answer"]
    example_queries_str += f"question: {query['question']}\n"
    example_queries_str += f"search_terms: {query['search_terms']}\n"
    example_queries_str += f"query: {query['query']}"
    example_queries_str += "\n\n"
example_queries_str = example_queries_str[:-2]  # Remove last two newlines
