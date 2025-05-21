The full model is described at https://biolink.github.io/.

Common node types: 
- `biolink_Gene`
- `biolink_Disease`
- `biolink_ChemicalEntity`
- `biolink_BiologicalProcess`
- `biolink_Cell`
- `biolink_PhenotypicFeature`
- `biolink_Pathway`
- `biolink_Drug`
- `biolink_Publication`
- `biolink_EvidenceType`.

Common node properties: `name`, `descripton`, `id`, `in_taxon_label` (human readable), `synonym` (multi-valued). `biolink_Gene` nodes additionally have `symbol` and `full_name`.

Common relationship types: 
- `(sub:biolink_Gene)-[pred:biolink_interacts_with]->(obj:biolink_Gene)`
- `(sub:biolink_Gene)-[pred:biolink_expressed_in]->(obj:biolink_CellularComponent or obj:biolink_AnatomicalEntity)`
- `(sub:biolink_Gene or sub:biolink_Disease)-[pred:biolink_has_phenotype]->(obj:biolink_PhenotypicFeature)`
- `(sub:biolink_Gene)-[pred:biolink_actively_involved_in]->(obj:biolink_BiologicalProcess)`
- `(sub:biolink_Gene)-[pred:orthologous_to]->(obj:biolink_Gene)`
- `(sub:biolink_Gene)-[pred:biolink_enables]->(obj:MolecularActivity)`
- `(sub:biolink_Gene)-[pred:biolink_participates_in]->(obj:BiologicalProcess)`
- `(sub:biolink_Gene)-[pred:biolink_gene_associated_with_condition]->(obj:Disease)`
- `(sub:biolink_Gene)-[pred:biolink_causes]->(obj:Disease)`
- `(sub:biolink_Gene)-[pred:biolink_contributes_to]->(obj:MolecularActivity)`
- `(sub:biolink_Gene)-[pred:biolink_part_of]->(obj:biolink_CellularComponent or obj:biolink_AnatomicalEntity)`
- `(sub:biolink_PhenotypicFeature)-[pred:biolink_related_to]->(obj:biolink_BiologicalProcess or obj:biolink_AnatomicalEntity or obj:ChemicalEntity)`
- `(x)-[r:biolink_subclass_of*0..]->(y)`

The `biolink_subclass_of` relationship should be used liberally as `-[r:biolink_subclass_of*0..]->`, indicating that the left hand side is a more specific type of the right hand side. For example, `(x)-[r:biolink_subclass_of*0..]->(y)` finds y and all of its subtypes, or descendants. This may also be described as the set of ys, or all instances of a y.

Unique relationship properties:
 - `has_evidence`: A property of relationships indicating the type of evidence supporting the relationship. Found in relationships such as `biolink_acts_upstream_of_or_within`, `biolink_actively_involved_in`, `biolink_enables`, `biolink_located_in`, `biolink_part_of`, and `biolink_orthologous_to`.
 - `publications`: A property of relationships referring to publications that are associated with the relationship. Found in relationships such as `biolink_has_phenotype` and `biolink_has_mode_of_inheritance`.
 - Qualifier properties: Provide additional context to relationships. Examples include `sex_qualifier`, `frequency_qualifier`, `onset_qualifier`, and `stage_qualifier`. Found in relationships such as `biolink_has_phenotype` and `biolink_expressed_in`.

