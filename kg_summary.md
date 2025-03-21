Entities and relationships in the graph utilize the BioLink data model described at https://biolink.github.io/.

Common node types: `biolink_Gene` (with additional properties for `symbol` and `full_name`), `biolink_Disease`, `biolink_ChemicalEntity`, `biolink_BiologicalProcess`, `biolink_Cell`, `biolink_PhenotypicFeature`, `biolink_Pathway`, `biolink_Drug`, `biolink_Publication`, `biolink_EvidenceType`.

Common node properties: `name`, `descripton`, `id`, `in_taxon_label` (human readable), `synonym` (multi-valued).

Common relationship types: `biolink_interacts_with`, `biolink_expressed_in`, `biolink_has_phenotype`, `biolink_actively_involved_in`, `biolink_orthologous_to`, `biolink_enables`, `biolink_located_in`, `biolink_subclass_of`, `biolink_participates_in`, `biolink_gene_associated_with_condition`, `biolink_causes`, `biolink_contributes_to`, `biolink_enables`, `biolink_part_of`, `biolink_related_to`.

Unique relationship properties:
 - `has_evidence`: A property of relationships indicating the type of evidence supporting the relationship. Found in relationships such as `biolink_acts_upstream_of_or_within`, `biolink_actively_involved_in`, `biolink_enables`, `biolink_located_in`, `biolink_part_of`, and `biolink_orthologous_to`.
 - `publications`: A property of relationships referring to publications that are associated with the relationship. Found in relationships such as `biolink_has_phenotype` and `biolink_has_mode_of_inheritance`.
 - Qualifier properties: Provide additional context to relationships. Examples include `sex_qualifier`, `frequency_qualifier`, `onset_qualifier`, and `stage_qualifier`. Found in relationships such as `biolink_has_phenotype` and `biolink_expressed_in`.


General labels such as `biolink_Entity` and `biolink_NamedThing` are very common and may be too general for most queries.

Biological labels like `biolink_BiologicalEntity` and `biolink_PhysicalEssence` are also quite common but cover a wide range of biological concepts.

Specific labels such as `biolink_Gene`, `biolink_Disease`, and `biolink_ChemicalEntity` are useful for targeted queries.