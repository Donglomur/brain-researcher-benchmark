# Complete matched candidate ablation grading

This operator component connects the existing matched input views to the existing
measured-target score. Supply complete output folders for `full`, `context_only`
and `training_trial_shift`. All three sets of 50 cases must validate before the
first protected target read. Each scored set must retain its initially admitted
schema, prediction fields and exact case-file identities, even if another valid
manifest is substituted later.

The same independently pinned operator design, target arrays and fixed reference
predictions are used for all conditions. Every original grade remains in the
output. The comparison reports signed full-minus-context and full-minus-shifted
incremental explained variance for all 240 mouse/area/joint cells, then averages
joints and areas equally within each of the five mice and mice equally overall.
Negative differences remain valid. No fold or joint is treated as another animal.
Differences are computed directly as `(SSE_control - SSE_full) / SST_target`,
rather than subtracting two potentially large nuisance-based gains. This avoids
losing a real contrast through cancellation when the fixed nuisance error is large.

```sh
python3 -B compare.py \
  --full /operator/outputs/full \
  --context-only /operator/outputs/context-only \
  --training-trial-shift /operator/outputs/training-trial-shift \
  --design /operator/design.json --design-sha256 EXPECTED_DESIGN_SHA256 \
  --private-root /operator/protected-arrays \
  --binding /operator/binding.json --binding-sha256 EXPECTED_BINDING_SHA256 \
  --output /operator/matched-grade.json
```

The Python API `evaluate(submissions, design, trusted_private_loader)` uses the
same operator-only loader contract as the measured-target scorer. The CLI adds
the independent metadata and array hash checks. A participant must not select
these pins or access the targets, reference arrays or other folds' training
labels. Candidate processes must be stopped before grading. File authentication
and the three-panel admission barrier do not provide a participant sandbox.

The measured-target scorer now accepts an optional `expected_admission` keyword,
containing the tuple returned by its existing `admit_submission` function. It
still validates the complete actual submission normally, then refuses a mismatch
before the first protected read. Its one-panel API and existing metric arithmetic
are preserved; each biological row additionally exposes candidate SSE and pooled
target SST for the stable paired calculation. The active paired-preparation loader
pin is updated accordingly.

This code does not establish that the same candidate code, initialization,
hyperparameter selection, compute budget or intended input views were used.
Those conditions require separate observed execution. A positive contrast alone
does not establish causal neural information; training shifts can also change
input distributions. There is no significance test, pass threshold, automatic
paper improvement decision or new scientific qualification.

Full ten-session preparation, MATLAB parity, independently qualified references,
protected participant execution and empirical ablation results remain open.
The original [measured-target scorer](../understanding-metrics-v1/README.md),
[input controls](../matched-input-controls-v1/README.md) and
[roster-bound preparation](../paired-preparation-v2/README.md) retain their scopes.
This adds one usable source component, not another benchmark registration.

`test_compare.py` uses only generated complete panels. It checks the original
single-panel result, independently calculated paired differences, all-mode
admission before protected reads, coherent replacement after admission and shared
private binding failure behavior. It does not fit a model or use neural data.
