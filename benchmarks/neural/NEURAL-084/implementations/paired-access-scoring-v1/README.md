# Paired restricted-observation and program assessment

This operator-only component compares two complete NEURAL-084 submissions on
the same 21,600 source cases. It fills the gap between the existing full-panel
viewer/program response collectors and the existing single-candidate scorer.
It does not execute either participant or change the scientific task.

`score.py` captures all 54 folds from each of five directories: `restricted`,
`program`, `cca`, `constant`, and `frequency-permuted`. Every file must satisfy
the existing raw-score schema, generation, fold and sorted 400-query identities
from one protected full54 pool. All 270 files are admitted before gold is
opened once. An incomplete/malformed condition or control blocks the whole
comparison; there is no partial-fold or successful-case-only analysis. Captured
winners and hashes are retained, and submissions are never reread after gold.

The original endpoint remains equal-person/session/acquisition-phase/class
mean recall, using all 54 people, both sessions, both phases and all four
overt-gaze targets. Argmax ties choose the earliest source class. Source labels
and nominal frequencies 60/[5,7,9,11] Hz are unchanged. Both candidates retain
their phase confusion matrices/support, session scores and person scores.
The output adds program-minus-restricted differences at all three levels, each
candidate's differences from the three shared controls, and complete paired
correctness counts (both correct, restricted only, program only, neither) for
each person and the cohort. These counts are descriptive: trials are nested
within people, donor sets overlap, and no independent-trial p-value or population
confidence interval is supplied. The report exposes no query IDs or gold rows.

## Operator use

Keep the pool, gold, scorer and report protected from participants. Supply the
independently authenticated pool size and SHA-256, with distinct directories
containing exactly `fold001.json` through `fold054.json`:

```text
python3 -I -S -B score.py --pool /protected/pool.json \
  --pool-bytes <verified-size> --pool-sha256 <verified-sha256> \
  --restricted /captured/restricted --program /captured/program \
  --cca /captured/cca --constant /captured/constant \
  --frequency-permuted /captured/frequency-permuted \
  --out /protected/new-paired-report.json
```

These paths illustrate deployment; no authentic files are bundled. The scorer
reuses, and checks the SHA-256 of, the accepted `full-cohort-scoring-v1/score.py`
and `delivery-source/public/io_utils.py`. A trusted source mirror may set
`NEURAL084_SOURCE_IMPLEMENTATIONS` to their implementations directory. No
historical source or pin is rewritten. `grade(pool_raw, prediction_loader,
gold_loader)` exposes the same operation to a trusted operator; callbacks must
never be participant-provided code. Directory/IO checks are source controls,
not a filesystem or network sandbox.

## What the comparison establishes

The shared pool and exact query IDs establish the same source cases and labels.
The names `restricted` and `program` record the intended conditions; the scorer
cannot verify their execution, participant identity, training exposure, compute,
cross-fold reset, external tools or observation delivery. Its output explicitly
marks information equivalence, access enforcement and method provenance as
unestablished. In particular, numerical arrays and rasterized waveforms can
derive from the same epoch yet have different precision and perceptual access.
The supplied CCA/control names likewise do not authenticate their producer.

A prospective comparison must bind each condition's actual delivery/runtime
receipts and frozen policy, permitted information, training access and resource
budget before outcomes are inspected. Native/direct, typed-viewer and adaptive
tool conditions must be separately declared; they cannot be inferred from a
prediction file or collapsed into a general native-versus-tool result. This
module does not add such a study or qualify one. Authentic preparation, protected
source provenance, full participant execution and reference qualification remain
absent. Generated checks establish neither EEG readability nor model competence.

## Focused generated controls

Run `python3 -I -S -B test_score.py` after integration. Five tests reuse only the
existing complete generated metadata fixture, then create two distinct synthetic
prediction streams. An integer oracle checks matched counts, the paired endpoint
and complete strata. Negative controls exercise missing/late malformed output,
generation and case mismatch before gold, and prediction capture before gold.
The CLI test uses real directory preflight and exclusive report creation with an
explicit in-memory read adapter; it does not claim a full filesystem-payload
round trip or replay existing transport tests. Source-only generation uses no
EEG, model, private inputs, downloaded datasets or empirical scores.

The sole integrator must register this additive component, enroll its focused
test in CI and bind a future protected scoring handoff. Existing programme
closure receipts and readiness remain unchanged.
