# Development difficulty pilot — November 17, 2026 UTC

**Historical calibration:** the four paper attempts below measure numerical
reconstruction. They do not satisfy the current same-task source-paper improvement
objective and establish no paper-improvement or current-SOTA success. The original
results and scope remain unchanged as calibration evidence.

Eight fresh agents completed and scored authentic-data attempts. Both paper
endpoints were reconstructed in under four minutes with detailed method assistance.
The neural programmes improved the primary metrics over fixed references, with
an EEG log-loss tradeoff and one exploratory sleep-attempt sequencing deviation.
These are eight attempts
on four existing endpoints, not eight new benchmarks or a qualification of the
234-task collection.

## Design

The two paper tasks compare paper + data + shared numerical method instructions
with the same packet plus selected official code. Each condition has one solver.
The neural tasks each have two independent attempts under the same feature-program
condition. Sleep staging additionally supplies the same pretrained YASA outputs
to both solvers. This is not a comparison of programme writing with case-by-case
investigation, or a test of no-tools LLM signal understanding.

Each solver starts with a fresh context and a candidate-only packet. It has a
15-minute authoring budget, including its own computations, existing local Python
tools, and no network, installations, paid model API, reference answers or grading
feedback. Training model selection uses training participants. All required
development observations must receive predictions. Producers finish before their
submissions are captured and graded; neither member of a pair receives feedback
while the other is working. Scoring errors and candidate failures are recorded
separately. No candidate revision after private scoring is allowed.

The agents run through the built-in subagent interface with fresh contexts and
the same inherited configuration, without model or reasoning overrides. The tool
does not expose an exact served model version, token usage or dollar cost. No
paid model API was called. Runtime and authoring time are distinct; authoring
timestamps begin with each agent's first recorded clock observation and omit
unmeasured dispatch overhead.

Access restrictions rely on protocol in a shared, unrestricted filesystem. They
are not a security boundary. Requested CPU and memory limits and preserved logs
do not establish a qualified execution sandbox. Therefore these are trusted
development artifact trials, not protected evaluation results.

## Results

All eight dispatched attempts produced complete, numerically scoreable submissions.
There were no authoring timeouts or omitted attempts. Numerical validity is
distinct from protocol compliance and scientific success. Exact aggregates,
per-person neural scores, all fixed comparator values and artifact identities are
in the [machine-readable summary](difficulty-pilot-20261117.json).

| Endpoint | Paper + data + shared method | Same + official code | Observed authoring time |
| --- | --- | --- | --- |
| TMS–EEG fixed regions | Fidelity score 1.0; all seven component losses zero | Fidelity score 1.0; all seven component losses zero | A: 138.3 s; B: 92.9 s |
| Purkinje morphology | Branch-length RMSE 2.26799 × 10⁻¹¹ µm | Branch-length RMSE 2.26799 × 10⁻¹¹ µm | A: 207.0 s; B: 209.6 s |

TMS submissions each matched all 4,320 graded numerical fields exactly. Distinct
programmes produced byte-identical submissions. Purkinje submissions covered all
10 cells, 13 components, 21,116 branches and 12,603 retained sections, with no
topology, missingness, integer or flag mismatches. Its separate numerical
diagnostics were also small: the largest aggregate-length error was
4.87198 × 10⁻⁸ µm, and all 58 summary diagnostics were present. These observations
support low implementation difficulty for these two strongly specified endpoints.

Sleep staging produced the following results on both complete development people:

| Attempt | Mean macro-F1 | Difference from YASA | Difference from random forest |
| --- | --- | --- | --- |
| 1 — exploratory sequencing deviation | 0.75997 | +0.02814 | +0.17988 |
| 2 | 0.78025 | +0.04842 | +0.20015 |
| Frozen YASA baseline | 0.73183 | — | — |
| Frozen random forest baseline | 0.58009 | — | — |

All 5,450 submitted epochs were scored in this panel. Attempt 1 improved the mean
but declined relative to YASA on one person; attempt 2 improved on both people.
Both programmes used the supplied pretrained outputs. The gains are descriptive
development improvements, not SOTA or population claims.

Sleep attempt 1 generated an initial set of development predictions before
refining its method on training-only validation. The agent preserved the earlier
source, predictions and logs, and reported no development-based selection or
private feedback. Nevertheless, this deviates from freezing the method before
the first development prediction. Retain its score as exploratory; do not count
it as strict prospective method-freezing evidence. Attempt 2 is reported
separately rather than silently pooling the two.

The visual-oddball EEG result has a clear metric tradeoff. Balanced accuracy is
the frozen primary metric; lower log loss is better for the secondary metric.

