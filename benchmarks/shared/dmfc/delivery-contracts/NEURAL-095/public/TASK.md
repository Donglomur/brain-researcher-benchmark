# NEURAL-095: submit a Python prediction program

Write one Python file accepting `--input DIRECTORY --out DIRECTORY`. It receives only four readonly files: `train.npz`, `query.npz`, `schema.json`, `units.json`. Learn from the748 training trials and predict the released behavioral produced interval `tp`, in milliseconds, for every258 query trial. Query targets and operator data are absent.

The neural observations are four50ms bins from40 held-in DMFC units, strictly before observedSet; cue/context and elapsed recording time are also supplied. This is prediction atSet on the original public historical Haydn20161211 train/validation split, not a200ms advance forecast or cross-animal test. Do not reinterpret the target as Go−Set. The original fixed reference and source interpretation remain the NEURAL-095 task contract.

Write exactly `/output/submission.npz`, containing a Unicode `case_id` vector with all258 query IDs exactly once, and a matching float32/64 `prediction_ms` vector. Any row order and finite negative predictions are permitted; no clipping or scientific score floor is applied. Do not emit other output files. Input/schema or malformed output failures are distinct from poor scientific performance.

Your program runs once offline, nonroot, in the existing pinned Python image (NumPy2.2.6 and SciPy1.15.3). No dependency installation or external service is available. Candidate work allowance is20seconds from the Docker start request; the runner requests termination at that deadline and measures termination latency separately; the CPU limit is20seconds with a22second hard limit. Candidate cgroup has1.75CPU and3GiB memory; the trusted holder has0.25CPU/128MiB. Scratch is64MiB, output is bounded8MiB tmpfs with32inodes, and the single submission is at most1MiB. The program file is at most64KiB. No private targets, saved predictions, operator receipts, scorer package or Docker socket are mounted.

After your program exits, its container is stopped/removed and confirmed absent. A trusted reader captures the one regular output file; the holder and tmpfs volume are then removed. Only afterward does the existing NEURAL-095 scorer read private targets. It returns MAE(primary), RMSE, eight-context macroMAE, all40condition/eightcontext groups, and signed comparisons against all five references. Candidate-minus-reference error below zero is better. No target feedback is available during program execution.

Use the portable artifact-scoring instructions in README.md. Candidate execution remains externally orchestrated.
