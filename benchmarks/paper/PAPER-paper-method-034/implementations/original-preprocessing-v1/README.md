# MARBLE original views, released preprocessing and result support

This component connects the exact released data representation to explicit
preprocessing and original-row bindings. It preserves the original Figure5d
endpoint in the sibling `figure5d-endpoint-v1` component: rat1, 32-dimensional
embeddings, 36 uniform cosine neighbors, and mean absolute position error in
metres over **all 2,000 query observations**. That scorer is unchanged.

The released MARBLE decoding recipe produces **7,999 training and 1,999 query
anchors**. This component reports that result and refuses its admission to the
2,000-query endpoint. It does not pad a final vector, shift the split, drop the
paper's last observation, or replace the task with the previous four-rat
clean/half-neuron extension. It creates no new benchmark ID or paper-win rule.

## Source recipes remain distinct

| Route | Preprocessing and exposure | Output support |
| --- | --- | --- |
| `released-decoding-pca20-segmented-v1` | Achilles split at raw row8,000; smooth each segment separately; fit PCA20 on training rates and apply the same PCA to query; forward difference each segment | Training anchors0–7,998; query anchors8,000–9,998. Rows7,999 and9,999 are derivative partners, not available terminal anchors. |
| `released-consistency-pca10-whole-v1` | Each of four complete recordings; full-recording PCA10, then forward differences | Each rat has N−1 anchors. This is the separate Figure5e population. |
| `paper-described-pca5-physical10ms-unresolved` | Paper describes physical10ms Gaussian smoothing and PCA5 fitted across each animal's data. Spike timing, kernel boundaries, derivative boundary and original support are unresolved. | Explicitly unavailable. No alternate 2,000-row recipe is invented. |

Primary sources are [the article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11903309/)
and [the pinned author revision](https://github.com/Dynamics-of-Neural-Systems-Lab/MARBLE/tree/09491ec077bf153b7dece8518cc65ddaa20eb26d).
That revision postdates publication and is not a verified paper-production
revision. Its four hippocampus notebooks contain no saved execution outputs.
`SOURCE.json` pins the actual inspected files and identifies remaining source
questions separately from executable released-code behavior.

## Exact source views

`dependencies/intake.py` is the unchanged, byte-pinned restricted data-only
decoder already used for the released 22,055,089-byte `rat_data.pkl`. It accepts
only the recorded CPU float32 storage/tensor representation after the exact
whole-file SHA256 passes. No generic pickle loader, Torch import or checkpoint
deserialization is introduced.

`inputs.py` independently validates all eight original tensor layouts and uses
their real strides and storage offsets. Achilles is noncontiguous; Cicero and
Gatsby begin at nonzero storage offsets. A flat reshape is incorrect. Neural
views retain all finite float32 values, including any fractional or negative
magnitudes; primary evidence does not justify an integer-count restriction.

```sh
python -B inputs.py --source-pickle /operator/original/rat_data.pkl \
  --output-root /operator/workspace/original-views
```

The new private output root contains readonly public neural arrays and separate
private three-column behavior arrays: position, right-direction indicator and
left-direction indicator. All four source recordings are retained. The original
view row identity is `rat_data:SOURCE_SHA256:RAT:row:INDEX`; array shape, dtype,
payload hash and original storage mapping accompany each view. Row indices and
25ms bin width are known; absolute recording timestamps and bin phase are not.

The supported CLI obtains authenticated views through `read_release`. Its
in-process wrapper tracks value changes for the trusted operator; an importable
Python object is not an independent authentication or security boundary. The explicit private
`_generated=True` test boundary labels generated exports as such. Numeric pins
are not historical scientific attestation, and file separation is not a process
sandbox. The source labels were already public; this does not create an
unexposed holdout or a paired-access agent episode.

The existing prepared cache can also be reused without another array export.
`cache.py` inventories exactly four complete label files and eight complete clean
neural segments. It ignores the old half-neuron extension. Header inspection
checks whole-file hashes, exact shapes, little-endian float32 C-order storage and
file extent. The cache manifest is a declaration, not source authentication.

```sh
python -B cache.py --cache-root /operator/existing/marble \
  --output-json /operator/workspace/cache-inventory.json
```

Adding `--source-pickle /operator/original/rat_data.pkl` performs a complete,
bitwise comparison against all eight original storage views and emits a compact
source-binding receipt. It preserves every original source row and writes no new
numeric arrays. Existing file modes are recorded, not changed; private role
labels do not establish access isolation. Neither operation smooths signals,
fits PCA, runs a model or changes the paper endpoint. Original-source comparison
requires an admitted execution; header inspection alone does not establish it.

An admitted one-time comparison subsequently verified all 12 existing files
against the exact original pickle: all eight source views, every source row and
every float32 storage bit matched. `ORIGINAL_CACHE_BINDING.json` preserves that
receipt. The comparison reused 11,343,244 bytes of cached arrays and created no
new numeric files. Its success establishes original input equality, while the
historical preprocessing, checkpoint and 2,000-query support questions remain.

## Faithful released preprocessing

`preprocess.py` accepts time×neuron arrays and performs the original helper's
channel iteration with the correct orientation. Each nonzero input bin produces
**one** event at its local integer index. A magnitude2 does not produce two
events. Negative/fractional values likewise remain nonzero events. Diagnostics
record this loss of magnitude information without redefining the source values.

The helper declares these indices milliseconds and samples at1ms, although the
recording bins are25ms. Its Gaussian sigma10 therefore spans ten input bins,
equivalent to250ms on the recording clock. The model receives the helper's rate
amplitudes; this code does not silently rescale them to physical firing rates.

The native path calls `GaussianKernel(10*ms)`, `neo.SpikeTrain(indices,
units='ms',t_stop=N)` and Elephant's `instantaneous_rate(...,
sampling_period=1*ms)` directly. It never substitutes `gaussian_filter` or another
approximation. `ElephantBackend` requires an explicit installed-version map for
`elephant`, `neo`, `quantities`, `numpy`, `scipy` and `scikit-learn`; it records
actual module hashes and inherited defaults. The author source does not fix
the smoothing library's cutoff, border handling or historical runtime. Missing
dependencies fail; nothing is installed automatically.

```sh
python -B preprocess.py --source-pickle /operator/original/rat_data.pkl \
  --runtime-versions /operator/frozen-installed-versions.json \
  --recipe released-decoding-pca20-segmented-v1 \
  --output-root /operator/workspace/released-preprocessing
