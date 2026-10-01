# Repair validation — 2026-10-01

The task now pins ten original EDF+ recordings from PhysioNet EEGMMIDB v1.0.0
using the dataset's official SHA-256 checksums. Docker builds stage them into the
image; the oracle and verifier use no runtime downloads or host dataset cache.
The instruction publishes the complete Welch/reference/aggregation recipe.

Independent source check: `authoring/check_source_measurements.py` was executed
in the image with Docker `--network none`. Its separate SciPy Welch computation
matches all five existing EC/EO densities, ratios, and both group summaries at
relative tolerance 1e-10. The EDF reader is shared with the oracle; this is not
an independent data-reader validation. No numerical reference was regenerated.

The first in-container Harbor oracle produced reward 1.0 with zero exceptions.
After the commit, retain an additional clean-HEAD run with its task digest,
`result.json`, config, actual output files, oracle log and verifier stdout.
Those execution artifacts belong in the maintainer's separate run directory,
not the public agent image. The final exact-HEAD receipt is authoritative over
this pre-commit checkpoint.

Verifier regressions may load the actual retained outputs via
`REPAIR_ORACLE_OUTPUT`; their default reference-copy fixtures are not source
recomputation evidence. The full suite passed 33 checks in a network-disabled
container using the actual retained oracle outputs (28 verifier cases plus five
staging-mechanics unit tests). The numerical checks require every source subject and
separate measurement tolerances from strict EC/EO and group arithmetic. Equivalent
subject labels/order, units notation, channel casing, and rounded measurements
are accepted. Empty summaries fail; prose interpretation needs hand review, not
keyword grading.

Role: **easy control / modern descriptive qualitative replication**. The five
modern participants are not Berger's original cohort; fixed EO→EC run order
precludes a causal eye-state claim. No frontier model calibration was run and
no Sol-unsolvability or hard-benchmark claim is supported. Public numerical
references require a contamination-aware plan for any later model evaluation.
