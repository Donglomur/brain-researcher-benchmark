# Follow-up repair: run-wise reference and offline source

The original dated subject-1 archive was downloaded and checked against the
separately published MD5SUMS. Archive and three input SHA256 values are frozen in
environment/data_manifest.json. All selected bytes match the shared read-only
cache. The Docker image stages those original files and verifier dependencies;
runtime internet is disabled.

The corrected real-data oracle produced accuracy 0.8333. Direct nibabel masking
and independent SciPy per-run detrending/scaling reproduce all 864 predictions
using the same sklearn/libsvm classifier. The real global-clean control produces
0.722222 and 247 different predicted labels. The stale global-cleaning bank is
replaced by runwise-clean-loro-v2, retaining every source-keyed prediction.

The public pinned recipe now matches instruction, oracle, verifier and metadata.
The verifier requires source and predicted-label agreement and exact arithmetic
within disclosed rounding precision; the loose score/correlation alternative is
removed. Scientific scope is a modern single-subject easy method control, not
the original paper's numerical endpoint or proven hard benchmark.

Final clean-commit Harbor and regression receipts are maintained outside this
task in tracking/pr_repairs_2026-10-01/pr-140/. They determine execution status;
this document alone is not an execution receipt. No model calibration or remote
publication is implied.
