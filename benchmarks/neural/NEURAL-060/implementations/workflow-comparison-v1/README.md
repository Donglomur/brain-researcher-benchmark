# Full-cohort workflow comparison

The protected NEURAL-060 grader reports the two workflows separately. This
command makes their paired comparison usable: it reads one complete
`neural060_full_score_v1` output, admits all 30 candidate/reference panels and
their exact original 29-session, 13-mouse and 7-lab supports against the pinned
public source roster, then reports
**frozen-program minus session-adaptive-tool joint loss** for each of the three
authoring replications. Positive differences favor the adaptive workflow;
zero and negative differences are retained. MSE is the original primary and
MAE is descriptive. The original nuisance and shifted-neural arms must be
present, even though neither is substituted for the joint endpoint.

```sh
python3 -I -B compare.py \
  --roster /absolute/repository/benchmarks/neural/NEURAL-060/contracts/delivery/REQUIRED_SOURCES.json \
  --score /absolute/protected-readback/SCORE.json \
  --score-bytes EXPECTED_BYTES \
  --score-sha256 EXPECTED_SHA256 > WORKFLOW_COMPARISON.json
```

Use the exact score identity from the operator's protected grading receipt.
The result records that identity. A hash proves which bytes were compared;
this command does not establish who produced them, valid model execution,
equal information/compute budgets, or protected-grader admission. It opens
only the named score and the fixed public source roster; it has no target, dataset, provider, model, environment
or execution-authority operand. The score is bounded to 16 MiB and read once
from an ordinary stable file. No other source tree is imported.

The tool subtracts the scorer's serialized metrics with 80-digit decimal
arithmetic. It preserves the existing overall equal-mouse values and returns
all 13 paired animal values, all 29 session differences and all seven lab
differences. Before comparison it checks every panel's session-to-mouse,
mouse-to-lab and equal-mouse aggregates, original primary joins and original
arm contrasts. Propagated binary64 rounding bins
(including subnormal values and shortest decimal serialization) plus an
80-digit decimal arithmetic bound accommodate independent serialization.
This is a rounding consistency check, not a scientific significance threshold or proof of provenance. It does not recompute an overall score by pooling sessions,
trials, samples or laboratories. Because the upstream scorer serializes
ordinary numbers as binary64, differences describe those serialized values;
they are not a recovery of unrounded internal metrics. Overflow/underflow
values supported by the upstream score remain decimal strings.

The replications are kept separate. They are not 39 independent animals and
the command adds no confidence interval, statistical test, training/authoring
uncertainty estimate or inferential decision. Its output always retains
unqualified neural contribution, unqualified reference competence and no
causal or native-understanding claim. The two implemented workflows concern
program building and adaptive tool use. Neither is direct observation or a
restricted viewer, and this comparison does not supply either missing mode.
The authentic full packet and qualified execution remain prerequisites for
scientific use. Generated score fixtures establish arithmetic and admission
behavior only.

Run the affected source controls with standard-library Python:

```sh
python3 -I -B test_compare.py --repository /absolute/current/repository --scratch /absolute/owned/scratch
```

These controls check a complete unequal-session hierarchy, all three
replications, adverse and null effects, numeric extremes, primary identity,
full panel and paired support, duplicate/nonfinite input refusal, and the
actual pinned-file command path. They use no recordings or estimator fits.

This component does not alter the retained full runtime, its historical
source pins or the current-layout materializer. Publication should register
this component and enroll its test as a separate source check; it must not
replace or promote the protected grader or any native qualification receipt.
