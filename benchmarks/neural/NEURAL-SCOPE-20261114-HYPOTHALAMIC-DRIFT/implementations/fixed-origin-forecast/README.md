# Hypothalamic drift: fixed-origin forecast scorer

This is the accepted V3 numerical component for the existing
`NEURAL-SCOPE-20261114-HYPOTHALAMIC-DRIFT` task. It scores complete forecasts for
1,661 cells from 31 mice in five groups, issued after session 9 for all sessions
10–21 and wake/NREM/REM. It supplies no data, reference fit, submitted-program
executor or protected deployment. Publication adds no benchmark or qualification.

`scorer.py` and `test_scorer.py` are unchanged accepted project source. Python
3.11+ standard library on Unix is sufficient; no packages or network are needed.
The API is `score(prediction, targets, comparator)`. See [INTERFACE.md](INTERFACE.md)
for every JSON field, group total, mask rule and aggregation denominator.

From this directory, an operator can grade independently authenticated inputs:

```sh
umask 077
python3 -I -S -B scorer.py \
  --prediction SUBMITTED.json \
  --targets OWNER_TARGETS.json --targets-sha256 OWNER_TARGET_SHA256 \
  --comparator OWNER_COMPARATOR.json --comparator-sha256 OWNER_REFERENCE_SHA256 \
  --output NEW_PRIVATE_REPORT.json
```

Run inside an operator-owned directory with mode 0700. The operator chooses
protected paths and expected hashes independently of the candidate. The output
is create-only, but its permissions depend on the caller's umask; the command
above deliberately sets it. Reports include protected exposure/missingness and
reference information, so never expose stdout/error streams or reports as an
automatic contestant feedback channel. File-type and hash admission are not
process isolation or a time limit. Preserve any partial output after failure.

The target is log1p(events/minute) on already qualified stable-bout exposure of
at least 20 seconds. Squared error is averaged equally over eligible sessions,
then states, neurons, mice and all five groups. A wholly unsupported group makes
the primary undefined. Reference minus candidate loss uses identical support.
Acute/chronic diagnostics remain separate. This prospective forecast equation
is not a published forecasting-result reproduction claim.

Authentic full-cohort identities, longitudinal ROI correspondence, event and
clock/mask producers (including the unresolved MCH threshold), strongest
train-only comparator selection, protected fixed-origin exposure, mouse-level
uncertainty and actual runtime remain unqualified. Hash-shaped receipts do not
establish those facts. Retrospective ROI tracking is conditional side information.

Run only the relocated generated interface checks from this directory:

```sh
python3 -I -S -B test_delivery.py
```

They verify the complete local member set, a real isolated CLI invocation on
invented full-support inputs from a different working directory, private report
permissions under the documented umask, and fail-closed public admission. They
do not replay the existing scientific test campaign or use authentic observations.
The unchanged `test_scorer.py` remains available for deliberate future regression
work. `COMPONENT_SOURCE.json` pins all other local members; `SOURCE_BINDING.json`
identifies the accepted source and private review without exporting that review.
Project code/docs use the repository MIT license; no external asset rights are granted.
