# Complete numeric packets for frozen neonatal EEG programs

The existing raster participant wire supplies waveform pages. This additive
route delivers the already-defined **complete numeric causal packet** to one
hash-frozen local program in a fresh process for every original case. It closes
a participant-interface gap without changing the source cohort, source admission,
packet representation, folds, labels, quality flags, or score.

Every native sample of all 18 bipolar channels in the exact causal 30-second
window is supplied, together with original units, rational relative sample time,
and the original 30 quality flags. The program returns one probability for the
three-expert vote fraction in [29,30). No labels, infant identity, absolute offset,
source filenames or complete case roster are sent. The strict existing Session
validator checks an owned packet snapshot, exact fields and protected input hash
before any child starts or packet bytes are serialized.

This is a `frozen_numeric_program` condition. It does not assert that numeric
arrays and gain-controlled PNG pages provide equivalent information to a model.
It is not a direct-model provider adapter or an interactive analysis-tool API.
Any direct/program comparison must select explicit compatible observations,
train-only artifacts and budgets, and separately account for program authorship.

## Operator use

Use the existing `raster-run-entrypoint-v1/run.py prepare` route for complete
source preparation, keeping the resulting Reference and case key private. This
new implementation neither downloads inputs nor constructs a reduced corpus.
The selected source route requires all 79 infants and corrected expert streams.

The participant specification has exactly `argv`, `artifacts`, `limits`, and
`max_document_bytes`, as in the existing frozen-run interface. Every artifact has
an absolute `path` and `sha256`; bind the executable, program, runtime artifacts,
and immutable train-only inputs. `argv` contains exactly one
`{task_instructions}` placeholder, replaced by this package's PARTICIPANT.md.
Read that file for the single-packet/single-answer wire. Paths and artifact hashes
are operator metadata, never automatically sent through the participant wire.

```sh
python3 -B benchmarks/neural/NEURAL-EXP-005/implementations/numeric-program-v1/run.py freeze \
  --reference PRIVATE_REFERENCE --case-key PRIVATE_KEY --read-limit 1073741824 \
  --participant-spec PRIVATE_SPEC --output NEW_PRIVATE_PLAN

python3 -B benchmarks/neural/NEURAL-EXP-005/implementations/numeric-program-v1/run.py collect \
  --reference PRIVATE_REFERENCE --case-key PRIVATE_KEY --read-limit 1073741824 \
  --plan PRIVATE_PLAN --plan-sha256 PROTECTED_CANONICAL_PLAN_DIGEST \
  --source-root ADMITTED_SOURCE_ROOT --scratch-root PRIVATE_SCRATCH --output NEW_PRIVATE_BUNDLE

python3 -B benchmarks/neural/NEURAL-EXP-005/implementations/numeric-program-v1/run.py score \
  --reference PRIVATE_REFERENCE --case-key PRIVATE_KEY --read-limit 1073741824 \
  --plan PRIVATE_PLAN --plan-sha256 PROTECTED_CANONICAL_PLAN_DIGEST \
  --collection PRIVATE_BUNDLE/collection.json --completion PRIVATE_BUNDLE/COMPLETED.json \
  --completion-sha256 PROTECTED_CANONICAL_COMPLETION_DIGEST --output NEW_PRIVATE_SCORE
```

Placeholder paths/limits above are illustrative, not an authorized run or resource
profile. Digests are `digest(document)` canonical JSON digests, not hashes of
newline-terminated JSON files. Freeze the plan before held observations and
protect the completion digest before scoring. The operator supplies and qualifies
source custody, artifact immutability, prospective fitting, process restrictions
and protected commitments; the source code cannot establish that chronology.

`freeze_plan`, `collect`, and `score` also expose the same steps as Python APIs.
`collect` accepts the lazy original `shared.packets(reference, read_samples)`
stream. The CLI obtains its reader from the unchanged SourceCorpus. Complete
support stays all original primary timestamps, never one convenient window.

## Shared validation and distinct identities

The existing pinned entrypoint loads the unchanged source adapter, causal packet
protocol, strict Session/collector, process lifecycle helpers, and separate
evaluator. The Session is reused only for exact packet admission and its single
bound answer. Numeric collection requests no raster page. The shared collector
preserves the exact full schedule; the new producer exports distinct numeric
plan, collection, completion and failure schemas and mode values.

Scoring first admits the protected numeric envelope. It then makes a local copy
with the shared collector's schema/mode solely to reuse its exact full-row
validator. That normalized copy is never returned as raster evidence. Numeric
and raster collections cannot be interchanged at this entrypoint, and the
unchanged infant-macro soft-vote Brier evaluator receives the same bound rows.

An omitted, extra, repeated, reordered or altered case withholds complete output.
Artifact hashes are checked before collection, before every case, and after the
last case. Missing answers, wrong bindings, malformed/nonfinite probabilities,
trailing stdout, nonzero exit, byte/deadline violations or an unqualified cleanup
prevent that case from committing. A child receives one packet and one answer
receipt; it gets no correctness feedback or retry.

The host creates an empty private working directory and a new process/session
for each case, uses the existing fixed environment, and closes extra descriptors.
Cleanup is restricted to the owned child/session and is required before commit.
Failure receipts retain completed-case resource totals and any failed case's
lifecycle evidence. These are observed wall time and wire/stdout byte totals,
not CPU, memory, model-token, fitting or authorship cost measurements. Memory and
whole-authentic-cohort resource admission remain unqualified.

## Generated controls and limits

```sh
python3 -I -S -B benchmarks/neural/NEURAL-EXP-005/implementations/numeric-program-v1/test_run.py
```

The initial seven controls passed, including one actual 80-process collection
on the existing invented 79-infant fixture. Every generated child read all 30
samples and all 18 channels, checked the complete numerical pattern and returned
0.25; the unchanged full-support scorer returned 1/144 Brier. Six additional
child checks exercised a successful packet commitment and wrong binding,
nonfinite output, forbidden interactive action, trailing stdout and nonzero
exit. One child exercised a too-small observation budget. Maximum concurrency
was one child plus its orchestrator. These are no neural performance results.

Additional controls cover artifact drift and the real collect CLI's source-reader
wiring and failed persistence. Their explicitly labelled metadata executor
avoids another 80-case process replay. Source admission is stubbed there; no
authentic EDF, annotation, private dataset or model is opened. Test scratch and a
bounded receipt can be placed with `HELSINKI_NUMERIC_SCRATCH_ROOT` and
`HELSINKI_NUMERIC_PROOF_PATH`.

Fresh process creation is not filesystem, network, provider or hostile-process
containment. Programs can access host resources unless the operator independently
enforces those boundaries. Authentic all-source calibration/alignment, quality
detector validation, competent train-only references, matched control arms,
model/provider identity and complete protected deployment remain external gates.
Public labels still prevent an unseen-pretraining claim from local held-infant
folds alone. No readiness/access status, task count, clinical validity, scientific
qualification, superiority claim or submission readiness is promoted.
