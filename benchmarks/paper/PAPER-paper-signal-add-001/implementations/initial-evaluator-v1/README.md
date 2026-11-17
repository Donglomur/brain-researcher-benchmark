# PAPER-paper-signal-add-001 initial evaluator

Computes source-grounded LFP Tort comodulograms and phase-bin curves, single-unit PAC count/Poisson model comparisons, and a separately prospective patient-grouped load contrast. Uses frozen2024 NWB example identities and original public masks. Authentic/native reproduction and scientific qualification remain unknown.

Dependencies: Python3.11+, NumPy, SciPy; h5py for local NWB input; pytest for generated controls. Nothing is installed or downloaded by this package.

```sh
python3 -m pytest -q tests
python3 evaluator.py lfp-example /approved/example.nwb --receipt /approved/receipt.json --output /approved/lfp.json
python3 evaluator.py su-example /approved/example.nwb --receipt /approved/receipt.json --alignment prospective_right_edge_bins_v1 --output /approved/su.json
python3 evaluator.py patient-contrast /approved/cohort.json --output /approved/contrast.json
```

NWB commands are documented interfaces, not evidence of authentic execution. Single-unit execution requires an explicitly prospective repair of a source sample-length defect. Population eligibility, native parity, grading/protected evaluation and component rights remain open. Original source mixes BSD3 and GPL-2.0-or-later components; no author implementation files are vendored.

See the [full source contract, usage and limitations](../../docs/initial-evaluator-v1.md), `source_contract.json`, and `tests/test_evaluator.py`.
