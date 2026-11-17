# Fixed no-change control

`control.py` is an engineering control for the existing processed-morphology and
coactivity prediction task. It predicts the dimensionless follow-up/baseline
volume ratio **1.0** for every requested row. It does not estimate a model, select
features, tune parameters, or use training labels. NumPy only parses the integer
query-row vector; feature matrices and training-target arrays are not decoded.

The original participant invocation is unchanged:

```text
/usr/local/bin/python -I -B /program/submission.py --input /input/data.npz --manifest /input/manifest.json --output /output/predictions.json
```

The two input files belong to the current mouse/view context. The manifest
authenticates the bounded archive; its exact original bytes are hashed into the
prediction. The ordered query IDs are copied unchanged from `query_rowid`.
Every requested row receives ratio 1, including the 43 requests whose follow-up
target is unavailable. The program has no private target input and cannot
identify those unavailable follow-ups. Private scoring retains the original
731 observed rows, equal-mouse denominator, missingness policy and references.

The exact same program is frozen before the first context and is used for both
baseline and neural inputs. The only view-dependent output is the required
identity field copied from the manifest. Predictions do not depend on either
view's features, labels, missingness or mouse identity. Therefore this specific
constant procedure is matched across views by source inspection. The expected
paired gain is exactly zero; absolute errors depend on the authentic targets
and must be measured by the protected scorer, never invented in advance.

This review applies only to this fixed control. A matching-program hash or a
method declaration does not prove that an arbitrary submitted program uses
matched tuning procedures or avoids intentionally degrading one arm.

Each CLI input is a regular non-symlink file: archive at most 262,144 bytes and
manifest at most 16,384 bytes. Only a bounded 16,384-byte query-vector member is
decompressed and decoded. The NPY header must specify the expected one-dimensional
little-endian int64 extent before any array view is created. Output is exclusive,
at most 131,072 bytes, and uses the original prediction schema. The program
itself is not a sandbox, source-preparation validator, or runtime certificate.
The executor must still deliver fresh isolated contexts, prevent cross-fold
access, close producers and validate all 40 outputs before private scoring.

Generated controls exercise the full 20-mouse, two-view, 774-request contract and
the unchanged scorer on invented values, plus malformed input and exclusive
output cases. These checks do not establish authentic execution, participant
isolation, neural understanding or scientific performance.

## Fixed runtime observations

Before reading either public input, the CLI checks UID/GID 65534, an absent fixed
temporary marker and an empty output directory. It then creates that marker,
requires write-open denials for the read-only root and each of the three mounted
files, and requires an explicit network-denial errno when connecting to the
documentation address `192.0.2.1:9` with a 0.25-second timeout. Mounted files are
opened with `O_WRONLY` without truncation or a write; a successful open fails the
control. A timeout or connection refusal is not accepted as a network denial.

One JSON stdout record, capped at 4,096 bytes, reports only versions, identity,
freshness booleans and denial errnos. It contains no biological values, row IDs
or paths. No extra output file changes the original single-prediction file
contract. A fixed reader captures that file inside the running namespace; the
operator commits the captured bytes only after pause, inspection, removal and
observed absence. This is not a claim of an atomic paused-filesystem snapshot
or general protection from hostile concurrent descendants. The container has
to run successfully and its report has to be
preserved and reviewed before these observations exist. They establish only the
listed behavior of the selected runtime. Do not run this probe on the host;
generated tests mock all probe filesystem and network operations.
