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
