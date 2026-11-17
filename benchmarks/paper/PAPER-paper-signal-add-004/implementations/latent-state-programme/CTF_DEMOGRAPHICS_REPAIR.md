# CTF demographic identity repair

The original preparation assigned each CSV age to `subject00` through `subject64`
by position and ignored the released `name` field. A full65-row table containing
a duplicated, unknown or permuted identity could therefore be relabeled as the
original complete cohort. Nonfinite ages also passed the CSV parse. This affects
the correctness of the separately recorded age-to-person join, not the primary
within-branch fitting statistic.

`source_inputs.ctf_demographics` now requires all65 literal ordered source names,
the released four-column schema and finite ages satisfying the age domain already
used by `diagnostics.age_group`. Duplicate headers and incomplete/extra fields
fail closed. It does not sort rows: the author scripts consume the literal source
order, so accepting a reordered table would obscure a source mismatch. The raw
CSV remains byte-preserved by the existing preparation. The static/dynamic age
policies, including their distinct age34 boundary conventions, remain unchanged.
Preparation validates the demographic member before reading signal members or
publishing data, avoiding partial array output from a failed identity check.

The evidence for the source schema is the task's existing saved loader metadata:
`name, age, gender, handedness`, with `subject00` through `subject64` matching the
signal filenames. This repair does not newly authenticate the archive body or
claim that its original table is misordered. The exact archive pin, source
revision, all six branches, original source split, fitting criteria and companion
controls remain unchanged. The preserved predecessor is
`historical/source_inputs.pre-demographic-identity-v2.py` within this implementation.

Generated tests exercise the actual parser, identity substitutions, reordered
rows, incomplete cohorts, malformed CSV/headers, nonfinite ages and the existing
distinct source age policies. They read no neural arrays or private targets and
run no model. A generated133-member archive also exercises the actual preparation
entry point and proves it rejects identity mismatch before signal decoding or
output publication. This is an input software repair; original numeric baselines,
DyNeMo trajectory attestation, historical runtime qualification and empirical
paper improvement remain unresolved. Source-manifest and central integration
pin refreshes are proposed separately to the integration owner; historical
manifests are retained as historical evidence.
