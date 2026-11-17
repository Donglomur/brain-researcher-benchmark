# Intracellular DSR evaluator

Concrete construction source for `PAPER-paper-method-009`: Pala MATLAB ingestion,
20 kHz spike detection/interpolation, held-trial voltage-to-rate fitting at both
25 and 50 ms, operational-time CV², and the exact pinned DSRP spike estimator.
Reports per-neuron paired irregularity/fractions and segment stability with
mouse identities retained.

Requires Python 3.10+, NumPy, and SciPy already available in the environment.
From this directory:

```sh
python evaluator.py --mat /approved/data.mat --plan /approved/plan.json --output /approved/report.json
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The CLI verifies the source-recorded data checksum and requires an explicit
prospective split plan. It downloads nothing. The tests use bounded generated
controls; no authentic reference or scientific qualification is established.
Unresolved 25/50 ms, spline, source-cohort, and twenty-segment reconstruction
details remain visible. Native DSRP code is unmodified and retains its MIT
license in `third_party/LICENSE`.

See the [complete input contract, policy choices, and limits](../../docs/initial-evaluator-v1.md)
and [source provenance](provenance.json).
