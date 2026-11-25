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

## Authenticated NWB input descriptor

The NWB bridge hashes and decodes the same retained descriptor. It verifies
descriptor device/inode, size and modification/change times before and after
hashing and HDF5 reads, refusing detected in-place changes before returning the
detached arrays. It does not claim an immutable filesystem or protection from
a hostile kernel. The existing exact source-asset receipt requirements remain.

Three generated controls in `tests/test_verified_nwb.py` preserve unchanged
array values and source-pin refusal, and reproduce pathname-replacement and
in-place-write failures. Their explicitly injected tiny HDF5 fixtures are not
source assets. No authentic recording, model fit or scientific qualification
is established, and all numerical analysis definitions remain unchanged.
