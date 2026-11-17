# Cardiac age-association reconstruction

Re-estimate how the age association of the Salzburg MEG spectral slope changes
between ECG retained, ECG rejected and the ECG components. Use the complete
655-person released processed table. Deliver all six separately inferred raw and
standardized Student-t models and all 30 parameter summaries in `summary.json`,
using the unchanged `submission_schema.json` and `instructions.md`.

This is the inherited **shared-specification reconstruction condition**: both
arms receive the same source-informed model and summary definitions. A receives
the paper, data and that specification; B additionally receives the exact named
official-source capture. It is not an unaided paper-only reasoning test. Neither
arm receives fitted answers, a developer numerical implementation or a private
reference. The article itself reports public results; this is exposed development
reconstruction, not blind evaluation. `SOURCE_MAP.md` explains the source meanings.

Read `MODEL_CONTRACT.json`, `MATH_SPEC.md` and `instructions.md`. Preserve all rows
and independently fit each raw/standardized model. The six fixed seeds in the
model contract are reconstruction-control choices, not recovered paper seeds or
an admission requirement. Other valid inference implementations and seeds are
permitted. Do not replace posterior inference with OLS, fabricated draws or an
affine conversion of raw posterior draws to the standardized model.

Submit your UTF-8 `program.py` and complete UTF-8 `summary.json` through the
operator's condition request. The summary has a 200,000-byte limit; the program
has a 131,072-byte limit. The operator snapshots exact files for both conditions
before releasing a pair manifest. It never imports or executes your program.
No score, inference correctness, convergence or scientific qualification is
inferred from successful structural capture. This profile stops at pair closure:
the inherited instructions describe the older paired scorer, but this route
never opens a fixed target. Independent reference and inference admission is
still required before any downstream grading.

This delivery has no bundled numerical environment, bootstrap or wheels. Before
a candidate attempt the operator must establish the same usable numerical
environment and declared authoring/execution resources for both conditions.
The old Linux CPython 3.12 wheels and 120-second/3-GiB profile are not this
profile. Current local Bambi/PyMC/ArviZ absence is a concrete fitting blocker;
this package provides no replacement sampler and grants no extra compute or
installation authority. No feasibility or candidate result is claimed.

The original question is an association comparison on already processed slopes.
Raw ICA/spectral preprocessing, CamCAN replication, joint causal cardiac removal,
unseen-participant improvement and whole-paper reproduction remain outside this
six-model endpoint. Correlated conditions are not independent biological samples.
