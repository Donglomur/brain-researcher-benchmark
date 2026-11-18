# Full paired spinal workflow: fixed engineering control

This additive package connects the existing current-condition delivery to a
bounded complete campaign and a protected paired evaluator. It preserves the
original **44 neurons, 132-record census, 116 eligible recordings, 16 fixed
input-noise exclusions, and 88 isolated access-arm/fold contexts**. Historical
delivery, preparation, and metric source files remain unchanged.

The construction control emits exactly **1 Hz for every query bin**. It uses
only public configuration, binding and fold metadata, with no trained model,
training-array read or target access. Its result can validate transport and
collection; it cannot reproduce or improve the paper. Source tests use generated
data and mocked container lifecycles. No authentic campaign or scoring result is
claimed by this source package.

## One bounded complete campaign

`run.py` freezes the same single control source before either access arm sees
labelled material. The original delivery creates a fresh context for every
held-neuron fold, checks actual runtime/resource settings, removes the producer
before capture, closes its holder and volume, and retires the labelled view
before proceeding. Both arms receive identical paper/data bytes; arm B also
receives the original pinned author code. Sealing the control does not establish
the previous knowledge or information access of future AI authors.

The new plan declares a whole-campaign clock. For example, five candidate
seconds per context and 1,800 seconds total retain the original **425-second
per-context allowance**, including its cleanup reserve. Each next context may
start only when that full allowance and finalization still fit. The total cap
can therefore stop a slow campaign before all contexts finish. That is a failed
attempt; neither a partial panel nor a shorter per-context allowance counts as
completion. The original sum of selected fold allowances is reported separately
from observed elapsed time and the new aggregate ceiling.

The trusted worker inherits the parent's absolute monotonic deadline. A bounded
observer preserves stdout and stderr, reaps its owned host process group and
requires natural exit zero. Those host observations do not imply Docker resource
absence: all 88 original lifecycle records must also close. An external
supervisor must observe this outer command's final exit and preserve its own
capture before authentic workflow qualification.

`PLAN.template.json` shows the exact input fields. It is an example, not a
ready local admission. An operator must select actual existing input/runtime
paths, current external disk reservations and a reviewed budget, then freeze
the exact plan and `SOURCE.json` SHA256 values. The command is:

```text
python -I -B run.py --source-sha256 COMPLETION_SOURCE_SHA256 \
  --plan /operator/frozen-plan.json --plan-sha256 PLAN_SHA256
```

The host needs the existing Python/NumPy environment used by the original
delivery. The candidate is standard-library-only and uses the exact retained
image `sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`.
No image pull, package installation, alternate dataset, or host execution of
candidate code is provided.

The old campaign retains its 256 MiB retained-file, 2 GiB cumulative managed
write, 4 GiB managed-read and 60 GiB free-disk limits. The new outer sideband
requires a separate 1 MiB write/retention and 8 MiB source/metadata-read envelope.
These are logical planning limits, not measured physical I/O or a universal
host memory sandbox. The immutable source closure is authenticated before
labelled access and again before worker/parent success; the unchanged per-fold
source checks retain their original accounting. Caller-supplied `other_reserve_bytes`
must remain conservative for the whole attempt.

## Protected paired evaluation

`grade.py` requires the operator-frozen successful host receipt and all 88
closed lifecycle and retired-view records. It reconstructs the retired public
binding for every fold, decodes both full candidate bundles, and checks that all
232 recording vectors match the closed captures before reading electrical
target arrays or reference predictions. Only then does it call the unchanged
current-condition evaluator for both arms against the same independently frozen
reference bundle. Closed operator artifact custody is trusted; a malicious
filesystem administrator is outside this interface's protection.

The required references remain **OASIS, default/cortical CASCADE, glutamatergic
CASCADE and GABAergic CASCADE**, with raw fluorescence provided directly by the
bank as the fifth control. This package does not create those four missing
trained-reference arrays. There is no placeholder-reference fallback and no
scientific scoring admission merely because a transport receipt exists.

```text
python -I -B grade.py --attempt /operator/closed-attempt \
  --host-exit-sha256 HOST_EXIT_SHA256 --source-sha256 COMPLETION_SOURCE_SHA256 \
  --bank /operator/frozen-bank --references /operator/frozen-references \
  --reference-manifest-sha256 OPERATOR_REFERENCE_SHA256 \
  --output /operator/private/paired-comparison.json
```

`SOURCE.json` includes the transitive original metric kernel as well as the
delivery/evaluator closure. The current matched noise-7/30-Hz condition remains
distinct from historical Figure 4 and the complete paper contract. Source-era
realizations, alignment, cortical comparison, full condition panels, model
training provenance and scientific agreement/superiority criteria remain
unresolved. No native isolation, AI accuracy, reproduction, improvement or SOTA
result follows from generated controls.

Fatal host/daemon loss can leave container closure unknown. The original
lifecycle's in-memory creation acknowledgments are not a crash-recovery journal;
there is no generic daemon cleanup or automatic retry. A successfully closed
finite run may be accepted at its actual scope without claiming that broader
failure recovery or clean-machine image distribution has been solved.
