# REM induction from activity at laser onset

Existing project: `PAPER-SCOPE-20261114-REM-DYNAMICS`.
Finite endpoint: Figure 5e of *Low-dimensional population dynamics in the brainstem gate REM sleep*, DOI `10.1038/s41593-026-02314-z`.

The scientific question is whether population activity at the onset of stimulation of dmM GAD2 neurons distinguishes trials followed by REM sleep within 60 seconds. The published eligible cohort comprises 45 laser trials from five mice, all in NREM at laser onset: 20 successful and 25 unsuccessful. Preserve every eligible trial and its mouse identity. Do not add vM stimulation trials or the spontaneous-transition Figure 2h analysis.

## Historical reproduction condition

Reconstruct the paper's analysis from the admitted paper and data. In the official-code condition only, the same material is supplemented with admitted official source. The scientific specification, inputs, held evaluation support and resources must otherwise match. No authentic candidate packet is assembled by this component.

For each of PC1 through PC22, use its activity at laser onset as the LDA feature. The article describes randomly selecting 70% of trials across all mice for training and the remainder for evaluation, repeating ten times for each PC. Deliver a binary prediction for every test trial of every owner-issued PC/repeat split. Use exactly the owner-issued `public_plan` and its canonical SHA-256. Splits may differ across PCs. Never silently balance the 20/25 cohort, choose the best PC, discard a repeat, change a trial's label or substitute training-set predictions.

The owner must first recover the actual trial census, annotations, split rounding and selected split realization. Neither a seed invented for this component nor a hash of a local split file establishes equivalence to the author's historical run. The schema accepts 31 or 32 training trials to represent the unresolved rounding; this is not evidence that either is the original choice. Without recovered original splits, results must be described as a declared reconstruction of the article's procedure. The retained code file has no LDA or train/test-split entry point. Exact author preprocessing, PCA, classifier implementation and dependency closure remain unresolved.

The original whole-recording scaling, centered smoothing and PCA are historical reproduction choices, not proof of past-only prediction. Declare the preprocessing actually used. Do not claim prospective prediction simply because the classifier uses a laser-onset feature.

The evaluator independently recomputes each confusion matrix and accuracy, then mean accuracy, sample SEM and a one-sided one-sample t statistic against 0.5 across the ten repeats for each PC. The article reports Bonferroni correction but the exact correction family has not been recovered from the reference implementation. The owner must leave `bonferroni_factor` null until independently resolved. An explicitly bound factor is multiplied by the raw p value and capped at one; it never establishes source parity. Zero sample variance produces an explicitly undefined t test, not fabricated confidence. Ten repetitions are computational repetitions, not ten biological replicates. No population-level mouse inference is implemented here.

Do not optimize toward a particular published p value, manipulate seeds, or choose tolerances after seeing results. The evaluator has no binary research-pass threshold and does not compare your output with an unqualified published scalar. Published anchors are context for reproduction, not private grader targets.

## Separately proposed prospective condition

This is an assistant-proposed extension within the same project, not the Figure 5e statistic. Predict the probability of REM within 60 seconds for every admitted trial, using only information available at laser onset under a separately admitted held-mouse and earlier-calibration protocol. The owner must establish that all original 45 trials have permissible prospective support; otherwise this exact endpoint is unavailable rather than shrinking the cohort. No historical reproduction workspace, learned representation, transcript, outcomes or full-recording preprocessing may carry into this condition.

The primary loss is the mean of five per-mouse Brier losses; each mouse receives equal weight. Pooled trial Brier loss and per-mouse class-conditional losses are separate diagnostics. A class absent from a mouse is reported with count zero and null conditional loss; it is not fabricated or dropped from the overall score. The scorer does not fit models, construct causal inputs, enforce sandbox isolation or establish that a submitted probability was generated without future information. Those are runtime/protocol responsibilities that remain unqualified.

Paper+data and paper+data+official-code access are conditions of one task. The 22 PCs, ten repeats, 45 trials and alternative evaluation profile create no extra registered benchmarks. This source-only component establishes neither an LLM result nor novel scientific improvement.

## Machine interface

Use Python 3.11 or later, standard library only. Example invocation:

```sh
python3 -I -S -B score.py /owner/private-owner.json /candidate/predictions.json
```

The tool writes one JSON report to stdout and exits zero on valid complete predictions. Invalid inputs produce a refusal JSON with exit code 2. It reads two ordinary single-link JSON files, each at most 2 MiB; it does not import candidate code or deserialize pickle. The owner object and its targets stay outside the candidate environment. `public_plan(owner)` creates an outcome-free support description; a neutral operator must supply that description and its hash to both conditions. This helper does not create a full candidate package.

Consult `INTERFACE.md` for the exact fields and generated `test_score.py` for examples. Fixture cohort identities, splits, targets, provenance hashes and predictions are fabricated controls and must never be used as paper evidence.

## Assessment feedback boundary

All scorer reports, including refusal details, confusion counts and per-mouse losses, stay owner-only until every submission in the complete assessment is frozen. Do not return intermediate scoring feedback to a candidate or permit adaptive grading queries. Repeated queries can expose outcomes even when the owner input file is never mounted. Any deliberately interactive variant requires separate leakage analysis and cannot inherit this protected-evaluation claim. This source scorer does not enforce that release policy.
