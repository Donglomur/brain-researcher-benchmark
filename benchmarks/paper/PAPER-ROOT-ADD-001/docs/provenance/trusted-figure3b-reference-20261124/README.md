# Complete selected Figure 3b reference

On 24 November 2026, the fixed original Ridge method completed **42 cells across all 14 sessions and eight people**, making **5,685 fresh estimator fits**. Its equal-session mean Pearson correlation was **0.04512071156679768**, matching the provided author reference. The largest absolute difference among the 42 cells was **3.191891195797325e-16**; the paired mean difference was **-4.631092136759512e-18**. These are descriptive numerical differences, not a newly selected acceptance tolerance.

This is a completed **trusted operator replay of the selected contextual population Figure 3b endpoint**. It establishes a freshly fitted reference for later comparisons. It does not establish participant NativeProvider qualification, a complete 224-array or whole-paper reproduction, an AI result, improvement, or SOTA. No information-access arms were compared.

- [Aggregate result](RESULT.json)
- [Exact source, runtime and lifecycle provenance](PROVENANCE.json)
- [Byte-identical measured guest driver and input contract](../../../implementations/trusted-figure3b-reference-v1/README.md)
- [Earlier provided-author array reduction](../original-reference-20261117/README.md)

## Scientific condition

The replay uses the existing selected-store reader and original `source_ridge_predictor` / `predict_job` primitives. Each held sentence qid gets a fresh `Ridge(alpha=0.01)` with original defaults. Training excludes every row of the held qid. Supplied 30-PC contextual features, layer index 5, lag indices 17–19, speaker handling, centered response smoothing, padding and row order are unchanged. Predictions are pooled before Pearson calculation; three fixed lag values are averaged per session, then all 14 sessions receive equal weight. The author reference is read only after every fit completes and never enters predictor inputs.

All 42 prediction files and cell receipts were retained privately and their hashes, shapes, contexts and fit totals verified. This public package contains aggregates and hashes only. Fourteen sessions come from eight people; cells and fits are not independent subjects. Public exposure and the original retrospective transformations remain. The 579-versus-567 unit correspondence remains a separate limitation for broader paper claims.

## Runtime and closure

The actual runtime was Linux/arm64, Python 3.11.3, NumPy 1.24.3, SciPy 1.10.1 and scikit-learn 1.2.2. All three loaded numerical thread pools reported one thread. The worker completed in 7.001 seconds, the complete outer operation in 10.864 seconds, and worker peak RSS was 131,182,592 bytes. Worker RSS is not a measurement of the whole Docker VM. The container had a 3 GiB memory limit, no additional swap, one CPU quota and no network.

Attempt 001 stopped because Docker was unavailable; no container, data-body read or fit occurred. Attempt 002 created a container but its exact prestart guard rejected an inherited Python entrypoint before the worker started. That container was removed. The narrow repair cleared the entrypoint, preserving the scientific driver and validator; a focused regression used the saved actual inspection. Attempt 003 completed all fits. Each attempt is retained, and all owned process scopes closed. The successful container was removed and its absence verified. No automatic retry, score tuning or favorable cell removal occurred.

The existing comparison reducer still records its generic scientific and participant qualification flags as false. Separate execution receipts establish this fixed operator replay; those flags were not rewritten to imply arbitrary participant isolation. A stronger classical comparator and a frozen AI-created method require separately selected experiments on the same endpoint.

Source attribution: Cai, Cash and Williams, [Zenodo 20128462](https://zenodo.org/records/20128462), associated with [Mapping the neuronal building blocks of human language with language models](https://www.nature.com/articles/s41586-026-10691-5). The retained release is recorded as CC BY 4.0; attribution does not imply endorsement.
