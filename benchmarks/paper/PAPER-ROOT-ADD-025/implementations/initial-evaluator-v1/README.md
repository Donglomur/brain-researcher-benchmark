# PAPER-ROOT-ADD-025 linear encoding/readout evaluator

Computes the paper-described supplementary linear encoding and readout endpoint from pinned, aligned 160 Hz component/behavior packets: source eligibility, sample pairing, matched subsampling, 10-fold univariate OLS, signed component/parcel averaging and consistency contrasts. It includes an explicit grouped-trial-fold sensitivity.

Requires Python 3.11 and NumPy. From this directory:

```sh
python3 evaluator.py packet.json output.json --seed 11 --fold-mode source_rows
python3 evaluator.py packet.json grouped-output.json --seed 11 --fold-mode grouped_trials
python3 -m unittest discover -s tests -v
```

Default selection uses all finite generative means, matching the inspected S11 script. `--generative-limit 4` selects the near-zero sensitivity. See the [input schema, numerical semantics and provenance](../../docs/initial-evaluator-v1.md).

This is a complete constructed linear endpoint, not the main MI/II analysis or a qualified native reproduction. Authentic acquisition, MAT/export/resampling parity, full source population, protected references, MINT semantics and scientific qualification remain unresolved. Supplied components were fitted across all trials. Generated tests establish engineering behavior only; no authentic/model/native scientific runs or dependency installations were performed.
