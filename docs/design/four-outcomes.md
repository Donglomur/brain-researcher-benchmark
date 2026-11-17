# Four scientific outcomes

This benchmark pursues four first-class outcomes across two tracks: **paper
reproduction, paper improvement, native neural interpretation, and neural
tool/model building**. Each scientific task keeps one task ID. Its applicable
outcomes, access conditions and executions are recorded separately; they are not
extra benchmarks.

This is the current design objective. It does not change existing task schemas,
silently replace scientific targets, authorize new runs or establish qualification.
The [current status](../status/README.md), [implementation guide](../usage/implementations.md)
and [registry](../../benchmarks/registry.json) describe what is actually delivered.

## What success means

| Track and outcome | Scientific question | Required distinction |
| --- | --- | --- |
| Paper reproduction | Can the participant faithfully recover the complete original result specified by the task, under declared source, data and evaluation conditions? | Agreement with a source result is assessed separately from superiority over it. |
| Paper improvement | Can the participant improve the source result on the same original task under fixed comparison conditions? | Method changes are permitted within the observation, evaluation and resource boundary; a different task is an extension. |
| Native neural interpretation | Can the participant infer the specified target directly from permitted neural observations or through the declared typed viewer? | Direct or viewer responses require their own evaluated evidence. A programme score cannot substitute for it. |
| Neural tool/model building | Can the participant create or adapt a tool, model, investigation procedure or frozen programme that solves the specified neural task? | Attribute the participant's contribution. Functional software controls, a developed artifact and scientific performance are separate claims. |

Each paper task needs separate reproduction and improvement outcome definitions.
Each neural task needs separate native-interpretation and building outcome
definitions. A missing source, unsupported target or undelivered condition remains
explicitly unavailable; an outcome label does not manufacture a feasible task.

## Paper reproduction

Reproduction is an independent success criterion, not only preparation for an
improvement attempt. The task must specify the original scientific result being
reproduced: a complete source endpoint or panel, its required companion results,
source versions, dataset and cohort, split, permitted inputs, preprocessing,
evaluation and aggregation. A convenient subset or changed endpoint cannot be
reported as reproduction of the larger result.

The agreement rule must be justified for that source result before evaluating
submissions. Numerical precision, stochastic variation, independent experimental
units and the paper's aggregation may matter; no universal tolerance or success
threshold is introduced here. The source result and its uncertainty must be
recoverable enough to support the claimed comparison. A descriptive result may
support reproduction even when an ordered improvement endpoint is unavailable,
but it still needs its own reviewed outcome definition.

Paper + data and paper + data + official code are access conditions, not different
tasks. A faithful independent implementation may be assessed in the first
condition; access to official code in the second does not itself establish
reproduction. Declare the condition, exact supplied materials and budget for every
attempt, and preserve disagreements and failed or incomplete runs. Compare access
conditions under matched participant and selection budgets; report any remaining
information or resource differences explicitly.

A qualified reproduced source method can also serve as the comparator for an
improvement assessment. Those are two uses of evidence, not two executions. Earlier
reconstruction scores, partial source probes and calibration artifacts do not
automatically meet the new complete reproduction definition.

## Paper improvement

Improvement asks for superiority on the same original task. Keep the allowed
observations, dataset, cohort, split, evaluation metric, aggregation and required
controls fixed. Candidates may change architecture, inference, optimization or
other permitted method choices within the declared observation and budget
boundary. The author recipe establishes the source result or comparator; it does
not force the improved method to copy the author algorithm.

The improvement rule needs a competent, adequately qualified comparator, a
justified effect criterion, appropriate uncertainty and the task's required
companion checks. A higher point score alone is insufficient. A published number,
a measured source-method result, a candidate result and verified current SOTA are
different claims. Surpassing the source paper does not by itself establish SOTA.

Reproduction and improvement must be reported separately even when an experiment
provides evidence relevant to both. Failure to improve does not negate a qualified
reproduction. A promising improvement score cannot repair missing source identity,
changed observations, leakage or an incomplete evaluation panel.

## Native neural interpretation and building

Native interpretation asks the participant to infer a scientific target from its
defined observation representation. Direct numerical or textual observations and
typed-viewer images are separate conditions. The contract must state what the
participant receives, which viewer actions are allowed, the demonstration budget,
whether feedback exists, and how fresh query context and response collection are
enforced. Typed viewing grants only the declared observation actions. Arbitrary
code, retrieval or external-model assistance belongs in a separately reported
assisted-investigation condition and cannot be credited as native interpretation.
All supplied preprocessing remains part of the declared observation representation.

