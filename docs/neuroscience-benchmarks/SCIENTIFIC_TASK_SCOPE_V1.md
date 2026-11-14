# Scientific task scope and qualification

Adopted prospectively on 2026-11-14. This protocol applies to new proposals. It does not change existing full-paper contracts, their holds, the original 200 tasks, or the current 217-draft count.

## What one task means

A task asks an agent to resolve one scientifically central question with a separately interpretable outcome. Its scope includes every cohort, control, comparison and robustness analysis required for that question. The source paper identifies the contribution; availability alone does not determine the endpoint.

Full-paper replication is a separate scope: it promises the paper-wide result set specified in its contract. An endpoint task must name the result it reproduces and what conclusions that result supports. It must not imply that completing one endpoint reproduces the whole paper.

Preprocessing, fitting and plotting are stages of a task. Subjects, folds, restarts, rubric leaves, controls and access conditions are not additional independent tasks. Multiple tasks from one source family require a materially distinct scientific question or estimand, or an independently assessed core methodological contribution, with a separately interpretable outcome. Changing the algorithm, representation or output packaging for the same scientific question alone does not add a task. Report both task counts and source-family counts; statistical aggregation must account for shared papers, participants and datasets.

## Paper reproduction and improvement

Before implementation, each contract records:

1. The central claim and exact estimand: population, intervention or predictor, comparison, outcome and unit of analysis.
2. A claim-to-evidence map covering every required figure/table result, cohort, exclusion, control, null result and external validation. Explain any omitted assay and why it is unnecessary for this endpoint.
3. Immutable paper, supplement, code and dataset versions; rights; a complete inventory at the authentic input level scientifically sufficient for the endpoint; biological identity and missing-data rules. A derived-analysis task need not start from raw voltage or images unless its claim requires those inputs; derivation provenance and relevant uncertainty still need verification.
4. The two information conditions: paper plus data, and the same paper/data plus official code. Both need an equally sufficient scientific specification and the same evaluation. Missing essential methods are an underspecification defect to resolve, not evidence of model inability.
5. A competent reference and baselines, with preprocessing, training, tuning and uncertainty fixed before final evaluation. Numerical tolerances follow measurement precision, stochastic variability and scientific effect size, rather than the identity of the reference implementation.
6. Separate reproduction and improvement outcomes. Reproduction tests the declared published result. Improvement uses fixed protected evaluation and matched resources, with leakage, tuning, multiplicity and grouped uncertainty addressed explicitly.
7. Required submissions and independently checkable scoring: predictions or fitted artifacts, runnable analysis, source provenance, estimates and uncertainty, and justified conclusions. Score result validity separately from code execution and narrative completeness.

If released code selects models using the final test set, preserve that behavior as a documented reproduction condition. A corrected comparison uses a separate preregistered split and tuning procedure; it cannot silently replace the reported result or be tuned until it looks better. A discrepancy can motivate a useful diagnosis task, but does not establish a successful reproduction or invalidate a paper by itself.

## Neural-data understanding

Define the inference first: for example, a physiological effect, a behavioral variable, a mechanism comparison or generalization to new animals/sessions. Specify the complete scientific evidence and the temporal information available at prediction time.

Compare per-case investigation and a program written in advance under the task's declared protocol. Keep signals, metadata, training labels, task-model access, preprocessing, quality flags and calibration information matched wherever the contrast requires it. A learned decoder supplied as a tool changes the available evidence and must be named as an access condition.

Raw waveforms, images and lossy feature summaries are different representations. A summary that loses within-bin timing is a separate information condition unless equivalence for the selected inference is demonstrated. Include signal-free, shuffled or nuisance-aware controls where they answer plausible shortcuts; retain biologically valid grouping and causal timing. A high score alone cannot distinguish native signal understanding, retrieval, tool competence and dataset-specific shortcuts.

## Readiness is evidence, not a file count

| Status | Required evidence |
|---|---|
| Registered draft | Distinct scientific question and a source-backed contract; gaps are explicit. |
| Inputs verified | Rights/provenance and complete authentic inputs for the declared scope are verified, including native units, identities and eligibility. |
| Runnable construction | An executable environment, reference, evaluator and meaningful positive/negative controls complete the declared workflow on authentic inputs. |
| Scientifically qualified | The estimand, baselines, protected evaluation, grouped uncertainty, contamination handling and outcome tolerances are defensible; independent review and actual end-to-end reference evidence support the claim. |
| Established reproduction | Observed agreement for the declared scientific endpoint and its uncertainty, with discrepancies and scope disclosed. |
| Model evaluated | Fixed-protocol model attempts provide measured performance/difficulty. This requires a separately authorized model campaign. |

These statuses describe different evidence, not an automatic ladder: a runnable diagnostic task may establish a non-reproducing result. CI or synthetic tests establish engineering properties only. Scientific qualification does not require a paid frontier-model campaign, but model difficulty cannot be claimed without model attempts. External submission readiness also depends on the destination's current review requirements; it is not conferred by a local label.

## Design precedents

ResearchCodeBench reports 212 nested code challenges from 20 papers; those are coding challenges, not 212 independent paper replications. PaperBench uses 20 paper-level tasks with thousands of rubric leaves. These examples support explicit task granularity and separate progress measures. [ResearchCodeBench](https://proceedings.neurips.cc/paper_files/paper/2025/file/cd0d0a873cc3e601c76f46dccc3d4c5f-Paper-Datasets_and_Benchmarks_Track.pdf), [PaperBench](https://cdn.openai.com/papers/22265bac-3191-44e5-b057-7aaacd8e90cd/paperbench.pdf).

The official Terminal-Bench-Science proposal and implementation rubrics emphasize substantial scientific workflows and fair verification; they do not universally require every assay in a paper. They reject numerical restrictions that only admit the reference approach. These criteria inform our design, without claiming acceptance by that project. [Proposal rubric](https://github.com/harbor-framework/terminal-bench-science/blob/main/rubrics/task-proposal.md), [implementation rubric](https://github.com/harbor-framework/terminal-bench-science/blob/main/rubrics/task-implementation.toml).

