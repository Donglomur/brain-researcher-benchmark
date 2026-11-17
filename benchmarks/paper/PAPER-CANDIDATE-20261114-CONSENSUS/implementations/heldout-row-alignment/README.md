# Heldout cache row alignment

This composes the existing [held-neuron correction](../held-neuron/README.md)
with a source-level repair of the four misaligned heldout cache fields in both
author entrypoints. It preserves the original trial permutation, source trial
multiplicities, split, numerical predictions and LL totals. It does not load
scientific data, fit models or establish Figure 2b reproduction or improvement.

The pinned author revision is
[`eec6021e8b9f9031eb775fc1a10a07e583cf0e29`](https://github.com/marineschimel/v1lm_nn/tree/eec6021e8b9f9031eb775fc1a10a07e583cf0e29).
In [fit lines 892–923](https://github.com/marineschimel/v1lm_nn/blob/eec6021e8b9f9031eb775fc1a10a07e583cf0e29/examples/fit_single_animal.ml#L892)
and [analyze lines 776–807](https://github.com/marineschimel/v1lm_nn/blob/eec6021e8b9f9031eb775fc1a10a07e583cf0e29/examples/analyze_fitted_model.ml#L776),
`argsorted_ids` sorts enumeration positions in descending order. Despite its
name, it does not sort trial IDs. That permutation is applied to `trialids`,
`pred_lambda`, `pred_us` and LL totals. The returned `ll_neuron_time`,
`pred_var_os`, `pred_var_us` and `pred_zs` retain their earlier order.

For example, gathered source IDs `[19, 4, 19, 7]` become `[7, 19, 4, 19]` in the
IDs and predicted means, while the four omitted fields still follow the first
order. The repeated source ID represents distinct occurrences and cannot be
repaired by a dictionary keyed only by source ID. The insertion applies the
same permutation to every omitted field **after** the LL totals have been
computed and reordered; applying it before that sum would reorder totals twice.

## Apply to exact external originals

Use Python's standard library. Keep both implementation directories together;
the tool authenticates and reuses the reviewed predecessor, without copying its
held-neuron implementation. It accepts only the three exact original files
described in [SOURCE_INPUTS.json](../held-neuron/SOURCE_INPUTS.json), authenticates
the insertion contexts, and creates a fresh output directory only after all
checks pass. Already-corrected originals are refused. A later write failure can
leave a partial tree, without a success report.

```sh
python3 -I -S -B align_sources.py \
  --fit-source /external/v1lm_nn/examples/fit_single_animal.ml \
  --analyze-source /external/v1lm_nn/examples/analyze_fitted_model.ml \
  --analysis-source /external/v1lm_nn/lib/analysis.ml \
  --output /external/fresh-aligned-source
```

The output contains all three composed source successors and
`ROW_ALIGNMENT_REPORT.json`, including exact original/predecessor/successor
hashes. The library successor is byte-identical to the prior held-neuron fix;
only the two wrappers receive the four new row-index operations. Every byte
outside the two insertions is identical to that predecessor output. Source
originals and rendered upstream bodies are not redistributed in this package;
the upstream license-scope limitation remains unchanged.

## Controls and limits

`test_alignment.py` has four generated controls and four source-integration
checks. Set `CONSENSUS_FIT_SOURCE`, `CONSENSUS_ANALYZE_SOURCE`, and
`CONSENSUS_ANALYSIS_SOURCE` to exact external originals to enable integration.
No variables gives an explicit skip; partial or incorrect inputs fail. Run the
tests through the project's approved lightweight test pool. The checks cover
the repeated-ID counterexample, exact byte composition, all-source tampering,
CLI output and refusal to overwrite an existing destination. Generated row
checks exercise insertion intent; they do not execute OCaml or Owl.

This is a corrected successor, not a reconstruction of historical caches.
Its original ordering is intentionally retained. It does not establish that
IDs alone distinguish repeated occurrences across neurons or MPI ranks, repair
already-existing archives, or remove the native per-trial exception handlers.
Missing trials, cross-neuron occurrence alignment, historical configuration,
the full seven-animal/three-fold census, both recurrent variants, exact PSTH
offset/aggregation, cached-output bypass and complete native dependency parity
still require qualification. No new benchmark score or readiness is claimed.
