# Legacy task recovery — November 16, 2026

The preserved legacy branches contain reusable work, but **199 task branches do not mean 199 accepted benchmarks**. This bounded audit inspected package structure across the preserved tips and ordinary source/review evidence for three selected tasks.

At the audit snapshot:

- All **199 task branches** contained task-specific configuration, instructions, a Docker environment, an oracle entry point and verifier tests.
- They represented **201 package occurrences across 198 distinct task folders**. One hardening branch modified three examples that also had their own branches. Folder counts do not establish distinct scientific questions.
- The exact preserved heads matched **48 open upstream PRs and 151 closed PRs without a merge**; none of these 199 PRs was merged. The open heads remain active branches; the other task tips are preserved in archive tags.
- Eighty branches contained a synthetic-fixture generator by tree metadata. Their scientific content was not classified from that filename.

See the [archive guide](../history/BRANCH_ARCHIVE_20261116.md), [recovery index](../history/BRANCH_ARCHIVE_20261116.json) and [repository quality assessment](REPO_QUALITY_20261116.md). Structural completeness, source checks and PR status are separate from scientific qualification.

## Three recovery samples

These were selected examples, not a representative quality survey. **Paper and dataset descriptions below are leads from legacy task metadata; the primary papers and data were not independently examined in this audit.**

| Sample | Useful work | Limits and decision |
| --- | --- | --- |
| [STEINMETZ-001 — PR 148](https://github.com/brain-researcher/brain-researcher-benchmark/pull/148), head `7125a5b4` | Source-bound out-of-fold grading checks trial identities, predictions, decision values and probabilities across four recipes and 20 folds. It recomputes training-fold majority baselines and requires hash-pinned private reference provisioning. Metadata points to a 2019 Nature paper and DANDI 000017. | A conditional **engineering-reuse candidate**. It is explicitly an easy, single-session method control, not reproduction of the paper's regional finding. The public package is not standalone runnable. Historical execution reports concern an older repair and do not validate this exact head. |
| [EVBOUND-001 — PR 187](https://github.com/brain-researcher/brain-researcher-benchmark/pull/187), head `399e27f6` | A paper/data lead: 2022 Nature Neuroscience event-boundary research and DANDI 000207. | Upstream explicitly retired the task as weak. Its verifier checks an exposed scalar AUC band, a broad session count and keywords rather than source-level predictions or complete-cohort analysis. **Retain the lead; reject the current grader as a mature benchmark.** |
| [WMLOAD-001 — PR 184](https://github.com/brain-researcher/brain-researcher-benchmark/pull/184), head `d6043703` | A recent paper/data lead: a 2024 Nature working-memory paper and DANDI 000673. | Upstream explicitly retired the task as redundant. Its scalar firing-rate AUC tolerance includes chance performance; the task does not implement the paper's stated phase-amplitude coupling endpoint. **Retain the lead; reject the current grader as a mature benchmark.** |

The retirement reasons are recorded in the [EVBOUND comment](https://github.com/brain-researcher/brain-researcher-benchmark/pull/187#issuecomment-5580264151) and [WMLOAD comment](https://github.com/brain-researcher/brain-researcher-benchmark/pull/184#issuecomment-5529245814). STEINMETZ's [publication note](https://github.com/brain-researcher/brain-researcher-benchmark/pull/148#issuecomment-5988474728) explains its private-reference and execution limits. Public answers and reference exposure also need assessment before any protected evaluation.

## What reuse would require

For the **paper track**, define the complete paper result, compare paper-plus-data with paper-plus-data-plus-code, and score prospective improvement separately from reproduction. For the **neural-data track**, require protected case-level outputs, defensible subject/session splits and suitable baselines.

STEINMETZ's grading components merit further review, with full dependency and evaluator-isolation checks, exact reference provisioning and validation at the selected commit. The other two samples need new scientific and scoring contracts before implementation can count as benchmark progress.

**None of the three is established as ready for direct import.** This audit read ordinary authored source and public review metadata only. It ran no tests, models or scientific analyses, read no datasets or private targets, and made no readiness or benchmark-count promotions.