```

This command performs numerical preprocessing and PCA fitting. It requires a
qualified runtime and an admitted execution budget. No authentic preprocessing
or fit was run while constructing this component. Elephant was unavailable in
the construction environment; no native smoothing-parity claim is made.

PCA uses the source `PCA(n_components=...)` defaults, recording the realized
solver, mean, component matrix, singular values and explicit fit-row identities.
Its unseeded source default remains visible; no historical seed is invented.
Query projection uses the same trained PCA. Both anchors and differences are
retained with original row IDs and each next-row derivative dependency. The
difference is `P[t+1]-P[t]`, without division by either clock's time step.

`construct_source_graph` supplies the exact source graph call with k15 and
delta1.5 to a trusted operator constructor. The pinned source's default spacing0
retains all nodes. `results.graph_embedding` verifies native `sample_ind`,
float32 anchor/difference arrays, and the returned `data.emb` before attaching
the existing row IDs. It refuses missing/reordered nodes. Graph construction and
MARBLE/CEBRA execution remain separate from this preprocessing component.

## Native notebook outputs and the paper endpoint

`results.decode_notebook_pair` implements the original position and direction
36-neighbor cosine decoders. `native_summary` and `adapt_notebook_outputs` retain
all six helper outputs for CEBRA-time, CEBRA-behavior and MARBLE. The adapter
requires all native rows, including CEBRA's final2,000th error. It separately
exposes the notebook's 1,999-row pointplot view, where each CEBRA error vector is
truncated by one, and its distinct median/SEM barplot inputs. The helper's
per-sequence diagnostic selects two endpoint rows; it is not mislabeled as the
median over the entire direction interval.

Means and standard-deviation companions are explicitly recomputed in float64.
SEM follows the notebook's SciPy call on the original error dtype. These outputs
do not establish bit parity with historical plotting libraries. The requested
paired Wilcoxon comparisons are retained as inputs; no historical p-values are
fabricated. These operator reports contain private predictions/errors and are
not participant-facing material.

`figure5_inputs` accepts independently supplied complete32D outputs and a frozen
original support declaration. Its support digest is SHA256 of UTF-8 JSON with
sorted keys and separators `(',', ':')`. It requires exact embedding order,
explicit original source row IDs, complete2,000-row query support and declared
preprocessing/model/exposure pins. It joins labels by those source identities
without reordering embeddings. `score_complete` calls the unchanged source
scorer. A 1,999-row artifact fails before decoding. A valid digest and2,000 rows
still do not prove historical source provenance; returned scientific
qualification remains false.

The training notebook's untransposed MARBLE call would confuse time with neurons
(Achilles would yield119 anchors), while its CEBRA loops expose complete neural
recordings and, for behavioral training, all behavior labels. The released
checkpoints omit PCA, original row IDs and exposure provenance. This component
does not silently fix that training code or certify its checkpoints.

## Validation and next scientific decision

Generated controls exercise exact tensor views, restricted pickle refusal,
source row support, clock/magnitude handling, PCA application, derivative
boundaries, graph/result binding and the hard2,000-row scoring boundary.
Differential controls extract the pinned source helper but inject an explicitly
generated rate backend and use real scikit-learn PCA. They check source wiring,
not numerical Elephant parity. `reference/rat_utils.py` and its MIT license are
retained for this comparison. `TESTING.json` records observed executions and
their limits.

The separate `tests/test_elephant_required.py` command requires the real
Elephant/Neo/Quantities backend declared in
`dependencies/elephant-test-versions.json`. Missing or mismatched dependencies
are errors. Its generated signals test the pinned author function with real
Elephant and PCA, nonzero-magnitude collapse, empty channels, Gaussian amplitude
and clock units, endpoint loss at smoothing boundaries, and runtime refusal.
The selected backend is an explicitly modern test environment, not a recovered
historical author environment. Those tests must pass in hosted CI before native
numerical validation is claimed; they were not run on the construction Mac,
where Elephant is absent. No authentic neural signals are used by this seam.

From this component directory, the three required hosted commands are:

```sh
MARBLE_FIXTURE_ROOT=/tmp/marble-generated-views python -B tests/test_original_preprocessing.py
python -B tests/test_cache_binding.py
python -B tests/test_elephant_required.py
```

The first command includes the complete original-shape generated export and
reclaims its temporary files. Its fixture root must be explicit; omitting it
skips that one control and is not the required complete command. The commands
contain 33, 11 and 4 tests respectively; method counts do not certify scientific
comparability or successful hosted execution. Use the six exact dependency
versions in the named JSON for the native command, without the unrelated full
MARBLE training stack.

Recovering historical2,000-query support remains a source question. A fresh
paper-described route would need an explicitly adopted physical event/clock,
kernel, boundary and exposure policy, and would be named as a new specification.
Moving forward differences before the split still loses the final row; shifting
the split to obtain2,000 vectors changes which observations are tested. Neither
operation is an automatic repair. Reproduction, exceeding the original result,
and broader SOTA all remain unqualified.
