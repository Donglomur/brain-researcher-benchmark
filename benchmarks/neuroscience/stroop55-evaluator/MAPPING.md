# Stroop55 native input bridge

This extends the existing **NEURAL-SCOPE-20261114-STROOP** task. It implements a concrete bridge from the deposited MAT-field schema to native signal windows and the already reviewed evaluator manifest. It adds no benchmark ID, empirical result or qualification claim.

## What is now verified

The version2 Figshare record identifies one5,076,812,783-byte archive. A bounded current range inquiry and an independent complete-directory check established547 entries, including55 matching prepared MAT basenames in each of three sessions and matching raw CSV/TXT inventories. The archive's full MD5 was not recomputed.

All three original top-level MATLAB scripts and UsageNotes were read as source, with decoded size/CRC/SHA identities verified. Source text was not executed. Neural arrays, marker MAT bodies and demographic records were not acquired or read. The original author's analysis code is embedded in the archive; no separate author GitHub repository or complete installed dependency environment is verified.

The source establishes the fields `nirsdata.oxyData`, `dxyData`, `totalData` and `vector_onset`; the analysis expects time-by35 channel matrices at25.6Hz. The marker scripts use `design_inf` row columns2–4 for codes11/12/13 and the first column of each cell matrix as a MATLAB sample index. The biological row-to-person join and the relation between marker indices and trimmed data must still be checked on actual metadata. The bridge refuses disagreement between the supplied marker columns and the prepared onset vector; it never invents a crop offset.

## Executable seam

`source_inventory(member_names)` checks all nine file inventories: three sessions times prepared MAT, raw CSV and raw TXT. It requires the same55 source basenames in all of them, including session3. Its output contains private source names and belongs in assembler custody.

`marker_columns(columns)` accepts the normalized three `design_inf` condition cells keyed by11,12,13. It reads only each row's first value as a1-based sample index; remaining columns are not assigned invented meanings. It does not join a marker row to a person by position.

`native_block_plan(vector_onset, columns)` cross-checks the complete two marker representations. For every actual block, it plans the contract's exact[-5,20) window:640 samples with offsets[-128,+512). It refuses a missing boundary or intersection with the following block. It does not pad, truncate to30, crop by class or silently exclude a case.

`native_windows(nirsdata, columns)` yields one640×70 native window at a time, with35 HbO channels followed by35 HbR channels in deposited order. It preserves values, checks channel/sample shape and finite window values, and supplies the exact relative time grid. Its output includes private source-block metadata and **must not be passed directly to a candidate**.

`private_manifest(inventory, aliases, seed_hex, case_key, recording_plans)` joins all165 recording plans to the unchanged evaluator. A separately verified source-to-opaque identity map is required. The caller supplies the precommitted partition seed and a separate private32-byte HMAC key for case IDs. Cases are HMAC-ordered, avoiding publication of chronology. Session3 supplies intended evaluation cases; every evaluation person must retain all three classes. The original55-person metric and joint held-person/session split are unchanged. Declaration checks cannot establish physical completeness, biological identity or exposure.

The caller must normalize loaded MATLAB structures to indexed matrices, a flat onset vector and condition-cell tables. Each recording plan supplies its actual `n_samples` so the manifest bridge can recheck all window bounds and subsequent-block intersections. This source package does not load authentic MAT files, execute MATLAB, fit preprocessing or write a candidate packet. The accepted evaluator dependency `stroop.py` is reused byte-for-byte.

## Scientific differences and unresolved inputs

- The author scripts pool all three sessions within a person, take the first30 onsets per condition across sessions, average shuffled groups into five pseudo-trials per class, and leave out one pair of pseudo-trials for each linear-SVM test. They repeat the shuffling33 times. That endpoint differs from our joint held-person/session3 three-class endpoint.
- The original filename assertion accidentally compares session2 twice and omits session3. The bridge checks every session explicitly.
- The author's768-sample window uses onset−127 through onset+640 inclusive; the first128 samples form its baseline, including the onset sample. The plotted linspace is not the exact25.6-Hz grid. The bridge follows the existing task's[-5,20) interval and does not claim to reproduce that paper preprocessing or result.
- UsageNotes specifies trimming15 seconds at both ends, while the article describes15 seconds at the start and5 seconds at the end. This discrepancy is unresolved. Marker/prepared-array alignment, exact filter implementation and edge effects need authentic validation.
- The plot labels use `mM.mm`; UsageNotes does not specify the device export's physical scale. Keep **export scale unverified**. No conversion to plain mM or micromolar concentration is justified.
- The proposed40×70 representation still needs a fixed, independently checked anti-aliasing/resampling implementation and information-loss assessment. Native640×70 extraction is an intermediate seam, not evidence that this candidate representation is ready.
- Original order is shared across people within a session. Candidate packets must remove source names, absolute time, block indices, session, marker codes and behavioral fields. HMAC IDs alone do not establish protection against known public-data exposure or schedule inference. Geometry, carryover/systemic-noise controls, competent train-only baselines and an enforced evaluator boundary remain required.

Generated controls exercise third-session roster mismatch,1-based indexing, complete marker joins, boundary and next-block refusals, retaining more than30 blocks, native grid/channel order, invalid values/shapes and full55-person evaluator compatibility. They provide implementation checks, not empirical neuroscience or model results.

Primary sources: [dataset version2](https://doi.org/10.6084/m9.figshare.31839673.v2) and [the data paper](https://doi.org/10.1038/s41597-026-07800-4). Exact source identities and remaining holds are in `BRIDGE_SOURCES.json`.

