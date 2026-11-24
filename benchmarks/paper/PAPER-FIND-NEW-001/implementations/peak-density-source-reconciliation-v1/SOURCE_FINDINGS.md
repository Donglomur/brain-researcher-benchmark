# Original peak-density endpoint: source reconciliation

This source finding concerns the peak-time density comparison in the May 2026
preprint. It does not replace the historical odd/even sequence-correlation
adapter. The final Nature Neuroscience endpoint and author replay remain
unqualified.

The inspected [preprint](https://pmc.ncbi.nlm.nih.gov/articles/PMC13232304/)
is the retained PMC13232304.2 text, SHA-256
`ef74c2e3983959cc8cd0a46b2f1876c456ead83abb7051b0be92e737845968e2`.
The archived [author revision](https://github.com/rsenne/dCA1_Paper/tree/5be84b41dc3580dd4942ea72b8c50a3248538821)
has a complete, non-truncated 155-entry tree; retained tree SHA-256
`08588d0bd66bd1f513bdbe67a131ca94c94cda2d60f68469343c749ff04cbcaa`.
These are existing public source caches, not new scientific observations.

## Comparison support that must survive admission

| Original panel | Observation context | Required density models |
| --- | --- | --- |
| Figure 2h | Fear conditioning, excluding inferred peaks below 2 seconds | Power law, exponential, Gaussian, uniform |
| Figure 4e | Recall context A | Same four models |
| Figure 4f | Recall context B | Same four models |
| Extended Data Figure 17c | Recall A/B separately for each sex | Same four models in all four strata |
| Extended Data Figure 20e | Habituation control, F9 and M10 | Same candidate comparison; exact complete table still needed |

The current canonical improvement contract mentions conditioning, recall and
sex strata but does not explicitly name the habituation companion. Integration
should add it to the source-reconciliation obligation; it must not silently
become an optional favorable-context comparison.

The preprint's habituation prose gives uniform WAIC **1192.9** while its
Extended Data Figure 20e caption gives **1192.2**. Both give power-law WAIC
1189.1. The difference is a source inconsistency, not a rounding tolerance to
be chosen by the evaluator. No value from either location is admitted as a
final-paper author baseline here.

## Peak inference is distinct from density fitting

The Methods section estimates event-specific peak locations with Gaussian
temporal fields, a cell-level peak center, between-sequence variability,
baseline and field amplitude/width. It describes rStan, four chains, 3750
warm-up iterations and 250 retained iterations per chain, followed by posterior
modes. These are statements about the temporal-response model. They do not
identify the priors, pointwise log likelihood or posterior sampling recipe for
the subsequent four-family density comparison.

The pinned author tree has four processed modeling CSVs and distribution
plotting notebooks. It has no files ending in `.R`, `.r` or `.stan`.
Absence of those filenames does not prove the model is absent from notebooks,
another repository or an unexamined release. A generic WAIC implementation
would therefore not establish source parity.

## Bounded source recovery

The next exact code sources identified from the complete tree are:

| Pinned relative path | Bytes | Git blob SHA-1 |
| --- | ---: | --- |
| `notebooks/figures/Figure2_3_distribution_histograms.ipynb` | 21071 | `8d8af9ad5b835bdbfc77ad1a50e435586a409b23` |
| `notebooks/supplementary/theoretical_dists.ipynb` | 4989 | `549e0c27eb4c478de198181e91e6cef126e4ef12` |
| `notebooks/supplementary/Figure_2_peak_props.ipynb` | 19995 | `b2cb339eacca9a889d59ee680fdf5f8d6cbbf746` |

No notebook was successfully recovered in this pass. The raw host failed TLS
negotiation with both curl and certificate-verifying urllib. The official
GitHub contents route returned a 279-byte HTTP 403 rate-limit response. The
failed response stays outside Git. No notebook code was inferred from its
filename, and the two remaining notebooks were not requested after that
failure. The pinned tree identifies source locations, not their execution
semantics.

The four released modeling tables are `astrocyte_shot_Gaussian_noise3_all.csv`,
`astrocyte_NEWcxtA_Gaussian_noise3_all.csv`,
`astrocyte_NEWcxtB_Gaussian_noise3_all.csv`, and
`astrocyte_NEWhab_Gaussian_noise3_all.csv` under `data/processed/modeling/`.
Their schemas, units, animal/cell identifiers, exclusions and relationship to
posterior modes must be authenticated from actual source before implementing
an input exporter. They were neither downloaded nor opened in this pass.

## Qualification boundary

Reproduction and same-task improvement remain separate intended outcomes.
Neither outcome is established by this source finding. Source claims above
preserve the preprint/final-version distinction. No trace
analysis, model fit, WAIC rerun, candidate trial or biological performance
measurement was performed. Canonical task and improvement contracts, old
scorers and historical evidence remain unchanged.

## November 24 final-source recovery

[Machine-readable source observations](final-source-observations.v1.json) now
resolve a specific preparation gap: the original seven-panel comparison has
28 explicit slots, with 12 final-paper caption values recovered and 16 sex-
stratified values still explicitly unrecovered. These are published source
observations, never score targets, author replay outputs or tolerances. The
manifest gives URLs, response hashes, original panel locators and the inspected
code revision so future preparation can reuse the recovered source identities.
The earlier account above remains intact as the record of that earlier pass.
Its older proposed HAB obligation is historical: the current seven-panel,
28-row primary contract takes precedence, with HAB required only for claims
that depend on the learning-emergence comparison.

The final [Figure 2](https://www.nature.com/articles/s41593-026-02448-0/figures/2)
and [Figure 4](https://www.nature.com/articles/s41593-026-02448-0/figures/4)
captions identify the same four-family pooled WAIC comparisons. The reported
density populations are conditioning 14 mice/2,707 astrocytes, recall A
11/1,371 and recall B 10/924. These caption counts do not authenticate original
row membership. In particular, recall B's separate odd/even correlation uses
seven animals after its event restriction; applying that restriction to density
inputs would change the paper's population.

The final article's public Extended Data Figure 8 maps the preprint's Figure
17 sex-stratified evidence, and its Figure 10 maps the preprint's Figure 20 HAB
companion. The final HAB caption prints uniform WAIC 1192.9. This identifies
the final caption value without rewriting the prior preprint discrepancy or
adding HAB to the authorized primary. The final source also distinguishes
peak-distribution counts from peak-variability counts. The accessible main
article is a subscription preview; its Methods body was not recovered.

All three previously identified notebooks were recovered over certificate-
verified HTTPS, and each matched its previously recorded Git blob SHA-1 and
byte count. They provide histogram/sex plotting, toy Poisson-null simulation,
and a peak-width companion respectively. None of these three contains the
four-family density fit or WAIC computation. This is a finding about the
inspected notebooks, not proof of absence elsewhere. The peak-width notebook
excludes F8, adds certain HAB animals and trims a display tail; these operations
belong to that companion and do not establish primary density preprocessing.

Final-caption correspondence is therefore partially recovered; executable
density semantics, complete native input/output support, the 16 sex-table
values and uncertainty remain unresolved. Printed agreement cannot establish
reproduction or improvement. Neither matched information condition gains a
qualified author density implementation from these plotting notebooks. All
canonical contracts, historical source evidence and readiness states remain
unchanged. No notebook, authentic dataset, model or scorer was executed.
