# Paired frozen programmes for the selected MEG paper endpoint

This source connects the accepted full-cohort window preparation to two isolated
programme conditions and the original fold scorer. It has generated control
evidence, **no authentic execution through this route and no qualified paper
reproduction or improvement result**. It does not change the task registry.

The task is the selected Figure 3 CS↔PFC face-versus-object result from
*A data-driven approach to identifying and evaluating connectivity-based neural
correlates of conscious visual perception*. All 94 original participants remain
in scope. The 376 category-averaged windows preserve four ROIs and all 1,000
original millisecond samples. Exactly 188 face/object rows receive held-fold
predictions in each information condition. These are known-category averages,
not unknown-category single trials or consciousness labels.

## Delivery and scientific compatibility

`prepare.py` first captures both complete submitted programmes and the fixed
wrapper. It then verifies the previously accepted preparation binding, reads
the 94 prepared arrays, and creates one anonymous `[376,4,1000]` float64 bank.
No neural value is filtered, resampled, standardized or otherwise transformed.
Private source/category identities remain outside participant mounts. Opaque
row order avoids exposing the category axis of the original prepared arrays.

Every phase receives the same complete bank, its exact held query IDs and the
other participants' face/object labels. The ten folds must come from one
externally fixed complete participant map. The supplied map is never labeled
as authenticated historical folds merely because it uses seed 127. A has
paper+data access; B additionally receives seven exact official code/config
files from author revision `cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0`.

Both programmes freeze before **any** outer-fold labeled view is exposed.
Across ten folds those views reveal every target label, so an interactive
author must not inspect their union and then resubmit. The operator must
separately document the assistance actually available while each programme was
authored. Runtime mount restrictions alone cannot establish that history or
eliminate memorization of publicly released data. This route measures a frozen
prediction programme, not an interactive agent or native neural understanding.

`run.py` first runs the protected-delivery verifier as a **mandatory admission
gate**, before creating participant transport, phases or exposures. It
authenticates the verifier source, performs a fresh complete audit, and binds
the returned and retained report to this invocation's externally selected
paper, source manifest, prepared packet, programmes and contexts. A prior
standalone report cannot skip this gate. Failed admission constructs no
participant transport.

After admission, `run.py` uses one concrete owned Provider for all 20 fresh phases,
with an unchanged campaign deadline and cumulative transport ceilings. A and
B receive byte-identical context for each fold. No writable state or feedback
passes between phases. The Provider retires the producer before capture and
independently checks container, holder, volume and owned CLI-process closure.
Its selected CLI ownership implementation requires an operator on Linux;
pointing the Mac at a Docker daemon is not sufficient.

The trusted pre-delivery audit reads the private source join to check all ten
contexts; no participant is present or receives that ledger. The separate
scoring read occurs only after all 20 responses pass public validation and
transport closure. Audit and scoring reads are recorded separately.
Probabilities mean P(object); exactly 0.5 predicts face. The unchanged original
scorer reports unweighted mean-fold accuracy and population fold SD. Its pooled
and participant accuracy summaries remain descriptive. This route does not yet
deliver the original classifier's separate AUC companions.

The interface preserves the original complete four-category QC/imputation and
held-batch min/max exposure. Source reproduction still means sample-SD ROI
standardization, linear detrending, the native source-ordered DBA calculations,
maximum squared CS↔PFC barycenter and the specified classifier. All 376 claimed
source feature values must agree across folds in a reproduction campaign.
Wrong or all-null but consistent claims are not numerical reproduction.
Improvement programmes may omit those source feature claims and use a new
method on the same selected observations and endpoint.

No cache of candidate-derived global features crosses phases. Recomputing the
original six-pair feature extraction in every phase has a complete
**45,120-DBA-call schedule**, versus 2,256 for one extraction. Early solver
failures can truncate calls; neither number is a measured run count. A separately frozen,
label-independent preparation/cache stage would require its own design and
review. `fixed_control.py` does no extraction or fitting and predicts 0.5; it
is an engineering control, not a competent scientific reference.

## Finite protocol and commands

[`PROTOCOL.json`](PROTOCOL.json) specifies a proposed full-support engineering
control, its finite ceilings and outstanding external bindings. It is
**not an execution admission**. No image, original-fold identity, paper body,
supervisor or candidate budget is fabricated. Scientific programmes need a
separate finite budget that covers their complete 20-phase work.

