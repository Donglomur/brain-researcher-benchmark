# Reconstruct three learning-phase ripple-rate models

Use the active long CSV and the explicit preprocessing/model specification in `DATA_AND_OUTPUT_CONTRACT.md`. Derive the source-row partition and all model support counts from this input. Report stimulus, feedback and interval fits; retain the signed interval correct-trial slope (`trial + ACC:trial`) and full covariance. There is no reward for a positive slope or a small p-value.

The proposed isolated program interface is `python -I /program/program.py --input /input --out /output`. Produce `/output/submission.json` only, at most 262,144 bytes. A nested model artifact is at most 32,768 bytes after compact ASCII JSON serialization. Program execution and this envelope scorer are separate qualifications: the scorer compares a saved artifact and cannot prove that a program computed it.

`INPUT_IDENTITY.json` binds the active raw bytes, raw-row count, this specification's SHA256 and canonical derived-wide SHA256. Its `max_wide_row_id=8082` is a fixed admission ceiling, not an answered count. Original and changed inputs use the same filename and specification. Do not use stored prior solutions, predictions, private references or scores during an attempt. Disclose general prior familiarity; these development data are exposed and are not a blind biological holdout.

A complete report has all three phases. A partial report keeps the complete preprocessing partition while explicitly abstaining on one or two phase fits. Whole abstention has no preprocessing claim and performs no private reference load. Numerical disagreement, wrong but complete membership and valid alternative covariance-axis order remain gradeable. Public structural or identity errors are rejected before private decoding.

This is a fixed processed-rate reconstruction under an explicit protocol. Full-paper text, first-session provenance and redistribution rights remain unresolved. The current information condition is data plus this protocol; it is not yet a complete paper-versus-paper-and-code experiment. See `RIGHTS_AND_LINEAGE.md`.
