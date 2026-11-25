# PAPER-ROOT-ADD-021 post-fit evaluator

This independently written component evaluates an explicitly supplied native parameter CSV: strict fit QC, grouped Gaussian smoothing, participant/region alpha-frequency and intrinsic-timescale summaries, log2-age relationships, hierarchy/PAF interactions, and separately labeled prospective participant-held-out prediction errors.

Requires Python 3.10+ and NumPy. From this directory:

```sh
python3 -B evaluator.py analyze --parameters /approved/generated_parameters.csv --packet /approved/packet.json --output /operator/statistics.json
python3 -B evaluator.py score-heldout --reference /operator/statistics.json --submission /candidate/predictions.json --output /operator/errors.json
python3 -B -m unittest discover -s tests -v
```

The packet binds the generated CSV SHA-256, official analysis-code commit, exact approved participant roster, and engineering/public-table assessment status. All finite operator reference targets must receive exactly one participant-held-out prediction. Reference statistics stay operator-side.

This completes a post-fit construction component. It does not implement or validate native ECoG spectral fitting, authentic dataset coverage, historical FOOOF identity, empirical reference agreement, a frozen benchmark score, or scientific qualification. Native knee-to-INT and paper/source peak-definition discrepancies remain explicit. No empirical datasets or author source are included.

See [the full task documentation](../../docs/initial-evaluator-v1.md) for the input contracts, source/prospective distinctions, rights, and preserved gates; [provenance.json](provenance.json) pins inspected sources.

## Small finite prediction errors

The held-out evaluator preserves equal-participant RMSE when nonzero residuals
are so small that their binary64 squares round to zero. It uses a scaled
calculation only for that zero-macro-MSE case; ordinary scores, exact-zero
errors and overflow refusals retain their existing behavior. The per-participant
MSE fields still use binary64 and may round to zero even when the root metric is
representable. A nonzero root metric below binary64's output range is refused.
Means also preserve representable subnormal values that would be lost by
dividing each term before aggregation. These are numerical corrections using
generated controls, not authentic-data results or scientific qualification.
