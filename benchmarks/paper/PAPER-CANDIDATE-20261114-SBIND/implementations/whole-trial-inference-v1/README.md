# Complete-trial WFCI1 inference

This component connects the existing **prospective** whole-trial preparation and
label-free continuous-normalization stream to complete WFCI1 inference. It calls
the model separately for every full trial with reset requested, preserves every
source frame, and never supplies held behavior values or placeholder labels.
It is one construction component of the existing SBIND task, not another task
or a reproduction of the paper's unrecovered historical fold assignments.

The whole benchmark still requires WFCI1, WFCI2, all thirteen fUS sessions,
original preprocessing and masks, competent reference/control methods, and the
complete original endpoints. This continuous WFCI1 bridge does not implement
the binary WFCI2 or fUS interfaces, training/model selection, or final scoring.
The owner must preserve matched inputs and budgets between information arms;
official author code remains restricted to the author-code condition. This
component neither supplies nor enforces those independent access boundaries.

## Existing interfaces and the repaired seam

`predict_held_wfci1` reuses the sibling `whole-trial-preparation` module to admit
both complete assay censuses and all ten prospective folds. Its input stream is
exactly the validation or test JSONL produced by the sibling
`continuous-normalization` component. The complete fourteen-channel WFCI1
metadata determines output width. A training stream, held behavior member,
changed identity, wrong reset, incomplete field or extra record is refused.

Before a callback or output write, a complete first pass validates every frame
and the independently frozen stream byte count/SHA256. The second pass buffers
each entire trial, checks its bytes against the first pass, requests a fresh
model state, and requires one complete neural and behavioral prediction per
source frame. Unequal trial lengths and the last trial are retained. No
fixed-length batching, frame shift, missing-prediction filtering or implicit
brain mask is applied. Every output retains its trial, offset and source index;
the source-defined scoring support/masks remain an owner obligation.

The callback signature is
`infer_trial(fields, x_init=True, behavior_width=14)`. It returns exactly
`{"neural": full_field_predictions, "behavior": fourteen_channel_predictions}`.
The callback receives only neural inputs. It is trusted code, and the request
to reset does not independently prove that a callback resets state or uses only
permitted history. The API is not an adversarial execution boundary.

An optional `TorchSBINDPredictor(model, device=..., dtype=...)` bypasses the
trainer's dependency on a behavior-shaped input. It uses an existing trusted
model, evaluation mode and disabled gradients. It accepts only continuous
behavior and refuses multi-step configurations that would shorten the output.
Behavior outputs may have trailing singleton spatial dimensions; they are
removed only after exact channel/extent checks. Device and float32/float64
precision are explicit future protocol choices. No checkpoint is loaded here.
**This optional native bridge has not been executed against PyTorch or SBIND.**
It must pass an admitted native source/runtime check before authentic use.

The inspected pinned [author trainer](https://raw.githubusercontent.com/ShanechiLab/SBIND/c00e006dd298cb8c51d1543641fb3be77cc585ae/sbind/sbind_trainer.py)
reads behavior shape during prediction and requests a reset for its first
batch. The pinned [model](https://raw.githubusercontent.com/ShanechiLab/SBIND/c00e006dd298cb8c51d1543641fb3be77cc585ae/sbind/sbind.py)
accepts neural inputs and an initialization flag and returns both modalities.
These browser-inspected APIs explain the adapter seam; they are not authenticated
local source captures, historical caller recovery or proof of causal outputs.
No upstream implementation is copied into this package.

## Failure, storage and resource behavior

Callers supply frozen stream identity/extent, positive per-trial frame and
output-byte limits, the exact census/split/normalization/representation digests,
a seekable binary input and a separate trusted binary output. A line is capped
at1MiB. Those limits must cover the authentic full selected role; reducing them
does not authorize dropping trials. Complete neural fields are inspected twice,
and complete input/prediction trials can be resident together. Native peak
memory, throughput and the sufficient authentic resource envelope are unmeasured.

Short writes are completed; zero/invalid writes fail. A failure may leave a
partial sink and model state, and no success receipt is returned. The owner
must stage outputs, discard/quarantine failed artifacts, enforce durable
publication and prevent aliased backing files or source mutation. The final
receipt binds successful output bytes/counts and the full input identity; it
does not establish fsync, physical isolation, source authenticity, native
causality, historical reproduction or an improvement. No targets, private paths
or authentic inputs are distributed in this component.

## Generated checks and integration

Eight standard-library methods check complete generated248+412-trial metadata,
unequal selected trials, all frames/resets, held-label rejection, exact source
and output identity, malformed/omitted/repeated records, mutation between passes,
short model outputs, nonfinite outputs, and failed/short writes. The selected
generated role contains two unequal trials; it is a boundary fixture, not a
smaller authentic benchmark. No model, source arrays, torch import or scientific
metric is executed. The retained validation records include the initial stale
historical-dependency-pin refusal and the passing run with the current pin.

Use Python3.11 and the adjacent `whole-trial-preparation/trial_preparation.py`
selected by `DEPENDENCIES.json`. In a trusted checkout, run
`python3 -I -S -B test_trial_inference.py` through the existing shared test pool.
For private construction, `SBIND_TRIAL_PREPARATION` explicitly selects that
reviewed dependency directory; the test authenticates its exact source before
import. A future CI component enrollment must authenticate this package and the
current dependency before discovery. No central CI/registry file is changed by
this private package, and no benchmark readiness is promoted.
