# NEURAL-018 scoring panel, version 2

The arbitrary-submission contract and primary joint forward-bps metric are unchanged. This version reports comparisons with all five fixed authored development references:

| Reference | Forward bits/spike |
|---|---:|
| Time-pooled condition | 0.15064826644621088 |
| Training-CV-selected ridge | 0.11073911302568201 |
| Original global rate | −0.003219973976338411 |
| Original condition/time | −0.36381109685480034 |
| Original past-activity/condition neighbor | −0.717818101449004 |

The two newer references are an outcome-informed follow-up on the same exposed development panel. They are not published SOTA, evidence of incremental neural information, or acceptance thresholds. Ridge remains below the pooled-condition reference. All original signed comparisons remain visible. Valid predictions can score below every reference; validity is not scientific success.

Run `python3 benchmarks/neuroscience/neural-018/scoring-v2/score.py score --submission /absolute/candidate.npz --output /absolute/new-result.json`. The scorer uses the unchanged bounded public validator and Poisson metric in the existing offline, nonroot, read-only, 2-CPU/4-GiB container. No candidate code runs, no new reference fit occurs, and no network or installation is used. Private targets are loaded only after the arbitrary candidate and fixed source lineage validate. Immutable saved follow-up score, prediction-commit and compact-output hashes bind the stronger references; no durable expanded rate array is created.

The task remains forecasting all182 units across40 future5-ms bins [450,650) from strictly earlier preprocessed observations plus declared condition context, on574 public historical validation trials of one Jenkins session. Original task details and submission schema are in `../INSTRUCTIONS.md`; source, licenses, public/private input boundaries and development exposure remain unchanged. This trusted local scoring adapter is not the full agent-facing isolated task environment or a research/submission admission claim.

Version1 source and receipts remain unchanged in the parent directory. The root manifest switches to this entrypoint only after version2's reference and invalid-submission qualification completes.
