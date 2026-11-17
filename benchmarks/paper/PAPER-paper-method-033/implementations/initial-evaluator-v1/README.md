# MindBridge fixed-target feature evaluator

Run `python3 evaluator.py protocol.json reference.json submission.json output.json` using a prospective protocol, trusted reference features and complete paired arm outputs. This package computes source-faithful Pearson identification/correlation metrics, validates image/session/exposure/calibration identities, and evaluates paired adaptation curves with neural controls. It does not run or claim to reproduce MindBridge.

See [the full interface and scientific limits](../../docs/initial-evaluator-v1.md). Run generated engineering controls with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Python and NumPy are required; no installation or downloads occur.
