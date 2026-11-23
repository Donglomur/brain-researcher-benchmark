# Five-seed Bugeon panel summary

The [conference paper, Tables 1 and 8](https://papers.nips.cc/paper_files/paper/2025/file/8f7dc9855bb4ae8ae4f2d649f3f4efe6-Paper-Conference.pdf)
reports Bugeon macro-F1 means across five training seeds. This owner-side component
connects the existing single-run evaluator outputs to that aggregation. Within
each seed it preserves the complete original outer-test prediction pool; across
seeds it averages the five macro-F1 values. Combining predictions across seeds,
averaging subject scores, or choosing the best seed produces a different result.

`summary.summarize_panel(runs, seed_roster=..., method_sha256=...,
protocol_sha256=...)` consumes exactly five run objects. Each has `seed`,
`training_run_sha256`, `packet`, and `readout_result` from the unchanged
`initial-evaluator-v1` API. The roster has no default: original training seeds
remain unrecovered. Method, protocol and training-run hashes are declarations
requiring separate evidence; five different strings do not prove five trainings.
Inputs contain owner-only labels and embeddings and must stay outside participant
contexts. The function returns an in-memory summary and writes no files.

The pinned evaluator validates each packet's original panel topology, complete
labeled population, metadata and exposure declarations. The summary checks its
result binding, literal test-record coverage and order, labels, subjects, selected
checkpoint, earliest CV tie and readout fit count. It recomputes pooled and
per-split metrics from granular predictions with the unchanged evaluator. Every
seed must share the exact fixed split, labels, metadata, exposure, context policy,
readout balancing and checkpoint epoch/row-order/width schedule. Local checkpoint
names and feature values may differ. Source invalid-split refusals are inherited.

Only the three source classification metrics are summarized; macro-F1 stays the
primary metric. Both `descriptive_seed_sd_ddof0` and `descriptive_seed_sd_ddof1`
are explicitly named diagnostics. Neither is selected as the paper statistic:
the source SD denominator and the SD/SEM reporting discrepancy remain unresolved.
These quantities describe optimization variation conditional on the cohort, not
biological uncertainty. No confidence interval, meaningful-effect cutoff,
reproduction tolerance or improvement decision is introduced.

The output retains each seed's packet/result/run digests and selected checkpoints.
Structural consistency does not authenticate native training, archive custody,
predeclaration, or actual readout fits. Legacy results contain CV scores but no
CV predictions, so this adapter checks the selection rule without recomputing
those scores. `execution_verified`, `training_independence_verified`,
`research_qualified`, and `full_contract_complete` remain false. The frozen
contracts, published targets and historical pins are unchanged.

Run generated controls from this directory with `python3 -B -m unittest -v
test_summary`. For an isolated staged component, set `NUCLR_IMPLEMENTATIONS` to
the existing task's implementations directory; production callers may likewise
supply `implementation_root`. The exact evaluator digest is always checked.
The controls use generated JSON operands and perform no fitting or native work.
