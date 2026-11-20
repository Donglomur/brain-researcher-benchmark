# SMC frozen-reference rescoring

The bounded evaluator successfully rescored both complete frozen author predictions on the original MC_Maze 20 ms task. Both predictions and freeze records were validated before target access. The shared two-score operation took 22.07 seconds, and its grader container and recorded host processes closed successfully. No author-model inference or retraining, and no AI candidate run, occurred. The unchanged velocity R² evaluator still includes its canonical TRAIN-split decoder fitting.

| Model | Metric | Current | Current−historical | Paper printed | Current−printed |
|---|---|---:|---:|---:|---:|
| causal | co-bps | 0.3221297804 | 0 | 0.3225 | -0.00037021963 |
| causal | fp-bps | 0.2192421155 | 0 | 0.2184 | 0.00084211547 |
| causal | psth R2 | 0.5931377256 | 0 | 0.5927 | 0.00043772564 |
| causal | vel R2 | 0.8459605027 | -1.11e-16 | 0.8479 | -0.0019394973 |
| noncausal | co-bps | 0.341016088 | 0 | 0.3407 | 0.00031608796 |
| noncausal | fp-bps | 0.2418654447 | 0 | 0.2417 | 0.0001654447 |
| noncausal | psth R2 | 0.5958331235 | 0 | 0.5963 | -0.0004668765 |
| noncausal | vel R2 | 0.8898607459 | 1.11e-16 | 0.8902 | -0.00033925406 |

The [machine-readable result](smc-historical-rescore-20261120.json) retains full precision. Six values match the historical calibration exactly; velocity R² differs only by the signed values shown. These are descriptive comparisons, not a tolerance-based equivalence or paper-reproduction claim.

The original scoring code and nlb-tools 0.0.3 evaluator were unchanged; their exact source identities are in the JSON. NumPy 1.26.3, SciPy 1.12.0 and scikit-learn 1.5.0 match the historical environment. The declared I/O variant uses h5py 3.10.0 instead of 3.11.0.

One shared child had a 2 GiB memory limit, one numerical CPU, 600/605 CPU-second soft/hard limits and 720 seconds of work plus 60 seconds for cleanup. It exited 0 without an OOM indication. Current peak RSS and CPU consumption were not recorded; the older run's measurements are not reused as current observations. All 12 Docker calls completed with retained captures, the container was removed, and the native lease was released.

The historical noncausal score's supervisor still failed with `ValueError: Scorer identity changed`, despite its scoring child exiting 0. This new successful score-only run does not erase that failure or the earlier image-admission refusal.

Exact released-checkpoint linkage to Table 2 and the original DANDI revision remain unproved. The targets have been public since January 2026. The 32 trajectory sets average inference; they are not independent replications. These results qualify this frozen-reference evaluator path, not fresh model inference, exact paper reproduction, improvement or SOTA.
