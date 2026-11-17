# TMS behavioral reproduction component

This component constructs and compares a full-cohort behavioral reference for the [TMS/V1 study](https://www.nature.com/articles/s41467-025-57882-8). It is evaluator code for `PAPER-paper-signal-add-021`, with invented mathematical and schema tests. This source release contains no authentic reference values or validated physiological result. It does not complete the paper's paired EEG task or establish a submission-ready benchmark.

## Inputs and execution

Use Python 3.11 and its standard library; no package installation is needed. Obtain `behavioralData_allsubs.csv` through the [official OSF release](https://osf.io/hf5a4/). The reader accepts exactly the selected release: **4,926,544 bytes**, SHA-256 `b677bede5c7c8c2806e2796ed58c783b07d2a73687d662b97ceb078916ade80a`. It never downloads data. A missing or different release fails before analysis; changing the hash is not a compatibility fix.

From the repository root:

```sh
python3.11 -I -S -B benchmarks/paper/PAPER-paper-signal-add-021/implementations/behavioral-reference/behavior_reference.py inputs/behavioralData_allsubs.csv reference.json
python3.11 -I -S -B benchmarks/paper/PAPER-paper-signal-add-021/implementations/behavioral-reference/score_behavior.py reference.json candidate.json
```

The first command creates a new reference file and refuses to overwrite it. Its fixed defaults are seed `20261114`, 2,000 bootstrap draws, and no optional global-shuffle diagnostic. The second prints JSON. **Read its `accepted` field:** numerical mismatch is reported in JSON and does not make the process exit nonzero. Malformed JSON, duplicate keys and nonfinite JSON constants raise errors.

`reference.json` is trusted evaluator input. A candidate file must use the same schema, metric names, complete ordered cohort and participant-condition cells as the reference. The scorer compares the four components described below; it does not independently authenticate a candidate's data access, provenance or execution. Keep authentic references and candidate outputs outside the source repository.

## Complete behavioral specification

The reader requires `subjID`, `day`, `TMS_condition`, `ierr`, `isacc_rt` and `isacc_peakvel`. It requires all 15 published release codes in `ROSTER`; these codes do not identify physical people. It rejects unexpected subjects, days, condition labels, ragged rows and duplicate or missing required columns. Missing outcome values are counted. Each participant must still have at least one valid value in every condition for each outcome; people or conditions cannot be dropped to obtain a score.

The seven figure conditions are `No TMS`, `mid inPF`, `mid outPF`, `early inPF`, `early outPF`, `midrep inPF` and `midrep outPF`. Days 1–3 define the first experiment, day 4 the early-stimulation condition and day 5 the middle-stimulation replication. No-TMS rows on days 4–5 are explicitly excluded by the seven figure predicates. No further trial filtering is applied. The intake record reports columns, row counts and observed `ispro` labels; participant cells report valid and missing counts; their scientific interpretation must be checked against the released derivative before relying on an authentic reference.

There are **315 participant-condition-outcome cells**: 15 participants × 7 conditions × 3 outcomes. There are **18 directional contrasts**: six for each outcome. All 15 leave-one-participant-out summaries are retained for every contrast. Rows are identified by CSV ordinal, not by an independently verified physical-trial map.

## What is compared

| Component | Definition |
|---|---|
| `deterministic_figure_reproduction` | Absolute trial-value means, valid counts and missing counts for every participant-condition cell. |
| `deterministic_helper_formula_reproduction` | Signed cell means on the same figure predicates. |
| `paired_statistics` | Equal-participant differences, mean, sample SD, standard error, paired t and Cohen's dz for absolute and signed means. Zero-variance t and dz are explicitly null. |
| `corrected_scientific_inference` | All 2^15 participant sign patterns, paired-participant bootstrap, Holm adjustment across six contrasts within each outcome, and all leave-one-participant-out summaries. |

Float comparisons use relative tolerance `1e-7` and absolute tolerance `1e-9`; integer, label and structural comparisons are exact. `accepted: true` means these component outputs match the trusted reference. The result always includes `whole_task_qualified: false`.

Figure means follow the released `generateFigure2.py` predicates and use absolute trial values. The signed statistics reproduce helper formulas on those predicates. They do **not** execute the author's different pro/anti-filtered `all5`/`clubbed` pipeline or recover historical randomized p-values. The optional `--literal-draws N` global-label shuffle is a diagnostic, uses a declared Python RNG, may destroy participant-condition cells, and is not scored. Leave it disabled for the reference command above.

Sign-flip inference assumes joint sign exchangeability of paired differences. Bootstrap intervals are approximate with 15 participants. Holm adjustment is within each outcome, not an omnibus correction across all three. Cross-day comparisons can contain session/order effects; these calculations do not establish randomized within-day causal effects. A smaller p-value is not evidence of a better method.

## Validation and benchmark use

The seven included tests passed during independent source review. They use explicitly invented arithmetic and schema fixtures, including missing-cohort refusals, signed-versus-absolute means, participant weighting, scale-sensitive sign-flip ties, zero-variance statistics and scorer mismatches. They are not observations from neuroscience data. To run them from the repository root:

```sh
python3.11 -I -S -B benchmarks/paper/PAPER-paper-signal-add-021/implementations/behavioral-reference/test_behavior_reference.py
```

An authentic run still requires full input-schema, condition, preprocessing and missingness checks. Full task qualification additionally requires the paired EEG analyses, competent references, protected evaluation, contamination controls and complete end-to-end evidence. Paper+data and paper+data+official-code arms must use matched inputs and budgets; evaluator corrections and answers must not be silently supplied to either arm. This public evaluator implementation and public paper may be familiar to a model, so a fresh context alone is not a contamination control.

## Attribution and redistribution

These files are a benchmark implementation of the documented figure predicates and statistical formulas, with separately specified participant-level inference. Sources are the [published article](https://www.nature.com/articles/s41467-025-57882-8), [official figure repository at the inspected revision](https://github.com/clayspacelab/Dake_Curtis_TMSV1_2025/tree/1e2c149e6e61f85b45acb8486c0fb31dc38d2dfa), and the linked [author analysis repository at the inspected revision](https://github.com/mindemory/mgs_stimul/tree/57c4aeac3028c02f4b886eb4fd05435e126a80fe). Inspected code choices are not proof of the exact historical publication execution.

The benchmark implementation is covered by this repository's [MIT license](../../../../../LICENSE). No third-party source files, article text or data are redistributed in this directory. The code license does not grant rights to redistribute the OSF data; consult the source's applicable terms independently.
