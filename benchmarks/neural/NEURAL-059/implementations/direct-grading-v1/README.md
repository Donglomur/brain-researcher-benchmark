# Protected direct probability grading

This operator entrypoint closes the score-null handoff from
`direct-probability-v1`. It grades complete direct numerical captures as their
own access condition, without relabeling responses as frozen programs (F),
investigating programs (I), or references (R).

`grade_capture` authenticates the existing delivery source and replays every
captured response through that collector. The collector validates all original
trial slots in the ordered 29-session, 13-animal, seven-laboratory roster. Replay
checks each exact projected observation, recorded UTF-8 response, byte hash,
probability, case identity, session, condition, and four-condition history
barrier. The complete replay artifact must equal the submitted capture under
typed canonical JSON equality. Missing or duplicate responses, changed counters,
fabricated qualification flags, altered probabilities, extra fields, and changed
prepared-input hashes are refused. A failed capture produces no aggregate score;
the original capture must be retained by the operator. No supported subset can
be substituted for the complete endpoint.

After replay succeeds, the protected grader joins held choices to probabilities
and calls the existing pinned probability arithmetic. Log loss uses the retained
1e-12 clipping rule, and remains primary. Session-level and pooled-trial scores
are secondary; the primary pools all required trials within each animal before
equally weighting all 13 animals. Brier score, threshold-0.5 balanced accuracy,
tie-correct AUC, class counts, clipping counts and per-trial operands remain
inspectable. One-class BA/AUC stays undefined rather than being assigned zero.

The four paired neural/context contrasts retain the same condition definitions,
all 13 animal effects, leave-one-animal and leave-one-laboratory summaries, and
the retained 1,999-draw conditional spread. That spread has unqualified coverage,
no refitting and no established animal exchangeability; it is not a p-value or
binary success test. Positive gain means lower log loss/Brier or higher BA/AUC
after adding the named information.

## Operator use

Preparation, captures, and scores belong in a protected operator workspace
outside Git and participant mounts. Preparation contains held targets and is
read for original-slot integrity before replay; target values enter metric
arithmetic only after the complete replay passes. This is trusted operator code,
not a target-access sandbox. Inputs use strict UTF-8 JSON and reject duplicate
keys. All ceilings are explicit positive selections from the actual frozen run;
the grading limits do not establish participant compute-budget equivalence.

```sh
python3 -I -B grade.py \
  --prepared /operator/prepared.json \
  --capture /operator/direct-capture.json \
  --output /operator/new-direct-score.json \
  --max-input-bytes SELECTED_AGGREGATE_INPUT_CAP \
  --max-packet-bytes SELECTED_OBSERVATION_CAP \
  --max-response-bytes SELECTED_RESPONSE_CAP \
  --max-total-response-bytes SELECTED_TOTAL_RESPONSE_CAP \
  --max-output-bytes SELECTED_OUTPUT_CAP
```

The input cap bounds both original input files and their canonical forms. The
output is created mode 0600, must not already exist, and is not written if its
byte ceiling is exceeded. The CLI prints only status, byte count and hash. The
library reports stable error codes; the CLI reports only a generic refusal to
avoid reflecting protected operands or paths.

## Limits and dependencies

Exact replay establishes artifact consistency. An operator could fabricate a
consistent capture; this does not authenticate a participant, delivery timing,
tool prohibition, isolation, calibration exposure, or model execution. It does
not qualify the original recording bytes, resolve the generating-source revision,
run a reference, or establish matched budgets with program conditions. Direct
versus F/I scientific comparisons still require a separately frozen comparison
and participant protocol. Every output remains `source_only_unqualified` with
scientific qualification, participant isolation and model execution explicitly
false. The historical 93-query route and canonical task admission are unchanged.

`grade.py` pins the existing delivery file. That loader pins the original-slot
validator, retained loader and scientific preparation/dependencies; the retained
loader additionally authenticates the probability-validation successor used for
metric arithmetic. Its existing trusted import and module-cache limitations
remain. Construction and grading should occur in a fresh, single-threaded,
trusted operator process.

`test_grade.py` uses only the existing tiny generated full-roster fixture. It
checks independent animal-weighted arithmetic, unequal session counts, paired
contrasts, missing/duplicate/future responses, tampering, original-slot omission,
undefined one-class metrics, protected output and byte ceilings. These controls
do not establish neural interpretation or scientific performance.
