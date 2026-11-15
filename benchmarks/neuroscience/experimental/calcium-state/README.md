# Calcium-state scorer prototype

**NOT READY for authentic benchmark evaluation.** This package implements metadata case construction and descriptive scoring for a prospective task. It contains no admitted recordings, animal roster, signal arrays, fitted references or candidate runner.

The endpoint classifies **presegmented, state-homogeneous windows**; target annotations determine segmentation. It is not continuous transition detection or forecasting. Read CONTRACT.json and CONTRACT_SCOPE_ADDENDUM.md together. Sleep and anesthesia are separate regimes: the same raw state code can have different meanings.

The scorer retains full declared frame accounting, rejects missing folds and animal overlap, and emits animal/regime/state metrics. Its opaque-ID metadata projection does not extract signals or enforce process isolation. Boolean admission flags and evidence hashes are claims to verify externally, not proof that a dataset is valid.

From this directory, run `python3 -B -m unittest -v test_scorer`. A future evaluator CLI is `python3 -I -S -B scorer.py --manifest MANIFEST.json --manifest-sha256 EXACT_DIGEST --predictions PREDICTIONS.json --rate-reference REFERENCES.json`. These placeholders have no supplied authentic counterparts.

Complete processed-data schema/cohort admission, animal and label joins, acquisition/preprocessing context, references, uncertainty, resource calibration and isolated execution remain open. No official source is copied here. Public data exposure and acquisition confounding constrain any later neural-understanding claim.
