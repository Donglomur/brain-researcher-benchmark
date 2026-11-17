# NuCLR: complete inputs to the official training schema

This component closes a concrete missing interface: the accepted original NPY
assets can now be assembled into the `temporaldata.Data` session objects consumed
by the released NuCLR training pipeline. It preserves all 17 sessions, 69 blocks
and 10,153 session-neuron observations. It does not train a model, serialize an
HDF5 dataset, run an agent, or establish an improvement result.

[PANEL_SELECTION.json](PANEL_SELECTION.json) records the prospective complete
five-subclass ordinary-transductive comparison: all 1,500 source-eligible labeled
IDs, while representation training still uses the full original population.
The source split and existing macro-F1 readout are unchanged. All nine prepared
panels remain present and the invalid E/I-inductive split remains refused.
Historical 0.6101 is the inherited matching five-seed paper target, separate from
a future matched current-source reference. This scoped comparison neither claims
improvement across all nine panels nor replaces the full reproduction contract.

## The adapter

`bridge.load_route()` authenticates the unchanged current readout route. Use that
route's accepted-input binding and select `label_level='subclass'`,
`panel='transductive'`. Then `bridge.iter_accepted_sessions(selection, route)`
yields every original session in the manifest order. It accepts no convenience
session, neuron or experiment subset. The full accepted three-file metadata
binding, original split and upstream input verification are inherited through
the existing route rather than reimplemented.

Each future iteration authenticates original activity/time and numeric metadata
members with the existing NPY reader. It reads the raw source values, uses the
already shifted `i * 3600` timestamps, and retains each source block's full row
and column order. It uses the accepted full-session 99th-percentile scalar with
its recorded scalar dtype. It does not estimate a new percentile, normalize by
block, shift again, reorder around gaps, interpolate, clip or drop observations.

`assemble_session` is the lower-level numerical constructor boundary. It calls
original `IrregularTimeSeries(..., domain='auto')` for every block, unions the
resulting domains, and constructs the final series with both `df_over_f` and
`df_over_f_norm`. Automatic interval endpoints and union semantics are delegated
to the real pinned dependency; no guessed epsilon or handwritten HDF5 schema is
introduced. All source metadata fields, literal unit IDs, labels, uppercase
subject ID, recording date, numeric dtypes and nonfinite metadata values are
preserved. UniqueID remains in the owner audit, as the released preparer omits it
from the model schema. The source's misleading fluorescence variable name does
not change the original deconvolved-calcium units.

The constructor boundary is also usable with generated arrays and explicit test
doubles. Those controls establish call/data correspondence, not authentic data
custody or actual temporaldata/HDF5 compatibility. Neither its runtime object nor
a receipt is an isolation capability. The returned objects contain owner-only
transcriptomic labels and must never be delivered wholesale to an agent.

## Runtime and serialization remain distinct

The loader requires the released temporaldata and brainsets VCS revisions and
refuses missing, different or editable declarations. Installation metadata is
not loaded-source-tree attestation. Actual dependency source inspection, a
pinned runtime, original serializer/load roundtrip and `torch_brain.Dataset`
window/column checks remain required. No fallback or automatic install is used.

An admitted conversion should consume each session once, serialize with the
original `data.to_hdf5(handle, serialize_fn_map=brainsets.core.serialize_fn_map)`,
and release it before requesting the next. It must prove complete exhaustion,
17 fresh ordinary HDF5 outputs and all 69 blocks/10,153 observation identities.
Holding every object simultaneously is outside the one-session memory design.
A resource-bounded, no-clobber serializer and its actual library controls must be
reviewed before authentic conversion. They are deliberately not fabricated here
without the required dependency implementations. This source-only construction
has read no authentic array values or prepared owner metadata.

## Original reference and frozen candidates

[REFERENCE_RECIPE.json](REFERENCE_RECIPE.json) freezes the inspected source/config
identities and complete training-to-embedding call chain. It explicitly separates
resolved source defaults from unresolved prospective execution choices. Default
30 epochs cannot silently stand in for the README's roughly 50,000-step
recommendation or an unrecovered historical training horizon. Device count,
workers, epoch/step horizon, seed roster, forwarding batch/checkpoint set and
finite budgets must be frozen and independently reviewed before any run.

