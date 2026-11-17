# NEURAL-034: active-fold calcium and behavior viewer

This additive source component presents the complete existing seven-fold panel as
typed image interactions and collects all 140 probabilities in the original
grader's format. It does not change the task, original programme route, registration,
source data, or scientific qualification. No authentic packet has been rendered and
no model or provider has been run by this addition.

This is **viewer-mediated interpretation**, not direct/no-tools prediction. An
operator backend loads one authenticated fold and returns images through a small
action interface. A separate participant adapter, fresh participant context and
filesystem isolation still require qualification before an authentic study. Do not
give the participant this operator process, its filesystem, source pins, journal,
collector, or another fold. This component contains no model/provider adapter or
OS sandbox and does not claim one.

## Original panel and observations

Every fold has 120 labeled training windows from six mice and 20 query windows
from the held mouse. All seven folds and the original 140 query IDs are required.
The 120 demonstrations remain available in full; a viewer can choose which to
inspect. The active fold has no action that selects another fold. Other folds'
training labels reveal current query answers, so the provider conversation,
participant memory and writable state must start fresh separately for each fold.
The collector replays histories but cannot prove that external reset occurred.

Each image includes all 300 samples of all 12 selected author-processed calcium
traces and the permitted aligned binary behavior proxy. The original converter
interpolated the calcium onto sample centers at `0.05 + arange(300) * 0.1` seconds
within each 30-second window. This viewer adds no filtering, resampling,
normalization or zero-centering. Source fluorescence units are retained. Twelve
separate lanes share one gain, with positive values plotted upward; clipped lanes
are flagged. Increase `units_per_division` to display a larger amplitude range.
Behavior is drawn as a binary
step trace at the same sample centers. Its biological polarity remains unresolved.

The fixed 1400 by 820 RGB raster uses authenticated existing EEG canvas/font/line
primitives and task-local geometry. Standard-library zlib compresses pixels
losslessly. Rasterization is a representation change and does not preserve every
floating-point distinction in the original arrays. Numerical arrays, query
labels, fold identity and source paths are absent from participant responses.
Training views include their allowed context A/B label. Query IDs are original
opaque identities, not newly generated cases.

This is a historically exposed, selected seven-mouse processed-data panel, not the
paper's full 11-mouse archive or raw microscopy. Context/day order, ROI selection,
whole-session processing and behavior polarity remain limitations. Behavior alone
may predict context. Accuracy in this combined viewer cannot isolate calcium use
or establish causal memory. A programme versus viewer comparison shares query
identities but differs in representation and computational access; it does not
isolate a causal effect of tools.

## Operator invocation

Use an existing Python environment with NumPy. No installation or download is
performed. `SOURCE_BINDINGS.json` authenticates the existing input inventory,
public roster, original grader and reused raster. Each packet is checked against
the original exact bytes and SHA-256 from that inventory before decoding; schema,
dtype, finite values, complete extent and ordered IDs are then checked. Private
targets and references are never opened by this component.

For each fold separately, bridge only JSON stdin/stdout to a fresh participant.
The following is an operator command template; supply the actual pinned packet
and a fresh output directory outside the repository:

```sh
python -I -B benchmarks/neural/NEURAL-034/implementations/fold-viewer-v1/viewer.py serve \
  --fold 0 --packet /operator/fold-00/public.npz \
  --output /operator/results/fold-00 --max-actions 512
```

The illustrative 512-action allowance is a prospective viewer allocation, not a
qualified study budget or the original programme's CPU limit. Freeze a common
allowance between 41 and 4096 before any study. Every action including responding
and finishing counts. A failed action terminates that fold; failed or incomplete
folds cannot be silently replaced in the collector.

Send one JSON object per line, with exactly these fields:

| Action | Other fields | Result |
| --- | --- | --- |
| `training` | `index`: integer 0–119 | Image with permitted label |
| `query` | `index`: integer 0–19 | Image and original query ID |
| `inspect` | None | Current image |
| `gain` | `units_per_division`: finite number from 2^-20 to 2^60 | Current image with shared gain |
| `respond` | `query_id`, `probability`: finite number from 0 to 1 | Irrevocable context-B probability |
| `finish` | None | Closes only after all 20 answers |

Every response requires a previously displayed current query. Images are returned
as PNG base64 plus explicit display metadata, never signal arrays. The source-pinned
manifest, hash-chained successful actions and completion receipt stay operator-only.
Failures retain bounded last-request bytes (including EOF/truncation status) and
cannot be collected. These records are replay checks, not proof of provider honesty,
independent participant state, authenticity of model authorship, or OS confinement.

After all seven independently closed sessions, collect with arguments in fold
order 00 through 06:

```sh
python -I -B benchmarks/neural/NEURAL-034/implementations/fold-viewer-v1/viewer.py collect \
  --packets /operator/fold-00/public.npz /operator/fold-01/public.npz /operator/fold-02/public.npz /operator/fold-03/public.npz /operator/fold-04/public.npz /operator/fold-05/public.npz /operator/fold-06/public.npz \
  --sessions /operator/results/fold-00 /operator/results/fold-01 /operator/results/fold-02 /operator/results/fold-03 /operator/results/fold-04 /operator/results/fold-05 /operator/results/fold-06 \
  --output /operator/results/complete
```

Collection reauthenticates every packet and replays every image and answer against
the same source and recorded Python/NumPy/zlib versions. Version recording is not
full binary attestation. Missing, reordered, swapped, modified or failed sessions
are rejected. Successful collection writes `probabilities.json` with exactly the
original 140 `(fold, query_id, probability)` rows and a `collection.json` receipt.
It does not read labels or grade anything. Reuse the unchanged registered-runtime
grader through its existing operator route to report seven mouse-level values,
equal-mouse balanced accuracy and log loss, and the six original reference
comparisons. That later grading and authentic preparation are not performed here.

## Generated verification

```sh
python -I -B benchmarks/neural/NEURAL-034/implementations/fold-viewer-v1/test_viewer.py
```

Controls use generated arrays and answers plus the existing public ID roster.
They verify packet/schema rejection, all-channel image effects, lossless PNG
encoding, typed projection, complete seven-fold replay/collection, failure records,
and output compatibility with the unchanged scorer using wholly generated labels.
They are software controls, not neural-data performance or native delivery results.
