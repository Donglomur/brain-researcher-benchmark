# CA1 fixed-bin mutual-information construction reference

Compute every neuron pair's discrete MI, finite-sample quadratic extrapolation, and IID-shuffle or temporal-shift diagnostics from complete prepared session arrays. Outputs retain full-session observations, fixed bins, shared schedules, negative corrections, pair-level results and animal-balanced descriptives.

Python 3.10+ standard library runs the evaluator and its core tests. MAT preparation additionally requires an already available NumPy/SciPy runtime. No dependencies or data are downloaded.

From this directory:

```sh
python3 mint_reference.py /local/packet.json /local/result.json \
  --sample-sizes 64 128 --null-mode iid_permutation --null-count 30
python3 prepare_mat.py /approved/local/input.mat /local/packet.json \
  --root-variable Hippocampus_data --identities /local/identities.json
python3 -m unittest discover -s tests -v
```

The sample counts are illustrative prospective choices. Input packet schema, explicit identity mapping, source discrepancies and metric definitions are in the [task implementation documentation](../../docs/initial-evaluator-v1.md). The test fixture supplies a complete generated packet example.

Scientific qualification is **unknown**. Actual supplement schema/population, bin provenance, native MATLAB parity, empirical reproduction, protected references and frozen grading remain unresolved. Circular shifts and exceedance fractions are diagnostics, not demonstrated false-positive calibration. The source figure script's direct-MI invocation is disabled; this independently written computation does not claim a historical or complete Figure2 reproduction. Generated controls establish engineering behavior only.
