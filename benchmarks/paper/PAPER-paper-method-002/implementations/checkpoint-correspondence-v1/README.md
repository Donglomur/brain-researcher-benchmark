# Retinal checkpoint correspondence

This operator component audits whether a recorded validation winner corresponds
to a supplied parameter checkpoint. It closes a bookkeeping gap beside the
existing `retinal-heldout` prediction scorer. It does not select candidates using
test scores, read parameters or calcium data, run Jaxley, change the retinal
metric, or authenticate a published result.

The exact source observation and its limits are in `SOURCE.json`. In particular,
a best-test scalar and an epoch-named parameter file are different artifacts.
Their correspondence must be established. A periodic evaluation may occur between
saved epoch boundaries if the actual configuration permits it. That is a
conditional source-code possibility, not a claim that the published run did so.
The observed default uses `eval_every_nth_batch=100`; with 48 batches per epoch,
only epoch-end evaluations would occur. Neither these defaults nor the 48-batch
inference identifies the historical experiment.

## Interface

Call `audit.audit(document)` with an operator-held dictionary. `test_audit.py`
contains a complete invented example. No command-line file loader is supplied;
an integrating operator must enforce its own bounded, duplicate-key-rejecting
input parser, artifact custody and provenance.

The dictionary has exactly these fields:

- `schema`: `jaxley-retinal-checkpoint-correspondence-input/v1`.
- `source_commit`: the exact revision in `SOURCE.json`.
- `observation_manifest_sha256`: a digest of the independently qualified complete
  observation, split, mask and site identity. This component only validates its
  syntax and binds its value into the report; it does not issue its authenticity.
- `epochs`, `batches_per_epoch`, `evaluate_every_nth_batch`: actual run settings,
  positive integers. No defaults are substituted for missing historical settings.
- `events`: the complete chronological validation-event roster. Every event has
  `epoch`, zero-based `after_batch` or `"epoch_end"`,
  `validation_mean_pearson`, and `parameter_state_sha256`. The mean is a recorded
  source statistic, not recomputed from observations here. Undefined means and
  unrecorded parameter identity use `null` independently.
- `checkpoints`: supplied records with `epoch_boundary` and
  `parameter_state_sha256`. Boundary `n` is the state after `n` complete epochs;
  boundary zero is initialization. An incomplete inventory is reported, not
  silently completed. Repeated boundary identities are refused.

All parameter digests must use the same independently specified exact-byte
serialization. Equality of caller-provided strings is not authentication of
files. The checker reports same-step matches separately from identical digests
at other boundaries. It never opens a checkpoint or unpickles anything.

The event roster includes periodic evaluations and every epoch-end evaluation,
including both when they occur at the same optimizer step. It rejects missing,
extra or reordered events and contradictory recorded state identities at the
same step. Selection uses strict improvement from the source's initial minus-one
value, retaining the first maximum. It does not replace undefined sites with
zero, invent a winner from all-minus-one scores, accept test scores in the input,
or infer parameter identity from a high correlation.

The engineering input limit is 100,000 complete events; larger runs are refused
in full. The output always leaves `paper_win` null, historical and observation
authenticity unestablished, and checkpoint-byte verification false. A same-step
digest match establishes internal supplied-metadata correspondence only.

## Qualification still required

Source cache and raw-ROI/site correspondence, historical splits/configuration,
the original paper's control membership, admitted author replay, protected
candidate freeze, effect threshold and dependence-aware uncertainty remain open.
The current derived runtime deliberately selects an explicit produced epoch;
this checker does not relabel that state as the historical validation winner.
There is one biological cell, and no new independent biological evidence here.

`python3 -I -B test_audit.py` runs generated software controls. Local construction
uses the existing shared test pool. Integrators must enroll this new task-local
test command explicitly; this source package does not itself edit global CI or
the registry. No real recordings, fits or author/candidate results are included.
