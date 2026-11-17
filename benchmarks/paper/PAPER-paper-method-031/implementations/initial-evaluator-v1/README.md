# FAST trace, fidelity and latency evaluator

This independent NumPy evaluator accepts a SHA256-pinned panel of complete time-first movie exports, fixed ROI masks and declared method outputs. It computes ΔF/F traces, zero-lag temporal agreement, event fidelity, synthetic-only MSE/PSNR, and declared end-to-end latency for matched FAST/candidate outputs. Real electrophysiology is a temporal comparator, never a clean image target.

Dependencies: Python 3 and NumPy, already available in the construction environment. No installation, network, GPU or model execution is performed by this package. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 evaluate.py \
  --panel /absolute/path/panel.json --panel-sha256 OPERATOR_FROZEN_SHA256 \
  --submissions /absolute/path/submissions.json --output /absolute/path/report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The exact array/JSON interfaces, source provenance, and scientific limits are in the [task documentation](../../docs/initial-evaluator-v1.md). Tests generate tiny engineering controls; they do not run FAST or authentic data. The package implements an explicitly prospective held-out recipe. It does not certify archive population completeness, native preprocessing, source rights, authentic reference results, hardware receipts, scalar reward, or scientific qualification. Reused real data retain original-source licensing checks. Canonical task history is unchanged.