The genuine reference must execute the released calcium encoder and contrastive
objective, save completed model checkpoints, and forward over the full permitted
population. The original collector sorts literal IDs, sums contributions in
float64, and divides by per-ID counts. A missing/zero-count original ID must fail
complete coverage. Only afterward does the readout project to the 1,500 selected
labels, retaining the collector's relative order and the original fixed splits.
Supplied arbitrary embeddings or a program printing 0.6101 are not references.
The existing selected-checkpoint resampling/scaling/logistic readout is reused.

Paper+data and paper+data+author-code need fresh restricted candidate contexts,
identical permitted data/supervision, endpoint and budgets, followed by frozen
submitted methods before final scoring. The second context alone receives
original author code. Original training diagnostics read full transcriptomic
labels and must remain owner-side. Removing diagnostic passes can alter random
number consumption; `debug` disables checkpoints and is not an equivalent
protected training recipe. Construction notes and the source-derived candidate
hypothesis below must not leak into a paper+data-only context.

Reproduction and improvement remain distinct. A current matched reference
comparison can be useful with explicit seed/cohort scope while historical
artifact/runtime equivalence is unknown. Numerical equivalence, meaningful-effect
and uncertainty policies remain unqualified; neither seed variability nor neuron
counts establish independent mouse-population uncertainty. No arbitrary margin,
new effect goal or weakened published comparator is added.

## Source behavior retained; candidate hypothesis only

At official revision `0fa409b304147ace00507063d44f03155691af62`,
`src/transforms/unit_dropout.py:31-43` samples a mask but the calcium branch only
changes raw `df_over_f`. `src/models/nuclr_v2ga_ca2.py:147-166` consumes unchanged
`units.id` and `df_over_f_norm`. Consequently this source data flow does not drop
model-input neurons; its RNG draws still occur. The reference and this bridge
retain that behavior. Exact hashes and locations are in the recipe.

Consistently masking units and both activity arrays is a prospective candidate
hypothesis. No candidate implementation, runtime causal claim, novelty claim or
performance gain is established here. It must be named as a method change, never
silently applied to make the original reference appear repaired.

The unchanged licensed original preparer is retained under `reference/` for
source differential controls. Its SHA256 is
`10af34325fcc3dedb47a3cb461b562ac0292f1481e9d3a757c094f6866ae35c0`.
The source README's `--session` spelling is an unambiguous argparse abbreviation
of `--session_dir`; no CLI failure is claimed. Use the exact long spelling in any
future source command.

## Generated validation

Repository-root command (existing NumPy environment, one thread):

```sh
python -B -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-012/implementations/temporaldata-bridge-v1 -p test_bridge.py -v
```

Fourteen targeted methods passed once. They compare the literal original
preparer's AST against this bridge using real NumPy and explicit external
constructor/loader doubles, check missing/changed source fields and runtime
provenance refusals, and exercise complete 17-session accounting through a mocked
custody boundary. They write no fixtures and run no authentic arrays, models,
real temporaldata constructors, HDF5 serialization or prior test suites.
The opaque interval double deliberately uses an invented endpoint convention;
passing it proves identical constructor calls, not real endpoint correctness.

Two separate generated data-flow controls also passed once:

```sh
python -B -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-012/implementations/temporaldata-bridge-v1 -p test_dropout_dataflow.py -v
```

They execute only the exact original `UnitDropout` and tokenizer AST bodies on
invented arrays, using explicit tensor/rearrangement/chain doubles. A forced
nontrivial mask changes the raw columns and consumes RNG calls while preserving
the normalized object, full unit IDs and numerical tokenizer input. A sensitivity
control changes normalized data and detects changed tokenizer input. This
confirms the specified generated data flow; it is not real temporaldata/Torch
execution or a causal performance experiment. The 14 schema controls were not
repeated for this addition.

The unchanged `reference/unit_dropout.py` and `reference/nuclr_v2ga_ca2.py` are
also from the official NuCLR revision above, under the accompanying Apache-2.0
license. Their original paths, complete SHA256 identities and relevant line
locations are frozen in `REFERENCE_RECIPE.json`.