| Programme/reference | Mean balanced accuracy | Mean log loss |
| --- | --- | --- |
| Agent attempt 1 | 0.64531 | 0.61048 |
| Agent attempt 2 | 0.65156 | 0.57757 |
| Frozen EEG reference | 0.56406 | 0.59022 |
| Frozen EEG + history reference | 0.55781 | 0.58687 |
| Frozen ocular-site reference | 0.49531 | 0.51843 |
| Frozen gross-amplitude reference | 0.50000 | 0.48628 |
| Frozen history reference | 0.50000 | 0.50152 |
| Frozen prevalence prior | 0.50000 | 0.50040 |

Both agents beat all six references on balanced accuracy. Both were worse than
the prevalence prior and gross-amplitude reference on log loss; attempt 1 was
also worse than the EEG reference. This is improved classification at the fixed
threshold, not uniformly better probabilistic prediction. The references are
authored development comparators, not a claim to published SOTA.

Neural authoring took 417.0 and 568.4 seconds for EEG, and 308.6 and 378.3 seconds
for sleep. They used participant-grouped training validation to select
regularized models, tree models, transformations and ensembles. Their tuning
scores are not reported as independent performance estimates; the tables above
come from the separate development scoring after closure.

The observed paper-task time difference is not an estimated code-access speed benefit.
There is one pair per task, unmeasured dispatch overhead, and one TMS attempt
encountered an unsupported macOS resource-limit call. Both Purkinje agents also
logged unsupported hard-limit setup. They retained their failures and completed
the trusted runs without private feedback.

## What the selected tasks measure

- **TMS–EEG fixed-region reconstruction** (`PAPER-paper-signal-add-021`): all
  12 regions, 36 effects and 540 leave-one-position-out summaries from the
  complete accepted derivative. The task supplies the reduction, inference and
  randomization rules. Pairing follows the declared source-position order, not a
  newly verified person mapping. It does not reproduce the paper's primary cluster analysis.
- **Purkinje morphology** (`PAPER-FIND-REP-013`): all ten released trees and
  13 components, graph branches, both annotated-caliber conventions and specified
  descriptive summaries. Both arms receive source-informed numerical rules and
  exposed author Sholl totals. This is a source-reconciliation endpoint, not
  whole-paper or donor-level scientific confirmation.
- **Visual oddball EEG** (`NEURAL-077`): six training people and two separate
  development people, with 400 development trials. EEG features and permitted
  ocular, amplitude and past timing features are available. A strong score alone
  cannot establish that the programme used a particular neural mechanism.
- **Whole-night sleep staging** (`NEURAL-007`): six training people and two
  development people, with all 5,450 development epochs submitted. The private
  scorer applies unknown/movement masks after complete admission. Features and
  shared pretrained model predictions are available; reusing those predictions
  is permitted and must be compared with their fixed baseline.

## Interpretation limits

Tasks were selected for authentic input and grader availability, not sampled
randomly from the inventory. Neural evaluation uses previously exposed
development participants. One paper pair and two neural attempts per endpoint
cannot establish a code-access effect, a model ranking, population performance
or the difficulty of the whole collection. There is no invented scientific pass
threshold: report the existing numerical losses and prediction metrics, along
with all frozen baseline comparisons.

Detailed method assistance is part of the tested condition. Successful execution
under that assistance is useful reproduction evidence, but does not demonstrate
independent analysis design, identifying a new mechanism or improving the research
frontier. Those require separately specified tasks and untouched evaluation data.

Keep these tasks as method-assisted reconstruction checks. A harder scientific
reasoning condition should target a paper-native claim whose method is recoverable
from the provided materials, require analysis choices and robustness evidence, and
score improvement on untouched data against competent fixed baselines. Simply
withholding benchmark-specific conventions would create ambiguity rather than
meaningful scientific difficulty. Do not change this pilot's tasks or scoring
after observing its results.

## Operator defect found during preflight

The EEG scorer initially failed source authentication: its worker had a published
bookkeeping correction while the historical source freeze still named the earlier
worker. The correction counts an attempted private-target read before a pin check
can fail; successful scoring, target identities and metrics are unchanged.

Before inspecting solver outputs, the pilot selected an isolated copy of the exact
historically frozen release. All original source and asset pins were retained,
and independent review verified the counter-only difference. Failed pin checks
under that historical worker must remain operator errors; its attempt counter
can undercount a failed read. This route does not excuse or bypass a pin mismatch.

The public repair adds a separately identified current source descriptor while
preserving the historical freeze. Ten source-integrity regressions and fourteen
existing generated adapter tests passed; scoring formulas and data admissions
were unchanged. These software checks are separate from the authentic solver
attempts reported above. Source consistency alone does not supply missing assets
or qualify a relocated deployment.

Raw data, hidden targets, numerical submissions and local operator receipts are
kept outside this public report. The public result summary records aggregate
outcomes and immutable artifact identities without distributing those bodies.
