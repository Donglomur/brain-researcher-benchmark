# NEURAL-022: active-to-passive velocity transfer

Write a Python program that predicts the two-component mean hand velocity for
all 92 supplied trials. The program runs as
`python -I /program/program.py --input /input --out /output`.
Write `/output/predictions.json` (at most 65,536 bytes):

```json
{"schema":"neural022_predictions_v1","predictions":[{"id":"<opaque ID>","velocity":[0.0,0.0]}]}
```

Include every ID exactly once, in `cases.json` order. Every velocity must contain
two finite, nonboolean numbers. The example shows the row format; a submission
must contain all 92 rows. Extra fields, missing rows and reordered IDs are invalid.

The available files are:

| File | Contents |
|---|---|
| `training.npz` | 141 labeled active trials: `ids` (141 Unicode IDs), `counts` (141×390 integer counts), `velocity` (141×2 nominal m/s), `directions` (141 integer commanded directions). |
| `queries.npz` | All 92 queries: `ids`, `counts` (92×390), `directions`, and `modes` (`passive` or `active`). No query velocity. |
| `cases.json` | The same ordered IDs, modes and commanded directions. |
| `TASK.md` | This contract and the fixed comparison results below. |

Load NPZ files with `allow_pickle=False`. Feature columns are six consecutive
20 ms bins, each containing all 65 units in fixed source-unit order. Use
`counts.reshape(-1, 6, 65)` to recover the bin/unit axes. There is no added lag,
smoothing, interpolation or dropped unit. The target is the mean of 120 native
1000 Hz two-dimensional velocity samples in the same half-open 120 ms window.
Velocity uses the recorded NWB 2.4.0 nominal conversion, raw×0.01+0, in m/s;
this is not independently calibrated sensor accuracy.

Fit and select transformations using active training labels only. Commanded
direction and query mode are permitted context. Passive training labels, query
behavior, source-row/event tables, support masks, the raw NWB and fixed reference
prediction arrays are unavailable. Network and external data are unavailable.
Query-dependent fitting/normalization and transductive fitting are outside this
declared method policy. The batch interface exposes all query inputs: valid output
alone does not certify compliance with that policy or establish method provenance.

The primary score is mean **squared Euclidean velocity error** over all 40 passive
queries: mean of `(pred_x−target_x)^2 + (pred_y−target_y)^2`, in (m/s)². Lower is
better. All 52 active queries and all eight directions within each mode are also
scored. Weighting is by trial, not an unweighted mean over directions. Every valid
finite table is graded, including predictions worse than the baselines. Extreme
finite values whose loss cannot be represented produce an explicit numerical
failure, never a clipped or favorable score. Invalid submissions receive no
subset score and are rejected before private target/reference bodies are read.

The signed primary comparison is **candidate passive loss minus fixed
passive-neural loss**; negative means the candidate has lower loss. That reference
was legally trained on 131 private passive labeled trials, a different calibration
allowance. The candidate remains `candidate_program` and is never renamed
`active_neural`, regardless of its algorithm.

The seven unchanged references were already fitted, committed and scored on this
same exposed cohort. All signed candidate comparisons remain visible:

| Fixed reference | Passive loss | Active loss |
|---|---:|---:|
| Active neural ridge | 0.048640404072381994 | 0.005640780666644063 |
| Passive neural ridge | 0.009045253242801947 | 0.03853784743217329 |
| Active training mean | 0.04934482273869313 | 0.03169065474012643 |
| Passive training mean | 0.04543882669357442 | 0.035008002363877425 |
| Active direction template | 0.009621646524091058 | 0.0012442110882261445 |
| Passive direction template | 0.0007483796911279814 | 0.01095611863691003 |
| Zero velocity | 0.04584302994526888 | 0.034052795158179494 |

The original fixed active-neural minus passive-neural passive-trial contrast was
+0.039595150829580046 (m/s)². It is a separate historical reference diagnostic,
not the score of an arbitrary submitted candidate. The strong direction-only
controls show why a neural-information improvement cannot be inferred from
beating only a mean or zero predictor.

This is one exposed Han animal/session and the complete publisher training and
validation split: 141 active/131 passive training trials and 40 passive/52 active
queries, all eight directions. Timing is retrospective and uses behavior-derived
movement onset; onset precedes the perturbation marker in 23 of 40 passive
queries. This is not online forecasting, perturbation-aligned causal inference,
animal-level replication, a reproduction of the original whole-arm encoding
paper, a protected test, an LLM capability evaluation, or a SOTA claim.

The prospective reused runner allows 20 seconds of candidate compute inside a
70-second candidate lifecycle, an 80-second grader phase, and 210 seconds for the
whole attempt (180 work plus 30 cleanup). Those are future runtime limits, not a
grant or evidence that this route has executed. The candidate has 1.5 CPUs and
3 GiB memory within a 2 CPU/4 GiB aggregate ceiling; it has only the four read-only
public files above and a bounded output directory.
