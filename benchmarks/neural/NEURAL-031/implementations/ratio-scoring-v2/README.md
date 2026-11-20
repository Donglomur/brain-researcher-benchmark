# Cancellation-preserving ratio scoring

This successor repairs the arithmetic mean used by NEURAL-031's existing
follow-up-volume/baseline-volume endpoint. All eligibility rules, schemas,
1,143 rows, 774 requests, 731 observed targets, 20 mouse folds, absolute MAEs,
paired-gain sign and equal-mouse weights are preserved.

The v1 scaled mean divides each value by the largest magnitude before adding.
For mouse gains `[1e308, -1e308, 1e-300] + [0.0] * 17`, the final gain is
representable (about `5e-302`), but the small term underflows during scaling and
v1 returns zero. Version 2 accumulates the exact binary-float inputs with
standard-library `Fraction`, divides by the unit count, and rounds to float
once. This preserves cancellation and avoids an overflowing intermediate sum
for near-maximum positive MAEs. The final float conversion retains ordinary
floating rounding; it does not invent a positive floor or change the estimand.

The API remains `endpoint.score(support, bundle, targets)` and the operator CLI
remains `score.py --support ... --submission ... --targets ...
--targets-sha256 ... --output ...`. All public predictions are validated before
the unchanged CLI opens targets. Keep the result and target metadata private.

`test_endpoint.py` has four new generated methods, including the complete
20-mouse score path with deliberately cancelling gains. Its independent
Decimal oracle starts from exact supplied binary floats. It also checks order
invariance, near-maximum positive means and exact cancellation. Run
`python -I -B test_endpoint.py` with the standard-library Python environment.
During private source staging only, `NEUROBENCH_SOURCE_ROOT` can identify the
read-only repository containing v1 for the preserved regression comparison.

The preserved [v1 package](../ratio-scoring-v1/README.md) and its
[SOURCES.json](../ratio-scoring-v1/SOURCES.json) remain unchanged. The existing
paired-executor and runtime-qualification bundles pin v1 and are not silently
retargeted. This package has its own source-control command and usable scorer;
future participant-runtime adoption must update that route's source bindings
and relevant controls. Source registration alone does not qualify a runtime.
No original target, native operation, model or neural-understanding result was
used or produced. Source authentication, isolated paired delivery, fitting
lineage, elapsed-time interpretation and scientific qualification remain open.
