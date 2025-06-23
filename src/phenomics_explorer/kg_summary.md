The full model is described at https://biolink.github.io/.

Important node types: 
- `biolink_Gene`
- `biolink_Disease`
- `biolink_ChemicalEntity`
- `biolink_BiologicalProcess`
- `biolink_Cell`
- `biolink_PhenotypicFeature`
- `biolink_Pathway`
- `biolink_Drug`

Important node properties: 
- `name`
- `descripton`
- `id`
- `in_taxon_label` (human readable)

`biolink_Gene` nodes additionally have `symbol` and `full_name`.

Important relationship types: 
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

In cases where multiple relationships could be used to indicate the same information, only most-specific relationships are used. For example, a `Gene` that `causes` a disease will not also have a 
`gene_associated_with_condition` relationship. Finding all associations thus requires querying for both.

Important relationship properties:
 - `has_evidence`: A property of relationships indicating the type of evidence supporting the relationship. 
 - `publications`: A property of relationships referring to publications that are associated with the relationship. 
 - `sex_qualifier`, `frequency_qualifier`, `onset_qualifier`: Found in `biolink:has_phenotype` relationships, indicating potentially clinically significant features for the phenotype.
 - `has_percentage`: An alternative to `frequency_qualifier` specifying frequency as a percentage of cases for `has_phenotype` relationships.
 - `negated`: Found in many relationship types, presense of this propery indicates the relationship should be negated. When used on `has_phenotype` relationships, this used to record features that can be of special differential diagnostic utility.

The following qualifiers are used in the graph:

Sex qualifiers:
| id           | label   |
|:-------------|:--------|
| PATO:0000383 | Female  |
| PATO:0000384 | Male    |

Onset qualifiers:
| id         | label                          |
|:-----------|:-------------------------------|
| HP:0003577 | Congenital onset               |
| HP:0003581 | Adult onset                    |
| HP:0003584 | Late onset                     |
| HP:0003593 | Infantile onset                |
| HP:0003596 | Middle age onset               |
| HP:0003621 | Juvenile onset                 |
| HP:0003623 | Neonatal onset                 |
| HP:0011460 | Embryonal onset                |
| HP:0011461 | Fetal onset                    |
| HP:0011462 | Young adult onset              |
| HP:0011463 | Childhood onset                |
| HP:0025708 | Early young adult onset        |
| HP:0025709 | Intermediate young adult onset |
| HP:0025710 | Late young adult onset         |
| HP:0030674 | Antenatal onset                |
| HP:0034197 | Third trimester onset          |
| HP:0034198 | Second trimester onset         |
| HP:0034199 | Late first trimester onset     |
| HP:0410280 | Pediatric onset                |
| HP:4000040 | Puerpural onset                |
| HP:6000314 | Perimenopausal onset           |
| HP:6000315 | Postmenopausal onset           |

Frequency qualifiers:
| id         | label         |
|:-----------|:--------------|
| HP:0040280 | Obligate      |
| HP:0040281 | Very frequent |
| HP:0040282 | Frequent      |
| HP:0040283 | Occasional    |
| HP:0040284 | Very rare     |
| HP:0040285 | Excluded      |

Evidence qualifiers:
| id          | label                               |
|:------------|:------------------------------------|
| ECO:0000304 | traceable author statement          |
| ECO:0000501 | inferred from electronic annotation |
| ECO:0006017 | published clinical study evidence   |

The `biolink_subclass_of` relationship should be used liberally as `-[r:biolink_subclass_of*0..]->`, indicating that the left hand side is a subtype or subclass of the right side. For example, `(x)-[r:biolink_subclass_of*0..]->(y)` finds y and all of its subtypes, or descendants.
