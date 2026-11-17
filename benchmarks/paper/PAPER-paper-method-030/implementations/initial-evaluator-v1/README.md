# CellMincer paired-trace evaluator

Executable evaluation of prepared 500 Hz, 5,000-sample optical/electrical mV traces: published prominence-tolerant peak F1, lagged correlation, subthreshold false events, and residual-spectrum diagnostics. The frozen population covers all 22 saved raw TIFF/ABF pairs across nine filename-derived cell groups. Complete whole-cell split assignments, private EP references, CellMincer outputs, and a matched PMD or Noise2Self output are required.

Requires an existing Python 3.11 environment with NumPy and SciPy. Validated with NumPy 2.4.6 and SciPy 1.17.1; no installation is performed. From the repository root:

```sh
python3.11 -m unittest discover -s benchmarks/paper/PAPER-paper-method-030/implementations/initial-evaluator-v1/tests -v
python3.11 benchmarks/paper/PAPER-paper-method-030/implementations/initial-evaluator-v1/evaluator.py \
  --panel panel.json --private-reference protected-reference.json \
  --submission submission.json --output assessment.json
```

Use the Python executable for your existing compatible environment. The paths passed to the evaluator must be operator-prepared files following the [complete interface and scientific scope](../../docs/initial-evaluator-v1.md); generated examples are in `tests/test_evaluator.py`. Private EP and reference-derived reports remain grader-controlled.

This is a prepared-trace endpoint, not a native TIFF/ABF loader or model runner. Native ROI/channel/timing/calibration validation, authentic fresh denoiser execution, historical 26-training/22-evaluation identity, dataset rights, and scientific qualification remain unresolved. Explicit prospective grouping, peak extraction, and spectral policies are distinguished from published equations. Generated controls establish engineering behavior only; scientific qualification remains unknown.
