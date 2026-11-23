# Exploratory fixed-image ERP pilot — 22 November 2026

One exploratory comparison used the same 32 fixed two-channel EEG query images, one query selected without labels from each of 32 people, and four labeled demonstration images. Direct image interpretation achieved **57.1429% balanced accuracy**; one generated image-processing programme achieved **26.7857%**. All 32 cases remain in both denominators, including delivery and runtime failures.

This report and the [exact frozen programme](../implementations/exploratory32-image-programme-v1/classify.py) document one experiment within NEURAL-077. They do not create a new benchmark identity or promote the registered task's readiness.

## Design and freezing

The endpoint was target-versus-standard **experimental event identity**, not physiological P3 presence. Each of 32 fresh Codex subagent episodes received four labeled demonstrations and one query image. The programme author received only the four demonstrations and authored a deterministic image-processing programme. A failure-reporting defect was corrected before query exposure; the prediction algorithm was then frozen before any query was processed. The operator invoked the frozen programme in a fresh process for each query, using the same four demonstrations and query images as the direct arm.

Both complete answer sets and the programme source were committed by hash at 19:34:37 UTC on 22 November 2026, before trusted ground-truth access. The trusted scorer validated both complete answer files before opening the authenticated private reference. No failed cases were omitted, retried, replaced, or repaired after prediction.

The direct arm's tool restrictions were instructions, not an enforced sandbox. Exact model snapshots and complete internal tool traces were unavailable. The arms shared image inputs but had unmatched reasoning and compute budgets. The programme batch took approximately 4.5 seconds locally and scoring approximately 0.37 seconds; these durations exclude model reasoning, preparation, review, and CI and are not an end-to-end speed comparison.

## Observed results

The cohort contained 4 target and 28 standard events. Balanced accuracy is the mean of the two class recalls. Explicit errors count as incorrect in their true-class denominator, rather than being excluded from scoring.

| Arm | Balanced accuracy | Conditional 95% interval for absolute balanced accuracy | Valid first outputs | Recorded first-attempt errors |
| --- | ---: | ---: | ---: | ---: |
| Direct image interpretation | 57.1429% | 30.357–76.786% | 31/32 | 1 delivery error |
| One frozen generated programme | 26.7857% | 17.857–35.714% | 26/32 | 6 runtime errors |

The prespecified paired difference, direct minus programme, was **30.357 percentage points**, with a conditional 95% paired bootstrap interval of **1.786–53.571 points**. The absolute intervals and paired interval used 10,000 shared observed-class-stratified resamples, NumPy PCG64 seed `20261122`, and linear percentile quantiles. The intervals condition on this small cohort and its observed class mix; no significance or benchmark-pass threshold was selected.

The direct delivery error was an incorrect demonstration-image path during dispatch. The programme's six first attempts exited with `ValueError`; the original report did not qualify their detailed cause. The frozen source contains an explicit rejection when visible blue trace columns cover less than 97% of either crop, but source inspection alone does not establish that this caused the six observed failures. The original outcomes are preserved, and no revised programme is evaluated by this report.

## Interpretation

The direct arm's interval includes the 50% balanced-accuracy baseline. Its point estimate does not establish reliable above-baseline performance. The paired difference includes differences in operational reliability because delivery and runtime errors count as wrong. With only four targets and one generated programme, the result cannot establish a general advantage of native interpretation over programmes or tools.

No human or established trained-model baseline was run. Public-source pretraining exposure cannot be excluded. Amplitude calibration and physical display-delay correction remain unresolved. These data do not qualify the full 6,400-case condition, reproduce a paper endpoint, demonstrate SOTA, or establish general model performance. A revised programme requires prospective evaluation; a stronger comparison requires a larger frozen cohort and fixed comparison baselines.

## Public reproducibility artifacts and limits

The [programme README](../implementations/exploratory32-image-programme-v1/README.md) describes its input contract, invocation, deterministic feature extraction, and known source-level restrictions. The exact released source is 13,848 bytes, SHA-256:

```text
559d391aab50ff00c1684de248f21b48ca75a9f5bf3a427f1f55f50310d7fc11
```

The reusable [subset scorer](../implementations/exploratory32-image-scorer-v1/README.md) was published separately in [PR #247](https://github.com/Donglomur/brain-researcher-benchmark/pull/247). Generated source checks on that scorer are engineering evidence, not participant performance.

This release contains aggregate results and frozen programme code. Private images, case identities, image hashes, label joins, individual predictions, and links to private individual records are excluded. Consequently, the public artifacts permit code inspection and describe the reported experiment, but do not independently reproduce its exact empirical scores or direct-model episodes. The experimental account and aggregates are transcribed from the completed pilot report; source identity is verified against the frozen file. No programme execution, new prediction, or rescoring was performed to prepare this release.
