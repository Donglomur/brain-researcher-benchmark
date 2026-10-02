# N170 source-bound repair

This is a fixed 37-person, PO8, shifted_ds processing adaptation motivated by
ERP CORE. It is not the complete paper pipeline or an exact historical ERPLAB
port. The public contracts describe the 30-channel reference, FIR, trial
selection, signed amplitude, fractional-peak measurement and missingness rules.

The 74 original SET/FDT files (788,438,272 bytes) are version/hash pinned and
acquired before offline runtime. Historical baked waveforms and answer-bank
targets are removed from the active task and remain Git/archive recoverable.
Accepted source-close condition waveforms are the sole downstream measurement
authority. No sign, variability, significance, onset gap, paper-number match or
prose keyword is required.

## Local validation evidence

- All 74 original hashes and 37 bounded SET metadata reports were checked.
- Two independently implemented source routes passed a fixed first-person
  pilot and the complete cohort. Exact event/rejection/source metadata agree.
  All 111 condition/difference waveform bounds, 177,600 PTP receipts and
  5,920 baseline receipts pass the prospectively frozen precision contract.
- 850 installed manufactured checks pass. These include actual MNE-versus-
  analytic-FIR fixtures, missing/zero/positive endpoints, source binding,
  strict IO, private-code isolation and protected output handling.
- The genuine seven-file oracle bundle passes the production verifier.
  Full native QA passes 861 cases: the 850 manufactured cases, one production
  case and 10 genuine-output controls. Three valid serializations pass; three
  effective source/membership mutations and four effective numerical mutations
  fail. All 860 authoring cases are excluded from production scoring.
- The pristine runtime audit covers 85 files, all original hashes, seven public
  contracts/notices/kernel files, the stager and successful capture receipts.
  The capture used 148 requests, zero retries. No solution, bank or populated
  output is baked in. The first build stopped before acquisition because the
  Dockerfile staging path overlapped a protected directory; its log is retained.

All participants and trial identities remain. One participant has no in-window
half-height sample under the public rule; its latency and the complete-cohort
latency summary are null. This valid result is accepted, not repaired by dropping
the person or changing the estimator. Retained MNE EOG-position notices do not
change the contributing scalp channels. No post-result scientific rule or
tolerance was changed.

Production scoring is one complete source-bound test. Original decoding and
preprocessing use independent routes; bounded MAT parsing and the public
downstream measurement kernel are intentionally shared. This is engineering
validation, not independent scientific replication or model-difficulty evidence.

## Delivery receipts

Clean-commit Harbor and final image/artifact/JUnit identity are recorded outside
the task under tracking/pr_repairs_2026-10-01/pr-197, bound to the exact delivered
commit. Consult final_receipt.json for the completed delivery state; a source
edit or this document alone does not establish Harbor success. Model calibration,
push/merge, and public data/image release are not part of this repair.
