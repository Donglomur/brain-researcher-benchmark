# NEURAL-020 initial evaluator

Frozen Area2 tensor preparation, private active/perturbed Poisson co-bps scoring, and training-mean/NLB smoothing controls. [Full task documentation](../../docs/initial-evaluator-v1.md) defines input contracts, commands, primary-source provenance and qualification gates.

Core runtime: Python 3.11 and NumPy. Smoothing and the complete 22-test suite also require SciPy and scikit-learn; missing test dependencies fail rather than skip controls. No command installs dependencies or reads the network.

```sh
python3 evaluator.py score --gold private_gold.npz --submission predictions.npz --output score.json
python3 -m unittest discover -s tests -v
```

Preparation requires the complete declared 826-row/65-unit pre-binned training-asset population and a frozen operator manifest. This is not an NWB acquisition adapter or a qualified scientific benchmark. Native conversion, authentic reference performance, leave-condition-out protocol scope and protected holdout admission remain unresolved. All bundled tests use generated engineering controls. Exact-source parity runs by default against the bundled, unmodified MIT-licensed scorer in `vendor/nlb_evaluation.py`, covered by `NLB_LICENSE`. An optional `NLB_OFFICIAL_SOURCE` override must match the same SHA256 pin. Tests extract only the two metric functions and never import the vendored module.
