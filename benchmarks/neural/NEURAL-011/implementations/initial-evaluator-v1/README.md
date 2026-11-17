# NEURAL-011 initial evaluator

Implements patient-macro seizure-event F1, mandatory sensitivity and false alarms
per 24 hours over complete selected Siena patient recordings. Includes pinned
source-compatible event scoring and clock-annotation parsing, a train-only causal
EEG line-length comparator, a timing-only comparator, and paired patient
uncertainty. Only within-Siena public development is supported.

Requires Python 3 and NumPy; engineering checks used Python 3.11.6 and NumPy 2.4.6.
No dependency installation or dataset download is performed by this package.
Run from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 reference.py fit train-private.json line-length.json --signals train-eeg.npz
python3 reference.py predict test-public.json scores.npz --signals test-eeg.npz --artifact line-length.json
python3 siena_evaluator.py evaluate test-private.json scores.npz line-length.json report.json
```

The operator supplies verified complete-recording manifests and arrays. Public
prediction manifests must exclude held-out references; EEG arrays contain only
the frozen ordered EEG channels in microvolts. Missing recordings, incomplete
vectors, nonfinite values, prohibited channels and patient overlap are rejected.
See [the full task documentation](../../docs/initial-evaluator-v1.md) for input
schemas, annotation and timing-control commands, source identities and estimator
definitions.

This is construction source, validated with generated engineering controls and
small public metadata. Scientific qualification remains unknown. Authentic EEG
payload/header verification, native reference competence, protected evaluation,
scientific admission and rights review remain open. The CHB-training to
Siena-confirmation branch is unimplemented. Generated test results do not establish
Siena detector performance or submission readiness.
