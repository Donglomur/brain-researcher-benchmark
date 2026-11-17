# CBraMod original endpoint arithmetic

This operator component computes the source evaluator's three metrics for each
of the complete twelve-dataset primary panel. It closes specific numerical
compatibility gaps in the preserved `cbramod-paired-program` scorer: that scorer
returns undefined balanced accuracy when any declared class is absent and
undefined R² on constant targets. The pinned author evaluator instead delegates
to scikit-learn's present-class recall mean and default finite R² behavior. No
historical scorer, prediction, task definition, split or comparison is changed.

Reproduction of the original findings and improvement beyond them are separate,
first-class outcomes. This numerical component can support both outcomes once
their source conditions are authenticated; it establishes neither outcome and
does not combine scores from paper+data and paper+data+author-code conditions.

`endpoints.score(dataset, targets, outputs)` takes outputs in original row order:

| Endpoint | Targets | Outputs | Metrics |
| --- | --- | --- | --- |
| FACED, SEED-V, PhysioNet-MI, BCIC2020-3, TUEV | `[N]` | Raw scores `[N,classes]` | Balanced accuracy, kappa, weighted F1 |
| ISRUC | `[blocks,20]` | Raw scores `[blocks,20,5]` | Same three, pooled over the 20 positions per block |
| SHU-MI, CHB-MIT, Mumtaz2016, MentalArithmetic, TUAB | `[N]` | Already-sigmoided scores `[N,1]` | Balanced accuracy, trapezoidal PR area, ROC area |
| SEED-VIG | `[N]` | Regression outputs `[N,1]` | Pearson, R², RMSE |

The binary rule is strictly `score > 0.5`; tied 0.5 scores predict class zero.
PR area uses `auc(recall, precision)`, never average precision. Multiclass ties
use the first class index. Scores are fractions, not percentage points; RMSE
retains the input PERCLOS scale. All rows receive equal weight. There is no
participant averaging, cross-dataset scalar or seed aggregation here. The five
original seed identities and SD convention remain unresolved.

The author ISRUC preparation discards the final incomplete 30-second epoch and
then the last fewer-than-20 epochs before forming consecutive **non-overlapping**
20-epoch blocks. The loader uses batch size one for validation/test, and the
evaluator pools the 20 positions from each block. The scorer requires those axes;
it cannot prove that a model actually received the complete sequence context.
The author's unsorted sequence/label filename zip remains a separate provenance
issue; no sorting or cohort reconstruction occurs here.

Numerical warnings are retained, nonfinite metrics are reported as JSON `null`
with their names in `undefined_metrics`, and one-class binary support is refused
because ROC area is undefined. These are explicit operator serialization/domain
rules. Exact historical dependency versions are unavailable, so this does not
claim historical behavior for every library edge case. Every report names the
NumPy and scikit-learn runtime versions actually used.

For an already authenticated operator-owned pair of numeric NPY files:

```sh
python3 -I -B endpoints.py PhysioNet-MI /operator/targets.npy /operator/scores.npy
```

The caller must independently establish original cohort, split, observation
access, exclusion and ordered row identity. This command does not admit files,
bind row identities, enforce participant access, or issue a paper-win verdict.
It is not wired into the active registry. It does not authorize authentic-target
access or native processing.

`test_endpoints.py --official-evaluator /source/finetune_evaluator.py` checks the
exact SHA-256 before compiling only the original post-inference metric statements
as an oracle. The model/data loops and all Torch code are excluded. Generated
controls cover the complete twelve-dataset dispatch, missing classes, strict
binary ties and PR area, constant regression, float32-to-list promotion, undefined
kappa, sequence-axis rejection and invalid outputs. Two counterexamples also
exercise the unchanged predecessor's numerical code. Use the shared test pool
for this command; no EEG, weights, authentic targets or model calls are involved.

This component is **software-only**. Original TUAB/TUEV split comparability,
complete twelve-dataset row manifests, checkpoints/pretraining exposure,
full-panel author baseline, central ablations, uncertainty and improvement
decision remain unresolved. The prior person-held-out 30%-label condition is
an extension and cannot qualify the original paper task.

Source identities and the generated-control record are in `SOURCE.json` and
`VALIDATION.json`. The source paper is [CBraMod, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/bbbd6d915cb90be21c1254a82d45cedd-Abstract-Conference.html).
