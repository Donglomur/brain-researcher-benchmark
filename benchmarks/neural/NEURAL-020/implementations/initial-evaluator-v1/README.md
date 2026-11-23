# NEURAL-020 initial evaluator

Frozen Area2 tensor preparation, private active/perturbed Poisson co-bps scoring, and training-mean/NLB smoothing controls. [Full task documentation](../../docs/initial-evaluator-v1.md) defines input contracts, commands, primary-source provenance and qualification gates.

Core runtime: Python 3.11 and NumPy. The retained 22 evaluator controls also require SciPy and scikit-learn; the eight public preflight controls need NumPy only. Full test discovery contains 30 controls, and missing dependencies fail rather than skip them. No command installs dependencies or reads the network.

```sh
python3 evaluator.py score --gold private_gold.npz --submission predictions.npz --output score.json
python3 -m unittest discover -s tests -v
```

Participants can check a complete prediction artifact using only their public query
packet, before the operator opens private targets:

```sh
python3 submission_preflight.py --query public_query.npz \
  --submission predictions.npz --output preflight.json
```

This route checks all public trial/bin/unit identities, the complete 65-unit
partition, prediction shape, explicit spikes-per-bin units, and finite nonnegative
expected counts. Fractional expected counts and zeros are valid; values are not
renormalized, imputed or converted from Hz. The unchanged evaluator supplies the
array and archive validators. No private labels, target coverage, source-recording
authenticity, performance or scientific readiness are established by preflight.
The result reports the packet's **declared** digest, not independent authentication
of its source. The operator's original score command still performs private
condition and target checks. The eight additional generated controls can run with
Python 3.11 and NumPy alone via `python3 tests/test_submission_preflight.py`.

Preparation requires the complete declared 826-row/65-unit pre-binned training-asset population and a frozen operator manifest. This is not an NWB acquisition adapter or a qualified scientific benchmark. Native conversion, authentic reference performance, leave-condition-out protocol scope and protected holdout admission remain unresolved. All bundled tests use generated engineering controls. Exact-source parity runs by default against the bundled, unmodified MIT-licensed scorer in `vendor/nlb_evaluation.py`, covered by `NLB_LICENSE`. An optional `NLB_OFFICIAL_SOURCE` override must match the same SHA256 pin. Tests extract only the two metric functions and never import the vendored module.
