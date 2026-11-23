# Supplied occurrence likelihood terms

This standard-library component independently recomputes per-bin and per-occurrence
likelihood terms from evaluator-supplied observations, model expected counts and
PSTH expected counts. It preserves supplied occurrence identities and time support.
It does not produce the unresolved final Figure 2b neuron vector or paper score.

The pinned [author likelihood source](https://github.com/marineschimel/v1lm_nn/blob/eec6021e8b9f9031eb775fc1a10a07e583cf0e29/lib/analysis.ml)
multiplies posterior mean firing rate by `dt` before returning expected counts
(`compute_LL`, lines 172–178), then computes `y*log(mu)-mu` (lines 209–213).
Its empirical route uses the same term (lines 285–300). Factorial constants are
omitted; they cancel in the model-minus-PSTH residual only for identical observed
counts and support. This component accepts expected counts directly and never
multiplies them by the bin width again.

## Input and use

Run from the repository root:

```sh
python3 -I -S -B benchmarks/paper/PAPER-CANDIDATE-20261114-CONSENSUS/implementations/likelihood-terms-v1/likelihood_terms.py \
  < /private/supplied-terms.json > /private/recomputed-terms.json
```

The input has exactly `schema: "consensus_supplied_likelihood_terms_v1"`,
`units: "expected_spikes_per_bin"`, an explicit `bin_width_seconds: 0.005`, and
`records`. The bin width declares the original 5 ms support; it is not a conversion
factor. Each record has these fields:

- `key`: `animal_id`, `fold_id` (0,1,2), `model_variant` (constrained or unconstrained),
  `condition_id`, `target_neuron_id`, `source_trial_index`, and `occurrence_index`.
  Animal, condition and neuron identifiers are supplied nonempty strings. Source
  trial and occurrence indices are nonnegative integers. Repeated source-trial
  identities are permitted when the complete occurrence keys differ.
- `time_bin_ids`: strictly increasing supplied integer indices, retained exactly.
- `target_counts`, `model_expected_counts`, and `psth_expected_counts`: lists with
  exactly one value per time bin. Counts must be nonnegative exact integers,
  including integral floats, at most 2^53. Expectations must be finite and positive.
- `reported_model_ll_terms` and `reported_psth_ll_terms`: aligned finite lists or
  null. When supplied, outputs include reported-minus-recomputed differences;
  no numerical acceptance tolerance is inferred.

The component rejects duplicate keys, altered extents, nonfinite values, boolean
numbers, negative/nonintegral observations, nonpositive expectations and overflowing
sums. In particular, it does not choose a smoothing or zero-rate convention.
An input containing such cases is refused in full, rather than being scored after
dropping rows. The engineering limits are 16 MiB JSON, 10,000 records and 200,000 total
time bins. These limits and supplied IDs do not establish complete native coverage.

Outputs retain each key and time-bin sequence, both term vectors, their separate
time sums, model-minus-PSTH residual, spike count and bin count. `math.fsum` performs
the time reductions; bitwise agreement with Owl's reduction order is not asserted.
Records are never averaged into a neuron, animal, fold or population score.
Authentic records contain protected observations or derived results and belong
in evaluator storage, not participant packets or public artifacts.

## Verification and limits

`test_likelihood_terms.py` contains 12 generated controls: hand-computable terms,
factorial cancellation, no repeated `dt` scaling, repeated trial occurrences,
support mismatch, invalid values, descriptive differences and all-or-no-output CLI
behavior. No control reads authentic data or executes OCaml/Owl.

Input provenance, native parameter/target isolation, complete seven-animal and
three-fold coverage, empirical PSTH construction/offset selection, active-neuron
mask, native zero/nonfinite behavior and final Figure 2b reduction remain unresolved.
Supplying records or matching their arithmetic does not resolve those requirements.
The helper reports no paper score, scientific qualification or readiness promotion.
