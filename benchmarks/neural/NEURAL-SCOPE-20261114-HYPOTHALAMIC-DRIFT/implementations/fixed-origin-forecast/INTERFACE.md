# Hypothalamic scientific and JSON interface


The full declared cohort is five groups, 31 mice and 1,661 neurons:

| Group | Mice | Neurons |
| --- | ---: | ---: |
| LH-Vgat | 6 | 509 |
| LH-Vglut2 | 6 | 257 |
| LH-Hcrt/OX | 6 | 425 |
| LH-MCH | 7 | 28 |
| POA-Vgat | 6 | 442 |

The trusted manifest must enumerate every mouse and every cell. Neuron IDs are
unique within mouse; matching neuron names across different mice is permitted.
No hardcoded invented fixture identity is an authentic cohort identifier. Exact
per-mouse cell distributions must be authenticated upstream; the scorer checks
the registered group totals and every supplied identity, not unknown original
per-mouse counts. All 21 sessions and three states remain in the trusted support
manifest, including missing observations. The future output has every cell and
all 12 sessions 10–21, with no omitted state or missing value, even when a target
will be masked. Thus protected eligibility need not be disclosed to the model.

The order is session-major, then `wake`, `NREM`, `REM`. Sessions 1–9 are
calibration history, never protected test errors. From the fixed origin after
session 9, each forecast concerns a nonnegative events/minute rate represented
as its finite, nonnegative `log1p(rate)`. Negative, missing, Boolean and
nonfinite predictions are rejected; nothing is silently clamped. Future targets
must never update forecasts. The scorer verifies the complete output support;
it cannot attest when a program produced those numbers or what data it saw.

For an observed slot, the target is
`log1p(60 * event_count / valid_stable_seconds)`. A slot is eligible only if its
trusted valid duration is at least 20 seconds. These seconds must already be
restricted to artifact-valid portions of stable bouts whose qualifying original
duration is at least 20 seconds. An aggregate duration of 20 seconds assembled
from short, excluded bouts is not valid input. This scorer deliberately does not
reconstruct bouts, motion masks, traces, peaks or clock alignment. The producer
must qualify those transformations before its counts/exposures become trusted.

For each candidate and the frozen comparator, squared log-rate error is averaged:

1. Equally over eligible future sessions within a neuron/state.
2. Equally over states with eligible sessions within the neuron.
3. Equally over neurons with eligible states within the mouse.
4. Equally over mice with eligible neurons within the biological group.
5. Equally over all five groups.

Exposure duration does not reweight eligible sessions. Both predictions use the
same trusted mask. A missing state contributes no invented zero. A mouse without
eligible neurons remains in the report with null loss and zero denominator. If
any group has no eligible mouse, the primary is explicitly undefined; the scorer
does not renormalize over fewer groups. All per-cell exposure arrays and missing
reasons, state/session denominators, mouse/neuron denominators and group/mouse
denominators are retained in the private report. Acute sessions 10–12 and chronic
sessions 13–21 also have separately recomputed descriptive hierarchical losses;
these do not replace the primary across all eligible sessions 10–21.

Paired loss reduction is `reference_mse - candidate_mse`, at mouse, group and
overall levels; positive means lower candidate error on identical support.
Reference selection must be frozen using other-mouse fixed-origin validation
across the stationary, context and competent slow-drift models. This component
accepts one already selected reference; its name/selection receipt does not
prove competence or authorize an improvement claim. It supplies no pass floor,
bootstrap, preferred-state permutation analysis, causal conclusion or SOTA claim.
The sample unit for later uncertainty is mouse, not 1,661 independent neurons.

Arithmetic uses binary64. Means avoid ordinary positive-sum overflow; a squared
error beyond finite binary64 range refuses explicitly. Finite log values are
scored directly without exponentiating predictions. Count-to-log-rate conversion
has a log-space fallback when an intermediate rate overflows. No tolerance is
used to forgive biological errors; generated floating-point assertions only
allow ordinary numerical rounding in the analytic fixture expectations.

## Exact input interface

All objects use exactly the listed keys. IDs are nonempty strings of at most
128 characters without control characters. Receipt hashes are lowercase
64-character SHA-256 strings. No primary signal, reference body or actual mouse
identity is distributed with this source.

Prediction object:

```json
{
  "schema": "hypodrift-prediction-v1",
  "task_id": "NEURAL-SCOPE-20261114-HYPOTHALAMIC-DRIFT",
  "states": ["wake", "NREM", "REM"],
  "sessions": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
  "cells": [{"mouse_id": "IDENTITY", "neuron_id": "IDENTITY", "log_rates": []}]
}
```

The displayed shape is illustrative, not a valid reduced fixture: `cells` must
contain all 1,661 cells of all 31 mice, each with exactly 36 log-rate values.

Trusted target object has keys `schema` (`hypodrift-targets-v1`), `task_id`,
`states` (same order), `sessions` (integers 1–21),
`producer_receipt_sha256`, `cohort_receipt_sha256`, `mice`, `cells`.
Each of 31 `mice` has exactly `mouse_id` and `group`. Each of 1,661 `cells` has
`mouse_id`, `neuron_id`, `valid_stable_seconds`, `event_counts`,
`missing_reasons`; the last three arrays each have exactly 63 entries.

For an observed slot, seconds must be finite and nonnegative, count a
nonnegative integer (not Boolean), and reason null. Zero duration requires zero
events. Durations below 20 seconds are admitted as explicit underexposure but
are not scored. For an unobserved slot, both duration and count are null and the
reason is a nonempty string up to 512 characters. Unknown values cannot masquerade
as measured zero. Counts remain counts; calcium events are not direct spikes.

Trusted comparator object has exactly `schema` (`hypodrift-comparator-v1`),
`reference_id`, `selection_receipt_sha256`, and `prediction`, the latter obeying
the same complete prediction schema. Candidate and comparator IDs must exactly
match the trusted cohort. The three receipt identities and all three input-body
hashes are carried into the CLI report without claiming to validate their
underlying scientific evidence.
