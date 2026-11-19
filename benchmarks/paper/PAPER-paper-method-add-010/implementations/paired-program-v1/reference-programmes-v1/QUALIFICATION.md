The two public reference programmes completed one authentic execution on the fixed Generic CS-to-PFC `bary-sq_dtw_max` face/object endpoint: 94 participants, 188 observations and the same ten participant-grouped folds. Each programme ran once per fold, preserving training source order and the whole held-out query batch. Independent review accepted the saved results and execution closure.

| Method | Mean fold accuracy | Population fold SD | Published-precision reproduction |
| --- | ---: | ---: | --- |
| Author batch-range logistic regression | 64.277778% (`1157/1800`) | 9.379022 percentage points | Yes |
| Training-range logistic regression | 66.5% (`133/200`) | 12.986341 percentage points | No |

The original method meets the benchmark's declared precision intervals for the paper's **64.3% ± 9.4 percentage points**. These intervals define numerical compatibility; they do not recover historical folds or the paper's rounding implementation. The primary score gives each fold equal weight; the SD uses `ddof=0`, not a standard error or confidence interval.

Training-range preprocessing raises the same-case mean by exactly `1/45` in accuracy, or **2.222222 percentage points**. Across participants, 14 improve, 70 are unchanged and 10 worsen in number of correct predictions out of two. There are 32 hard-prediction disagreements. This descriptive score increase is distinct from published-precision reproduction and does not establish statistical superiority. The folds were already exposed reference folds, not untouched validation.

[QUALIFICATION.v1.json](QUALIFICATION.v1.json) records exact fold counts, fractions, source/data/runtime hashes and the accepted evidence identities. The programme paths and hashes refer to this `reference-programmes-v1` package. Runtime versions describe the qualified installation, not complete binary or cross-platform portability. Private evidence is identified by hash; its labels, participant identities, feature values and per-case predictions are not included.

The supplied Generic connectivity scalars derive from oracle category-homogeneous averages after author QC. Raw feature extraction, the full measure search, paired-feature distribution/AUC and whole-paper reproduction remain outside scope. This trusted local CLI execution does not qualify hostile-code isolation. The two programmes are scientific method comparators; no AI ability, access-condition effect, SOTA or benchmark admission is established. Earlier constant-0.5 preparation examples remain unchanged engineering artifacts.
