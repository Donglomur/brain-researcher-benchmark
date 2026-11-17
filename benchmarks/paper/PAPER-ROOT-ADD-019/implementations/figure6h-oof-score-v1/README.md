# Figure 6h out-of-fold endpoint

This component computes the original Figure 6h statistic from complete frozen prediction records: per-session `100 * (1 - min(error))` over 11 settings, followed by an **equal-weight mean across 18 sessions from eight rats**. It adds a prediction-based scorer for the source-grounded reaction-time subtask identified in `improvement.v1.json`. The existing Figure 3 timing grader and historical 37-root/four-head implementations are preserved.

No authentic preparation, MATLAB execution, author reproduction, candidate run, or paper improvement is established. The exact cohort roster, original fold realization, published numerical baseline, native preprocessing and protected comparison remain unresolved. Eighteen sessions and eight distinct rat IDs are necessary checks, not authentication of the original roster. This component is not enrolled in the canonical scorer; enrollment and scientific qualification are integration proposals.

## What is scored

The operator supplies labels, ordered trial identities, tenfold assignments, original session/rat identities, unit counts and a preparation-evidence digest. Author and candidate records must match that exact manifest. Each session needs every setting and exactly one binary out-of-fold prediction per trial. Source labels are fast=1, slow=0; no probabilities, abstentions or missing trials are silently converted. No folds or labels are generated.

The author panel uses the pinned 11 ridge strengths `logspace(-4, -0.2, 11)` in order. Every setting's pooled trial misclassification fraction must agree with its exported native MATLAB `kfoldLoss` to absolute tolerance `1e-12`, including nonwinning settings. A mismatch stops scoring: this component does not assume that independently reconstructed losses equal native weighting semantics. Actual native parity is still untested. The exporter must retain `kfoldPredict` classes and all `kfoldLoss` values from the same fitted partitioned model; exporting new random folds does not recover the published run.

The candidate may use a different architecture. Its 11 setting identifiers are freely named and must be frozen before outcome access; using the same panel size is an explicit proposed comparison control, subject to operator admission. It does not authorize candidate fitting or select a model for the researcher. The scorer applies the source best-of-11 rule, resolving ties at the first setting like MATLAB `min`. This statistic reuses CV outcomes for selection and evaluation and is selection biased. It is not an independent test accuracy or nested-CV result.

The report retains all setting losses, integer errors, fold counts, selected indices, paired session deltas and rat clusters. Session SD and descriptive session SEM are separately labelled because source code plots SD while the paper caption says SEM. Neither becomes a biological confidence interval. No significance test, meaningful-effect threshold, winner flag or current-SOTA claim is invented.

## JSON interface

`score.py` uses the Python standard library. The operator-only manifest has exactly:

- `schema: "ach_fig6h_oof_manifest_v1"`, `task: "PAPER-ROOT-ADD-019"`, `preparation_sha256` and `sessions`.
- Eighteen session objects, each with `session_id`, `rat_id`, `unit_count`, ordered `trial_ids`, integer `folds` (1–10, each represented), and integer `labels` (0 or 1, both present).

Prediction bundles have exactly `schema: "ach_fig6h_oof_predictions_v1"`, `role` (`author` or `candidate`), `manifest_sha256`, `program_sha256`, `setting_ids`, and `sessions`. The author also supplies `lambdas`. `manifest_sha256` uses `score.digest(manifest)`: SHA-256 over compact, sorted-key UTF-8 JSON. This digest includes labels and must stay operator private. `program_sha256` binds the supplied program bytes; freezing/custody must be verified externally.

Each prediction session has the identical `session_id`, `trial_ids`, `folds`, and `predictions` (11 settings × retained trials). Author sessions additionally include 11 `native_kfold_losses`. Author setting IDs are `ridge_00` through `ridge_10`. `test_score.py` contains a complete **invented** wire example in `fixture()`.

```sh
python3 -I -B score.py --manifest /operator/manifest.json \
  --author /operator/author-oof.json --candidate /operator/candidate-oof.json \
  --output /operator/fresh-result.json
```

Outputs must remain operator private; the CLI refuses to overwrite an existing output. It does not launch candidate code or provision an isolation boundary. Schema/hash equality cannot prove that predictions were actually held out, code was frozen before label access, or source records are authentic. Those require the admitted execution and custody protocol. Reaction time and held-out labels must not be candidate inputs.

## Additional source defect retained

The exact cached author file matches SHA-256 `c963c8b204fee99ca40668a4651e90e0beab44ec4e986b9bb184e8cf93ff3f42`. Lines 79–81 create `y` from original trial indices, replace fast indices with 1, then test membership in slow indices on the already modified vector. If original trial 1 is slow, newly assigned fast labels equal that slow index and become 0. For fast mask `[false,true,true]` and slow mask `[true,false,false]`, literal source produces `[0,0,0]` while mask semantics produce `[0,1,1]`. `audit_source_labels` reproduces both and reports changed original trial indices without choosing or applying a correction. Whether this occurs in any authentic session is unknown.

The already reported `thres`/`thresh` discrepancy at lines 60–64 also remains: assignment to element 2 of the initially empty `thresh` makes element 1 zero under MATLAB array expansion, rather than the separately assigned first-percentile `thres(1)`. No corrected preprocessing is called the historical baseline. Resolve these issues, inclusive-quartile ties, session identities and random folds before admitting a native comparator.

## Verification and remaining work

The small controls exercise actual CLI serialization, nonwinning native-loss mismatch, unequal fold sizes, equal-session versus pooled-trial aggregation, selection/ties, rat pairing, the source label collision, malformed predictions, incomplete panels, duplicate JSON keys and output preservation. Run them only through the shared two-slot test pool under the delegated resource policy.

Next qualification needs the authenticated full 18-session/eight-rat preparation and original source/fold evidence; an explicitly reviewed resolution of preprocessing discrepancies; an isolated same-model export proving every native loss; frozen candidate/comparison budgets; and predeclared effect and rat-dependent uncertainty. Figure 3 timing and whole-paper causal demixing remain separate obligations. No replacement task, easier split or smaller cohort has been introduced.
