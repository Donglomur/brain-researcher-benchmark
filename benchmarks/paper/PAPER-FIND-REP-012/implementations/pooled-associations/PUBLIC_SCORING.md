# Artifact assessment

This scorer assesses your submitted four-endpoint result artifact. It does not execute your analysis program or establish that the declared method was actually used. A complete benchmark run additionally needs a separately bounded candidate runner, provenance and access-condition audit.

All four endpoints always count. There are16 numeric checks (`r`, `p`, `paired_y_mean`, `paired_y_sd` for each endpoint),24 endpoint-support checks (four counts and two support digests per endpoint), and5 cohort checks. Abstaining contributes zero credit for that endpoint; missing slots make the artifact invalid. Wrong finite scientific values remain assessable and their errors are retained.

For each numeric field, tolerance is `atol + rtol * abs(reference)`. The r tolerance uses `(1e-9,1e-7)`, p uses `(1e-12,1e-6)`, and the two added outcome moments use `(1e-10,1e-8)`. These tolerances accommodate ordinary floating-point reconstruction of the supplied release; they are not caption-rounding intervals or significance thresholds. The reference is private and fixed independently of the submission.

Field credit is `1 / (1 + absolute_error/tolerance)`. The numerical score is the fixed16-field average. Support credit is the product of the fraction of24 endpoint-support checks and the fraction of5 cohort checks that match exactly. Overall score is numerical score multiplied by support credit. Full reconstruction additionally requires all four endpoints reported, every numerical comparison within tolerance, every provenance comparison exact and no scientifically inconsistent counts or r/p/SD domains.

Exact values receive maximal credit. Smaller p values or larger absolute correlations receive no special reward. Scores never establish improvement over the paper. The private reference targets the supplied processed release, with its acknowledged differences from the printed article; copied caption statistics are not authoritative outputs for this task.

Malformed JSON, duplicate/extra fields, missing/duplicate endpoint IDs, Boolean numeric fields and JSON NaN/Infinity have no numerical score. Unsupported task/version/input identity and scalars unrepresentable in finite binary64 are distinguished from incorrect science. A nonzero decimal token that underflows to binary64 zero is unsupported. Integral fields require literal integer tokens. An invalid private reference is an operator error, not a candidate failure.