The future preparation command is:

```sh
python -I -B prepare.py \
  --prepared /private/accepted94 \
  --folds /private/selected-folds.json \
  --programme-a /submissions/A.py --programme-b /submissions/B.py \
  --paper /sources/paper.pdf --paper-pin-json /private/paper-pin.json \
  --author-source /sources/author-cab648b \
  --output /private/new-meg-prepared
```

The fold document has exactly `folds` (94 participant IDs mapped to integers
0–9, every fold present) and `evidence` (a bounded provenance string). The paper
pin has exactly `bytes` and `sha256`. All source inputs and destination paths
must be fixed by the trusted study operator before preparation. Keep failed
partial outputs; use a newly admitted directory for any later attempt.

Externally pin `PREPARED.json`, the independently selected paper and the paired
source manifest; qualify the operator boundary before execution. Runtime
declarations now require `paper_pin`, `paired_source_manifest`,
`delivery_read_bytes`, `delivery_write_bytes` and `delivery_seconds`. The
original campaign allowance covers the audit plus all twenty phases; the audit
cannot extend that deadline. On the selected Linux operator, under the
separately reviewed supervisor:

```sh
python -I -B run.py \
  --prepared-root /private/new-meg-prepared \
  --prepared-pin-json /private/prepared-pin.json \
  --runtime /private/selected-runtime.json \
  --runtime-sha256 EXACT_RUNTIME_SHA256 \
  --output-root /private/new-meg-campaign
```

The persisted `BATCH.json` is deliberately **provisional**: final publication
itself can cross the deadline. Acceptance additionally requires independent
successful process-exit and original-deadline observation, complete pinned
receipts, final artifact pins, and no unresolved owned resources. Absence of
`FAILURE.json` is not success or cleanup evidence. No failed phase is retried
automatically. A separate recovery action must retain the same owned identity
and receive its own finite authorization.

## Evidence and remaining qualification

The original accepted binding is 69,418 bytes, SHA256
`76a1d48c5bbb4f4126c9c6b4692d4a38b6cd97fa0fde3496c48281ffe3ef1e94`.
Its authentic 94-array preparation is inherited from
[`AUTHENTIC_PREPARATION.v1.json`](../original-feature-producer-v1/AUTHENTIC_PREPARATION.v1.json);
none of those arrays was read for this source construction. Original source
semantics and citations are retained in
[`SOURCE.md`](../original-feature-producer-v1/SOURCE.md). Statements about local
native availability in earlier historical receipts describe those cutoffs;
later native generated controls do not authenticate historical paper parity.

The additive Provider was copied unchanged from commit
`356fc3cde325ae91920c6fe157da707116198b98`, path
`benchmarks/neural/NEURAL-007/implementations/whole-night-programme/provider-public-mode-v2/vendor_transport/`.
Its exact vendor manifest is enforced by the adapter. Prior Sleep engineering
receipts establish neither MEG execution nor arbitrary-program qualification.

Generated checks cover exact cohort/row geometry, opaque bank correspondence,
assistance mounts, frozen programmes, original scorer joins, late invalid
outputs, closure, source pins, one-instance budgets and deadline publication.
They establish software behavior on generated data only. Test details and
cutoff hashes are recorded in `VALIDATION.json`, `ADMISSION_VALIDATION.json` and
`SOURCE_MANIFEST.json`. The first validation file preserves the earlier
pre-admission cutoff; the admission file records the changed runner controls.
Coordinator logical grants, Provider counters and adapter reads have different
scopes. They do not measure physical disk I/O, total CPU or simultaneous
process-tree memory. Preparation/bootstrap/library I/O also needs the external
whole-operation supervisor in a future run.

Historical row order/folds, release-to-publication and corrected-supplement
joins, authentic full-precision source features/probabilities, numerical
agreement criteria, a competent matched baseline, and participant-aware,
selection-aware improvement rules remain unresolved. A printed 64.3% ± 9.4
percentage-point fold SD is not a success threshold or uncertainty interval.
The scorer consequently leaves paper reproduction/improvement success null
and scientific qualification false. A new fold map, above-paper decimal or
program consistency cannot make those fields true.
