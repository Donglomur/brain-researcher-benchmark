# Complete causal forecasting packet projection

`packet.py` supplies the missing operator-side projection from an authenticated,
complete count panel to separate participant and target packets. It preserves the
current NEURAL-018 endpoint: 1,721 training trials, 574 development query trials,
137 observed units before +450 ms, and all 182 units for 40 future 5-ms bins.
It performs no fitting, smoothing, rebinning, source acquisition or candidate run.

The source is the pinned organizer's unsmoothed, movement-aligned MC_Maze counts.
Its `make_train_input_tensors(..., include_forward_pred=True)` returns separate
past and forward held-in/held-out arrays; `make_eval_input_tensors` returns query
held-in past counts, and operator-only `make_eval_target_tensors` returns the
query held-out past and forward counts. Upstream preparation must preserve
the ordered source trial and unit identities when combining those fields.
The integer `trial_type` and `trial_version` context is explicitly allowed by
the local task. This is the task's condition-assisted interface, not a claim
of byte identity with the official challenge input interface.

The operator passes exactly these arrays to `project(source)`:

| Source field | Required meaning |
|---|---|
| `counts` | `(2295,180,182)` complete unsmoothed counts; bins `[-250,650)` ms, with separately generated past and future windows concatenated at +450 ms |
| `trial_ids` | Unique bounded Unicode identities for the count trial axis |
| `split` | Exactly 1,721 `train` and 574 `val` entries, source-assigned |
| `unit_ids` | Unique bounded Unicode identities for the count unit axis |
| `unit_is_heldout` | Boolean source population membership, 137 false / 45 true |
| `bin_left_edges_ms` | Exact `-250,-245,...,645` grid |
| `trial_type`, `trial_version` | Original integer condition context, one entry per source trial |

Production geometry is fixed; there is no smaller-panel mode. Trial and unit
axes may be permuted with their identities and membership arrays. Output order
is source order within split and within unit group, with held-in units followed
by held-out units. Missing, fractional, negative and nonfinite counts are
rejected; no cells or trials are dropped. The target mask is all true.

`project` returns `(public, targets)`. The public packet contains training past
counts for both populations, training future counts, query held-in past counts,
the permitted condition context, exact clocks, units and identities. It contains
neither query future counts nor held-out query past counts. Every output array
owns storage independent of source and the other packet. The public fingerprint
hashes only the complete permitted observations and metadata; forbidden query
values cannot affect it. This version's fingerprint is new and must not be
substituted into historical receipts.

`write_packets(source, public_dir, operator_dir)` requires two existing empty,
disjoint directories and exclusively creates `public_input.npz` and
`operator_future_targets.npz`, respectively, with mode 0600. It never overwrites
an earlier preparation. Its returned receipt includes both file hashes and is
operator-only. A failed write can leave an incomplete operator preparation;
preserve that failure and use new directories. Do not publish a packet unless
the call returns successfully and an independent reader verifies its receipt.
The caller controls filesystem isolation; this utility is not an adversarial
filesystem sandbox.

`scorer_public(public)` produces the public identity dictionary accepted by
`../registered-runtime/scoring-v2/scoring_core.py`. The targets have that
scorer's exact private schema. This component does not replace the legacy
container wrapper's fixed asset pins or register an admitted runtime. Before a
new authentic packet can be scored, its own authenticated source and target
receipts must be reviewed and bound by an operator wrapper.

The source preparation boundary remains explicit: integer values and declared
clock/identity arrays cannot prove that upstream processing was unsmoothed,
causal, complete, or correctly source-aligned. The organizer loader, original
source asset, split, unit flags and joined tensors still need an independently
verified native preparation under a frozen protocol. In particular, this
projector does not load raw NWB or retrospectively infer a movement onset. It
only proves the declared projection excludes forbidden cells. No new authentic
data preparation, model result, direct interpretation, viewer evaluation,
programme lifecycle qualification, or benchmark admission is established here.

`test_packet.py` uses generated full-geometry arrays. It tests the +445/+450 ms
boundary, interleaved trial and unit identities, exact group ordering,
noninterference from forbidden values, rejection of malformed panels, detached
storage, serialized inventories, disjoint output roots and the existing
scorer's public submission validator. It must run through the shared bounded
test pool; it is not a scientific data or model run.

Source conventions are pinned in `SOURCE_FREEZE.json`. The original historical
scorer and task contract remain unchanged. The source remains one exposed
Jenkins session; temporal forecasting does not establish interventional causality
or biological generalization.
