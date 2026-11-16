# Full across-day motor-decoding artifact scorer

Score a completed prediction file for **NEURAL-023**, the fixed Indy 2016-10-05 to 2016-10-06 exposed-development task. The complete support is 22,091 assessment rows from 96 neural channels. The four scientific helpers in `dependencies/` are unchanged, hash-pinned implementations of the accepted NPZ validator, target/reference loaders, metric calculation and independent arithmetic audit.

This source package contains no neural arrays, target values or reference report. The operator separately supplies the exact assets described by `ASSETS.json`; there is no automatic acquisition and no command-line override of their expected identities. Candidate-public assets comprise source-day labeled counts, 60-second next-day labeled calibration, target-free assessment counts, and their public coordinate manifest. The target and reference report are operator-only.

From a checkout, invoke a dedicated trusted operator process with existing Python and NumPy:

```sh
python3 -I -B benchmarks/neuroscience/neural-023/external-artifact-v1/external_score.py \
  --source-root /absolute/path/to/external-artifact-v1/dependencies \
  --submission /absolute/path/to/predictions.npz \
  --target /absolute/path/to/operator/assessment-targets.npz \
  --reference /absolute/path/to/operator/reference-metrics.json \
  --output /absolute/path/to/fresh-output-directory
```

All argument paths must be absolute and unlinked. The output parent must exist and the output directory must be new. Source, submission and operator inputs must be ordinary single-link files. Helper paths are relative only to the explicit source root; the adapter never searches the surrounding checkout for missing dependencies. There are no workstation paths, container/image dependencies or network calls.

Submit exactly `case_id[22091]` and `velocity_m_s[22091,2]`. IDs 3010–25100 must occur once each; row reordering is accepted. Velocities are finite x/y values in m/s for the trailing 20 ms interval. See the existing [public contract](../public_contract.md) for permitted integer/float widths, NPZ encodings and bounds: 1,000,000 bytes on disk and 600,000 bytes uncompressed.

The complete public submission is validated before either supplied operator path is inspected or read. Immutable source and asset snapshots must match their declared hashes. Candidate bytes are never executed. The resulting `score.json` contains mean-axis R², per-axis scores, MSE/MAE, all eight descriptive clock blocks, all seven signed reference comparisons and the independent arithmetic audit. Negative scores are valid. An undefined axis remains undefined; unsupported finite arithmetic produces a null primary score rather than clipping. A separate read-only `receipt.json` binds the score hash and submission identity. Inspect its status; an interrupted or failed directory is not completion.

The process uses a 30-second alarm and a CPU soft ceiling of at most 20 seconds, preserving tighter inherited limits. These controls do not guarantee filesystem deadlines or impose a memory quota. The operator owns host allocation, starts scoring only after any producer has stopped, and keeps target/reference access outside the candidate environment. This artifact interface cannot prove producer shutdown, fitting provenance, input dependence or protected execution.

Eight generated relocation checks exercise a source copy at an unrelated directory, separate invented operator assets, full-support grading, invalid/incomplete submissions before unavailable operator paths, wrong identities, missing/changed helpers and the explicit CLI with an inherited CPU limit. These are interface controls, not authentic neural-data runs. The publication projection preserves accepted scientific calculations; it does not add a new benchmark ID or repeat the authentic qualification.

This is one exposed animal/day pair and retrospective batch prediction, not an unseen-test, population, online-forecasting, SOTA or LLM-performance result. NEURAL-023 assessment counts also expose NEURAL-024 future-neural targets; do not claim the latter hidden after this exposure. The original data source recorded by the existing task is O'Doherty et al., [Zenodo 3854034](https://doi.org/10.5281/zenodo.3854034), CC BY 4.0. The prepared assets are separate from this source-only publication. Repository source licensing does not grant additional dataset rights.

The existing legacy `score.py` and generic CLI are unchanged. This companion is invoked directly and introduces no named-profile dispatcher.
