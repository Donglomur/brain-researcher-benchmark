# Authentic optogenetic Figure 1H delivery

This component turns the complete pinned `optoData.mat` into paired candidate
packets and an independently checked operator reference, then freezes and grades
JSON or native MATLAB struct submissions. It covers all 3,304 trials from both
optogenetic mice and eight sessions. It adds no task ID and does not change the
canonical task or the earlier normalized evaluator.

The endpoint reconstructs the control and optogenetic source contact-time distributions
computed by the [pinned author Figure 1H function](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig1/plots/plotOptoHists.m).
It is not the earlier component's prospective equal-mouse mean-delay statistic.
Every trial is retained in the submitted selection audit; both groups pool all
sessions and mice exactly as the author plotting source does.

**The article's quantitative contact percentages remain unresolved.** Independent
calculation did not recover its contact-within-three-seconds percentages from
the unshifted native plotting values. The timer origin is unvalidated: the
Figure 1H function uses grabTimeC/1000 and labels zero as cue, whereas the pinned
[author event-analysis helper](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/loadEventTimes.m)
subtracts waterTime. This discrepancy cannot be
interpreted as a paper error before the physical timer origin is reconciled. The
article's stated total stimulation-trial count does match the raw stimulation
population; it is a different denominator from the selected histogram population.
No selection was adjusted to reproduce the text. This release therefore supports
source-release numerical reconstruction, while cue-relative timing and
article-text quantitative reproduction remain explicitly unresolved. It establishes neither a population
causal estimate nor whole-paper reproduction.

`TASK.md` defines the candidate contract and its source-derived conventions. Both
conditions receive identical native data, article, task, schema, attribution and
identity-only roster. Only the official-code condition receives the selected
plotting function, parent figure script and CC0 license. Shared conventions make
this a method-assisted reconstruction condition. The selected code is not a full
MATLAB plotting environment, and neither condition includes operator code or
reference outputs. Do not interpret this construction as a measured code-access
benefit or benchmark difficulty result.

## Operator commands

Run from this package directory. Supply absolute paths to existing authenticated
assets; this implementation performs no download, package installation or solver
execution. Preparation and MATLAB submission ingestion require NumPy/SciPy.
JSON admission, independent checking and scoring use the standard library.

```sh
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -B delivery.py prepare \
  --mat /absolute/source/optoData.mat \
  --paper /absolute/source/article.xml \
  --code-root /absolute/pinned-official-code \
  --output /absolute/private-preparation

python3 -B delivery.py freeze-reference \
  --draft /absolute/private-preparation/operator/draft-reference.json \
  --independent /absolute/independent-review/independent-reference.json \
  --output /absolute/private-frozen-reference

python3 -B delivery.py freeze-submission \
  --submission /absolute/attempt/submission.json \
  --packet /absolute/private-preparation/candidates/paper_and_data \
  --attempt candidate-001 --output /absolute/private-frozen-submission

python3 -B delivery.py grade \
  --reference-dir /absolute/private-frozen-reference \
  --submission-dir /absolute/private-frozen-submission \
  --output /absolute/private-grade.json
```

Distribute only the selected `candidates/<condition>` directory. Keep `operator`,
the frozen reference, independent verification, submissions and grade receipts
outside candidate inputs and public Git. The packet validator authenticates exact
condition-specific membership, input/paper/code pins, current task/schema bytes
and the complete identity roster; changing a self-authored manifest does not
allow substitute data or official code in the paper-and-data condition.

Preparation produces an unapproved draft. Reference freezing requires a separately
implemented `independent-opto-native-reference-v1` artifact with the full identity
roster, `trial_outputs` (same per-trial fields as the submission), group-specific
selected keys, excluded keys, bin edges and histograms. The verifier checks every
graded per-trial value and every histogram value, plus the immutable authentic
identity roster. This checks numerical agreement; the reviewer's independence is
an operator responsibility. A fabricated self-review is not independent evidence.

Submission freezing captures bytes before numerical parsing, including malformed
attempts. Subsequent body changes fail admission. Invalid grading writes an
`admissible: false` receipt and exits with status 2; receipt/output directories
cannot be overwritten. Do not delete failed attempts. JSON duplicate keys,
nonfinite values, missing/extra/duplicate trial identities, incorrect bin edges,
and in-range-only probability renormalization are rejected. Admitted outputs
receive continuous numerical diagnostics, not a scientific pass threshold.

Shared-host files and operator manifests are not a security boundary. This does
not sandbox authoring, freeze a solver's method before development execution, or
stop an actor with write access replacing an entire receipt tree. Prospective method freezing needs a task-compatible controller; the current
shared controller covers NEURAL-007/077 and does not yet support this task. The optional
SciPy MAT parser is for trusted development submissions: the compressed 32 MiB
file-size limit is not a decompressed-memory bound. A protected deployment must
supply a qualified resource-limited parser/container before hostile native MAT
inputs are accepted. The observed authentic preparation used under 96 MB RSS;
that measurement does not qualify adversarial parsing.

## Validation and remaining scope

```sh
python3 -I -S -B -m unittest discover -s tests -p test_contract.py -v
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  python3 -B -m unittest discover -s tests -p test_native.py -v
```

The 15 standard-library controls test semantic boundaries, strict admission,
independent comparison, authentic-reference exclusion and forged-packet failure.
Four optional SciPy controls test generated MATLAB structs and pin rejection.
These generated controls are software evidence only.

Separately, the exact authentic input was prepared and its full native reference
was independently recalculated without importing this implementation. All trial
conditions/selections/contact values and all histogram values agreed. Nine local
operator path controls exercised both packet conditions, full JSON/MAT ingestion,
a source-value perturbation, coverage failures, malformed submissions, post-freeze
mutation and identical paired inputs. Reference-as-input replay in these controls
is not a solver trial or qualified oracle. Sanitized identities and counts of
checks are in `validation.json`; raw data, target vectors and receipts remain
operator-only. No paid APIs, new packages, training or new solver trials were used.

Full neural encoding/decoding, detailed intervention trajectories, raw video
tracking, native MATLAB execution, protected evaluation, task difficulty and
whole-paper qualification remain outstanding. `scientifically_qualified` and
`full_contract_complete` stay false. Data are CC BY 4.0; official code is CC0;
the exact article and code versions are recorded in `source-pins.json`. Public
paper/data/code exposure remains relevant to future solver-study interpretation.
