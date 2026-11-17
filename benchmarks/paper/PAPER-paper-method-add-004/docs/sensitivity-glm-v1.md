# Empirical sensitivity and Figure 7C models

The [sensitivity and model component](../implementations/sensitivity-glm-v1/README.md)
extends this task's existing empirical preparation and four-estimator producer.
Its [frozen prospective policy](../implementations/sensitivity-glm-v1/POLICY.json)
requires complete 5,775-unit input support and records the unresolved differences
between the paper and source notebooks.

The component provides all 103,950 duration/trial sensitivity fit coordinates,
mandatory reports under both reference policies with original-population failure
and retention diagnostics, and the two balanced Gaussian REML Figure 7C source
models. Mouse-bootstrap fixed-effect intervals are a separate prospective
extension. Source models, descriptive stability and animal-grouped uncertainty
have distinct interpretations.

Follow the implementation README for current commands, schemas, exact source
identities and generated controls. It preserves existing task definitions and
historical components and adds no benchmark ID. Original-data admission, paper
QC reconciliation, native/source numerical parity, protected improvement
evaluation and scientific qualification remain required. It does not reconstruct
the historical random windows, source p-values, pooled-area Figure 7B or the
complete paper.
