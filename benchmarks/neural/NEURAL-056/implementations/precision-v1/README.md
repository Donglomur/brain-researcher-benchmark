# NEURAL-056 Pearson precision repair

This task-local successor repairs finite-precision correlation in the existing
image-to-EEG scorer. It is executable operator scoring source, with generated
software controls. It does not establish authentic preparation, model performance,
an admitted runtime, or scientific qualification.

The preserved predecessor divides each vector by its largest absolute value
before subtracting its mean. With a large common offset and small representable
variation, that division and subsequent centering can alter the Pearson score.
The regression fixture uses 100 copies of `1e308` and 100 copies of the next
representable larger float, predicted by a two-level indicator. Its mathematical
correlation is exactly one. An independent 1,500-digit Decimal oracle converts
the input floats exactly; it does not reuse either vectorized algorithm.

The new kernel subtracts one observed value before scaling. For the exceptional
columns whose opposite-sign differences overflow, it first halves the values.
It then uses power-of-two scaling, centers the bounded differences, and computes
the ordinary Pearson coefficient. No tolerance classifies cells as constant.
Exact constant predictions still score zero with undefined raw correlation;
any exact constant target still makes the full primary mean undefined.

`n056_precision.evaluation.grade` retains the predecessor's real `collect`,
`paired_lifetime`, `prediction`, NPZ parsing, immutable artifact checks, and the
120-output barrier before any target callback. The new aggregation preserves all
200 images × 17 released coordinates × 100 time samples for every person, three
arms, four roles, equal-person means, participant-paired control effects, and
separate uncorrected odd/even reliability. It also checks private target axes
before reshaping. `development` uses the repaired kernel over all nine inner
people and three arms, and rejects mixed outer-person records before scoring.

## Use and dependency

Put this directory and the preserved shared package on the Python import path:

```text
benchmarks/neural/NEURAL-056/implementations/precision-v1
benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/authoring/delivery-20261105/common/remaining-builds-wave37/neural056-complete-program/successor-v3/package
```

Then call the same operator API with the same panel, completed records, protocol,
and budget objects:

```python
from n056_precision.evaluation import development, grade

# Existing authenticated operator objects; never candidate-supplied targets.
result = grade(panel, records, protocol, budget)
```

The shared source remains unchanged. This component does not select itself in the
existing whole-program runner or change the registration. Integration must select
the numerical successor explicitly and retain its revision in the result; old
numerical results remain historical. The original legacy numerical reconciliation
must treat the documented precision regression as a versioned arithmetic change,
while retaining endpoint, admission, and ordinary-input agreement checks.

The kernel accepts finite float32/float64 matrices and returns the predecessor's
`raw`, `score`, `constant_target`, `constant_prediction`, and `mean` fields. The
study result adds `numerical_revision: neural056-pearson-precision-v1` without
changing its scientific metric. Required dependencies are NumPy and the existing
standard-library-only source admission path; no package installation is needed.

## Verification and scope

Run `tests/test_precision.py` through the approved shared test pool. Tests include
the exact decimal regression, opposite-sign extremes, subnormals, ordinary full
support parity, power-of-two/sign invariance, constants, nonfinite and malformed
inputs, real NPZ/custody admission of 120 generated records, equal-person/control
aggregation, corrupt final output and incomplete-roster refusal before target
access, constant-target propagation, and target-axis rejection. Generated process
completion records test software contracts; they do not qualify actual process
isolation, train/query execution, or biological data alignment.

All 14 controls passed in pool run `neural04-n056-precision-002` using the existing
Python 3.12.8 / NumPy 2.4.6 environment. The exact regression measured predecessor
`0.7071067811865475`, Decimal oracle `1.0`, and successor `1.0`. Measured child CPU
was 2.742571 seconds, and peak child RSS was 520,257,536 bytes. This is software
verification, not qualification of the source's specified NumPy 2.2.6 environment.
The first pool attempt was busy and launched no test process.

No source downloads, public or private EEG reads, checkpoint access, feature
extraction, model fits, provider calls, or scientific scores are part of this
change. The full 80-repeat target, nine-person training split, 200 unseen concepts,
all controls, and original exposed/transductive data limitations remain. This is
prediction-program scoring; it does not demonstrate direct neural interpretation
or reproduce the paper's random-half endpoint.

Source pins and the construction outcome are recorded in `COMPONENT.json`.


## Complete paired role comparisons

`grade` also returns `paired_role_comparisons` from the same admitted120 blocks.
It reports all six role pairs with fixed directions: I minus F, F and I each
minus the fixed and tuned references, and tuned minus fixed reference. Each
contrast retains ten named person differences for every arm and their equal-person
mean. `control_effect_differences` compares each role's representation-minus-control
effect within the same person before averaging. No coordinate or repeat is treated
as another person, and an undefined person propagates to the whole contrast mean.
The existing role scores, primary metric, within-role effects and descriptive
reliability remain unchanged. No extra target reads or participant products are
required. Comparisons occur only after complete artifact admission and scoring.

These are descriptive comparisons conditional on the ten exposed people and200
shared images. They neither provide population confidence intervals nor assert
equal actual spending, adequate reference performance, runtime isolation, or
scientific/native-neural understanding. F/I match at the original frozen-policy
and information/budget-ceiling level; actual costs must still accompany any later
qualified run. This component still requires explicit selection into a qualified
runner, with consistent development and final numerical versions.

`tests/test_role_comparison.py` exercises the real120-product admission path with
heterogeneous generated role/person/arm predictions, hand-computable signed paired
contrasts, incomplete/corrupt final-product refusal before target access, and
constant-target propagation without deleting a person. It is a software control,
not a scientific or model run. Set `NEURAL056_REPO` to the repository root when
running a staged candidate outside the repository.
