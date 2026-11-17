# Sequential processed-summary observations

This component delivers the original NEURAL-005 next-round choice task as
typed numeric observations, then collects complete probability submissions for
the existing scorer. It fills the missing observation-and-answer route without
changing the original programme controller, grader, cases or registration.
It does not execute a participant, call a model, provide a viewer or enforce
an external participant's tool access. Authentic delivery and model performance
remain untested.

The complete panel has **3,254 supervised training rows from 26 people** and
**816 development queries from seven other people**. Every development case
appears in each of the history, prestimulus and all-ERP conditions: **21 complete
person/view sessions and 2,448 committed probabilities**. These are three views
of one existing assignment, not three new benchmarks. No subset option exists.

The unchanged feature implementation supplies 50 history features, history plus
three prestimulus features (53), and history plus seven ERP features (57).
Prestimulus columns are selected by name: they are not the first 53 columns of
the all-ERP matrix. Common eligibility requires all seven current ERP values
before any view is masked. Each session supplies all training examples in its
corresponding view, including their supervised outcomes and original training
folds. The operator must fix the same training-only method and tuning policy
across views; matching declaration bytes does not prove that a participant
followed that policy.

## Observation timing and answer collection

The forecast is made after the current trial completes. The observation is a
source-preserved feature vector computed from its completed within-episode
prefix. A single current query is emitted at a time. Its finite probability
must be flushed and fsynced to the operator journal before the next query can
be emitted. Nonces bind answers to the pending case, person, view and session.
Responses cannot revise earlier predictions. An invalid answer or failed
durable commit ends that broker session.

Later lawful prefixes can reveal the earlier prediction's behavioral outcome,
including through the next completed choice. This delayed behavioral feedback
is part of the original sequential contract. Private grades, protected target
fields, source row indices and future-prefix batches are never participant
messages. A complete development-prefix file must never be given to a
participant. Each person/view starts a fresh broker state; a separately reviewed
participant transport must also establish a fresh external model/process state.
The broker alone cannot establish that reset, tool restrictions, provider
context capacity, training-policy compliance or complete participant isolation.

The broker is an **operator-only process**. Its exact pinned development packet
contains protected outcomes, which the operator decodes to project permitted
observations. Targets and source row locators are discarded from the query
representation. Neither the Study object, its source files, its complete query
list nor its operator journal should be passed to a participant. This is a
projection boundary, not an operating-system sandbox against host access.

The collector requires all 21 session directories, the same method declaration,
unique session identities and complete ordered journals. It independently
reconstructs each allowed observation from the original inputs, verifies the
observation and response hash chain, and captures the validated completion
bytes once. Missing sessions, changed observations, changed values, wrong
identities or incomplete persons refuse collection. All sessions must validate
before any collection output is published.

## Operator invocation after separate runtime authorization

`SOURCE.json` pins the new runtime source, unchanged feature implementation,
original case roster, source pins and scorer dependencies. Dependencies execute
the captured verified source bytes, bypassing cached bytecode. The operator must
retain the reviewed manifest digest and a stable trusted checkout; this source
manifest is not a self-authenticating approval or a hostile-host loader sandbox.

Inputs are the already provisioned `train.json` (1,303,752 bytes) and
`development_private.json` (890,937 bytes), with exact identities in
`../pinned-source-preparation-v1/SOURCE_PINS.json`. The component performs no
download or preparation. It authenticates both files and the fixed public case
roster before opening a session.

Create one method JSON document with exactly `schema_version: 1`, `method_id`,
`description`, `training_policy`, and `limitations`; the latter four are
nonempty strings, each at most 4,096 characters. Freeze the same file before
opening any of the 21 sessions. Session directories are named `<view>-<person>`
under one private existing session root. For each exact person/view pair:

```sh
python -I -B benchmarks/neural/NEURAL-005/implementations/sequential-observation-v1/broker.py \
  --train /operator/train.json --development-private /operator/development_private.json \
  --method /operator/method.json --participant "$PARTICIPANT" --view "$VIEW" \
  --output "/operator/sessions/$VIEW-$PARTICIPANT"
```

The first JSON line on stdout carries the complete permitted training view.
Subsequent lines contain one current numeric observation. The participant
transport responds through stdin with one newline-terminated JSON object with
exactly `session_id`, `nonce`, `participant`, `view`, `case_id`, and `probability`.
The first five values must match the current observation; probability is a
finite JSON number in [0,1], not a Boolean. A response is capped at 4,096 bytes.
The last output line acknowledges software completion, without a grade.
Keep operator stderr and files outside the participant channel. These commands
require a separately frozen participant transport, budget and isolation review;
they are not an executable model study by themselves.

After all 21 sessions close:

```sh
python -I -B benchmarks/neural/NEURAL-005/implementations/sequential-observation-v1/collect.py \
  --train /operator/train.json --development-private /operator/development_private.json \
  --sessions /operator/sessions --output /operator/fresh-collection
```

The output contains `history.probabilities.json`,
`prestimulus.probabilities.json`, `all_erp.probabilities.json`, and
`COLLECTION.json`. Each probability file retains the original complete
816-case submission schema. The original registered-runtime scorer can score
each file after separate operator/runtime admission; its private assets and
host launcher are unchanged. The collection itself does not call that scorer
or supply an admitted score report to `predictive-contribution`.

Retain METHOD, START, commits, probabilities and COMPLETE for every session,
then all three submissions and COLLECTION. Files use exclusive creation.
Failure or interruption may leave a partial directory without COMPLETE or
COLLECTION; preserve it rather than overwriting, appending, retrying or calling
it a finished protocol. Directory/hash evidence assumes trusted operator
custody. No provider or whole-study time/resource grant is supplied here.

## Scientific scope

These values are **processed offline ERP and behavioral summaries**, not raw
EEG waveforms. The author tables were joined by row position; independent
biological ERP-epoch alignment and causal online availability remain unresolved.
Next-round prediction is an extension of the paper's same-row endpoint.
Seven historically exposed development people are not a new confirmation cohort.

Preserve absolute equal-person losses for all three views and the mandatory
training-participant-macro prior in an eventually admitted study. The existing
primary ranking remains all-ERP log loss, lower is better. Report signed
history/prestimulus/all-ERP differences, including negative values; no positive
gap reward, SOTA threshold, causal effect or intrinsic neural-information claim
follows from this software. The unchanged predictive-contribution contract
continues to govern any later descriptive report. All canonical scientific and
submission qualification flags remain unchanged.

## Generated verification

```sh
python -I -B benchmarks/neural/NEURAL-005/implementations/sequential-observation-v1/test_broker.py
```

Twelve generated controls cover all 21 complete sessions and 2,448 answers,
complete training and feature views, seven-ERP eligibility before masking,
durable ordering, future-answer noninterference and later lawful feedback,
invalid answers, verified-source execution, observation tampering despite a
resealed hash chain, missing support, original scalar metric compatibility,
and the real broker CLI for one complete generated person. They do not read
authentic numerical inputs or targets, run a participant/model, invoke a native
runtime or establish scientific performance.