Tool/model building permits the specified tools and computational methods. It can
include case-by-case tool-assisted investigation, model development or a frozen
prediction programme. Require an attributable participant-created or adapted
artifact or method, including a recorded investigation procedure where applicable.
Using a supplied fixed model alone is a reported access condition or comparator,
not evidence of a participant building that model. Bind allowed training and validation data, selection and
tool access, method commitment, resource use, output coverage and evaluation.
Working code or a completed prediction file is software evidence until the
scientific assessment and method provenance are established.

Both outcomes address the task's declared target, with meaningful controls and
comparators. Their information access may differ, so report those differences
before interpreting a comparison. For example, a programme trained with 1,200
labels is not an information-matched comparator for an observer receiving four
demonstrations. A tool-assisted score cannot be relabeled as native interpretation.
Likewise, native interpretation does not establish a reusable prediction system.

“Native interpretation” names the scientific outcome. A report of native runtime
execution or a native software control describes an implementation being exercised;
it does not establish this interpretation outcome. Image rendering, a scripted
viewer client and an author-model timing probe retain their engineering scope.

## Record outcomes without double counting

Keep the scientific task identity separate from outcome, access condition and
execution identity. A result should identify the task and outcome assessed, the
declared condition, the source/data/evaluation versions, the actual execution or
executions, the observed result and its scope, and any unresolved qualification.
These are reporting requirements, not a new executable JSON schema.

- One paper task with reproduction and improvement outcomes remains one task.
- Paper-only and code-assisted conditions, neural access modes, participants,
  folds, seeds and controls are not extra task IDs.
- If one execution supports multiple outcome assessments, each assessment points
  to that same execution. Do not count it as two runs.
- If an outcome requires multiple independently executed runs, retain their actual
  identities, costs, failures and dependence; a single summary is not a single run.
- Source preparation, software controls, author-model probes and participant
  attempts remain distinct evidence categories. Their counts cannot be added to
  produce a completed-benchmark count.

Outcome-specific qualification must not be inherited by another outcome or
condition. Changing a scientific target or task population requires an explicit,
reviewed revision or extension with preserved predecessors; changing a display
label does not create new evidence.

## Current implementation and transition

The current registry contains 117 paper and 118 neural task entries. All 117 paper
definitions now bind adopted outcome metadata: 66 normal reproduction/improvement
pairs, 49 unavailable complete-primary pairings and two source-declaration gaps.
The original definitions and improvement contracts remain preserved, with explicit
selectors for reviewed current policy successors. All recorded paper scientific
outcomes remain unknown. An unavailable complete-primary pairing does not make
independent reproduction scientifically impossible; each claim retains its own
source, scope and execution requirements. Improvement-contract dispositions are
separate from reproduction support and scientific success.

All 118 neural definitions bind current understanding contracts with separate
access-mode descriptions. Their delivered-source dispositions do not qualify
native interpretation or tool/model building. Task-specific proposals must connect
the two outcome definitions to the actual observations, controls and available
execution paths; unsupported modes must remain visible.

`paper-contract TASK_ID --outcome reproduction` inspects the explicitly selected
reproduction declaration where one is bound; `paper-outcomes TASK_ID` reports the
current paired-outcome metadata and remaining limits. `paper-contract TASK_ID`
inspects the selected current improvement contract where available.
These commands do not establish a reproduced finding or candidate improvement.
Historical paper `score` and `run` adapters still require `--calibration`; their
results do not automatically become qualified reproductions or improvements.
`neural-contract TASK_ID` describes the current target and access modes. Task and
runtime admission holds remain in force.

The eight historical pilot attempts remain four scoped paper reconstructions and
four neural programme attempts. Source-preparation receipts, native software
controls and scripted viewer collections retain their reported scope, dates and
limits. None is retroactively renamed into a qualified outcome.

Before admitting a new outcome, review its complete scientific definition, actual
source and input support, comparator and decision rule, allowed participant access,
and the execution evidence needed for that claim. Preserve the old definition and
negative findings. Report the four-outcome objective alongside delivered coverage
and remaining work, rather than treating design completion as benchmark readiness.
