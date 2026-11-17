# Figure 1 five-module simulation scorer

This component implements the original Figure 1i correct-triplet and Figure 1j
contamination endpoints. It preserves all five modules and summarizes all ten
original realizations. It does not generate simulations, fit Rastermap, recover
the published numeric result, or decide paper improvement. The older empirical
evaluator remains unchanged and evaluates different endpoints.

The source basis is the authenticated cached `paper/metrics.py` and
`paper/fig1.py` at Rastermap revision
`b37644ea52c4cd81f143a9c2cec90286ffd61c49`; hashes and URLs are in
[provenance.json](provenance.json). No source payload is redistributed here.

## Endpoint semantics

`source_benchmarks(xi_all, embeddings, rng)` returns fractions in an array with
axes `[metric, method, module]`, with contamination first and correct triplets
second. It appends the source's float32 random embedding control. Qualifying
contamination-pair counts are returned separately. Module order is tuning,
sustained, sequence 1, sequence 2, power-law.

- Correct triplets: draw `10*n` distinct-neuron triples per module, uniformly
  without replacement within each draw, allowing new draws to repeat triples.
  Sort by the ground-truth rank and count strictly increasing or decreasing
  embedding ranks. Both orientations count as correct.
- Contamination: draw `10*n` distinct-neuron pairs per module. Only pairs whose
  embedding ranks differ by more than five qualify. Preserve the exact source
  half-open slice `order[lower+1:upper-1]`; changing its upper bound changes the
  endpoint. Average outsider fraction over accepted pairs. Rejected draws are
  not replaced. With no qualifying pairs the low-level result is NaN; complete
  panel aggregation rejects undefined scores.
- Ties: retain NumPy's default `argsort`, as the source does. Do not introduce
  average ranks, stable sorting, tie correction or a tie-aware replacement
  metric. NumPy/environment identity matters for source replay.
- Draw stream: the direct API creates the random control first, scores
  contamination for every supplied embedding then the random control, and
  scores triplets in the same order. With the same initial legacy RandomState,
  embeddings and NumPy, the differential control checks exact values and final
  RNG state against the pinned author functions.
- Aggregation: `summarize_panel` requires IDs `0..9` and shape
  `[10,2,methods,5]`, converts fractions to percentages, and reports the source
  mean and SEM (`100 * std(ddof=0) / sqrt(9)`). Modules and metrics are never
  combined into a weighted score. Neurons and sampled pairs/triples do not add
  independent realizations.

## Operator scoring interface

Python 3.10+ and an existing NumPy environment are required. The CLI accepts an
operator-owned JSON request and writes a new JSON report:

```sh
python3 scorer.py /absolute/operator/request.json --output /absolute/operator/report.json
```

The request has exactly these three top-level keys:

```json
{
  "schema": "rastermap-figure1-score/v1",
  "method_names": ["source_rastermap", "candidate"],
  "realizations": [
    {
      "id": 0,
      "metric_seed": 1234,
      "activity_sha256": "<64 lowercase hex characters>",
      "target": {"path": "/absolute/operator/target0.npz", "sha256": "<sha256>"},
      "embeddings": {
        "source_rastermap": {"path": "/absolute/operator/author0.npz", "sha256": "<sha256>"},
        "candidate": {"path": "/absolute/operator/candidate0.npz", "sha256": "<sha256>"}
      }
    }
  ]
}
```

This excerpt illustrates one row; execution requires all ten rows, IDs `0..9`
in order, and every method in every row. The target packet must contain only
`xi_all` and `neuron_id`. Each embedding packet must contain only `embedding`
and `neuron_id`. Every `neuron_id` must be the integer shuffled activity row
index, exactly `0..5999` in that order; an algorithm's sorted permutation is
not an embedding vector. `xi_all` and embedding may be vectors or N-by-1
matrices. All must be finite and complete. Original module counts are
1,000/1,000/1,000/1,000/2,000. The scorer rejects smaller fixtures in this route.
Packets are limited to 1 MiB compressed and expanded; pickle loading is off.

The operator must stage these packets from independently authenticated original
simulation identities and frozen embeddings. Packet hashes verify bytes and
row checks enforce an interface; they do not authenticate the original
generator, prove that a submitted method used the declared activity, or prove
that `source_rastermap` came from a competent author run. `activity_sha256`
records that operator association; the scorer does not open the 6,000-by-50,000
activity matrix. No preparation or author calibration is claimed here.

**The CLI uses an explicit prospective RNG policy:** each method is scored by
the one-method-plus-random source routine with a fresh identical RandomState
for that realization. This gives paired metric draws and makes a method's
scores independent of other submitted methods. The original source's
post-fitting RNG state, seven-method draw schedule, and software environment
are not recovered. Therefore CLI scores must not be labeled the original
published panel or an exact author replay. The direct `source_benchmarks` API
can replay the full original embedding list once its initial state is recovered.

The report retains all per-realization, per-method, per-module percentages,
means, SEMs, accepted-pair counts, random controls, artifact hashes, and metric
seeds. Candidate minus author differences are oriented so positive is favorable
for each endpoint (author minus candidate for contamination). These are
descriptive paired differences, with no superiority test or binary reward.
The report contains no input filesystem paths, ground-truth values, or raw
embeddings. It still belongs to the operator's external evidence until final
query and feedback rules are approved; repeated access would disclose scores.

## Software controls

Use the shared reviewed test pool described in the wave's `TEST_POOL.md`; do not
launch numerical test processes outside it. The commands inside the pool are:

```sh
python3 -I -B tests/test_scorer.py
python3 -I -B tests/source_parity.py /absolute/cache/paper__metrics.py
```

The first file checks source interval and rejection rules, reversed and
interleaved orders, whole-panel aggregation, malformed and mismatched packets,
complete roster preflight, and paired report directions. The generated transport
test uses a stub metric and is labeled accordingly. The second file requires
the exact source hash, extracts only four pure metric functions via AST, and
compares actual scores plus final RNG state on shuffled, tied and untied
generated fixtures across three RNG seeds. It imports none of the source's
training or embedding dependencies. These are software controls, not scientific
simulation generation, author inference, or a candidate trial.

## Remaining scientific work

Recover and pin the published Figure 1 numerical artifact, the original
serialized ten simulations, native environment and execution RNG provenance.
Calibrate the author result without treating a regenerated artifact as the
published bytes. Freeze meaningful effects, joint panel decision, uncertainty,
candidate source/target access, tuning budget and final query policy before
any candidate evaluation. The public generator and original seeds remain
exposed; local target isolation cannot erase that exposure. Genuine source
preparation and native work require their own frozen protocol and resource
lease. No native numerical workload was run to build this component.
