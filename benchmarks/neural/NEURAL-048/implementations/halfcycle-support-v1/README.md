# Complete-half-cycle support for NEURAL-048

This operator helper derives the support and availability of already aligned samples from explicit physical-time dependencies, then calls the existing source-pinned causal-history builder. It closes a concrete interface gap: an operator cannot provide a short sample-level support bound while declaring that the value depends on a later half-cycle boundary.

The [published methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC13246447/) describe rescaling head-curvature half-cycles to a common frequency. **Inference:** recovering that scale requires the ending crossing; a location within the aligned cycle is therefore not itself evidence that the transformed value was available at that physical time. This helper carries that dependency forward. It neither reproduces the alignment nor proves that the operator has declared every dependency.

`compile_samples(samples, intervals)` accepts two exact-field inventories. Each interval has `id`, `worm_id`, `session_id`, `clock="physical_ns"`, integer `start_ns` and `end_ns`, and these four integer dependency bounds:

- `signal_support_end_ns`, `signal_available_ns`: the latest source support and availability across **all** signal operations used for that complete aligned interval.
- `crossing_support_end_ns`, `crossing_available_ns`: the corresponding bounds for detecting both bounding curvature crossings, including any smoothing or interpolation used to detect them.

For each dependency, the complete right boundary must be no later than its support end, which must be no later than availability. The compiler takes the maximum support and maximum availability across the two dependencies. Thus later source dependencies and processing latency remain visible. These are conservative declared bounds, not measured execution latency or authenticated native timestamps.

Each sample has exactly `id`, `worm_id`, `session_id`, `interval_id`, integer `time_ns`, `curvature`, `velocity`, `odor_encounter`, and a nonempty finite `neural` vector. Its time is the corresponding **physical** source position, established by the operator; a normalized frame number cannot be relabeled as nanoseconds. The compiler does not infer that mapping. Sample-level support overrides, unknown intervals, cross-session borrowing, duplicate physical samples, changed channel width and incomplete dependency declarations fail. The interval inventory must match the selected sample inventory; unused intervals fail.

`build_histories(samples, intervals, events, lags_ns, neural_shift_ns, max_age_ns)` passes the compiled samples to the unchanged `initial-evaluator-v1/evaluator.py`, pinned to SHA-256 `cd2dc29f52e4aa79a5dc5b913aad9bef57b08e9bbf74f7c7a463b923c9e03d57`. The original helper checks support and availability against each actual lag query, and checks exact within-session neural displacement. One unavailable event rejects the complete request. No unavailable windows are dropped to improve apparent coverage.

The result contains histories, exact input/compiled-sample digests and explicit unqualified status. It is an operator artifact, not a participant packet or an isolation boundary. The scorer, log-loss estimand, whole-worm folds and frozen comparator are unchanged. The helper does not fit models or make a direct neural-understanding claim.

The [Dryad documentation](https://datadryad.org/dataset/doi:10.5061/dryad.8sf7m0cz2) identifies aggregate MAT rows with their individual H5 recordings and says the aggregates add neuron identities and manually annotated odor encounters. This supports investigating a direct aggregate-to-episode mapping for the prospective neural task. It does not authenticate field names, a physical clock transform, causal preprocessing, the selected animal cohort or a replacement for the author's CSV workflow. Those native source questions remain unresolved; no native payload was read here.

Run the generated controls from this component directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The controls exercise full-boundary rejection through the real history builder, late availability, exact large integer clocks, cross-session identities, duplicate physical samples, malformed values, unchanged histories under future-value perturbations and complete-request failure. They use invented software examples, not animal data. Passing them establishes the declared-bound propagation behavior only.
