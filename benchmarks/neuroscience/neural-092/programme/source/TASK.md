# NEURAL092 — observed state-by-area association reconstruction

This is an **observed-data investigation**. QUERY spike counts are deliberately available to the candidate, so it can reconstruct the actual state associations. It is not a renamed hidden-response prediction task. The private scorer binds the authentic packet and recomputation; no fixed biological sign or significance is required.

Keep all32 Allen Visual Coding Brain Observatory1.1 sessions/32mice. Six fixed anatomical visual areas are source-verified via electrode IDs; mouse genotype is not a unit genetic type. Metadata-only inspection of every selected recording established drifting-grating blocks2/5/7. Block2 defines FIT rates and pupil terciles; block5 is public validation; block7 is observed QUERY. Source chronological ordering is checked. The target interval is half-open `[onset+.05,onset+1.95s)`, within a valid native presentation. No query activity determines thresholds, pairing, selection or normalization.

Running and pupil comparisons are separate. Rest≤1cm/s versus running≥5cm/s is paired within the exact native stimulus condition, QUERY block and pupil bin. Missing pupil is an explicit stratum, so missing-eye sessions are retained for running. Pupil HIGH versus LOW FIT-tercile bins are paired within condition/block and REST/RUN. MID, missing and transitional states receive explicit dispositions. Each side is sorted by native onset then ID and zipped once; no reuse, response-driven replacement or winner selection.

Per unit: mean paired(high-rate−low-rate) divided by its positive FIT mean-rate baseline. Per area: equal unit means. The primary is error reconstructing running effects, equally weighted over available fixed areas in each session, then sessions/mouse and mice. A required session with no defined area/pairs makes the full primary unavailable. Pupil reconstruction is separate; six source sessions lack gaze, so the full32 pupil endpoint is expected to remain unavailable and must not be silently relabeled a26-mouse primary. All area/session dispositions are returned.

For all15 area pairs, also return a sensitivity contrast after equal-count matching in frozen FIT-rate and published-QC bins. Selection is by stable unit-ID hash within each bin, never by query response. The sensitivity balances coarse rate/reliability descriptors; it is not exact physiological matching or a single universal cross-area cohort. No bootstrap/selected p-value supports a claim here. Null or mixed directions are valid findings. Explanatory predictive gains remain null until independently fitted, method-matched, isolated reference predictions exist; a candidate cannot inflate a score by weakening its own nuisance predictions.

Candidate interface:

`python program.py --public-index /packet/public/INDEX.json --packet-root /packet --output /output/submission.json`

Return all32 session keys, both running/pupil modes, all six area values and all15 matched-area contrasts. Undefined support is explicit null. Public observed QUERY counts, FIT baseline, state labels and the explicit mathematical protocol are sufficient for an independent reconstruction. Benchmark-authored reference/scorer/core and answer-generating fixtures are operator-private and excluded from the candidate mount. Whole-panel candidate shape/value admission precedes private-index-bound recomputation.

Operator scorer:

`python -I -B private/run.py score --roster private/ROSTER.json --index /packet/private/INDEX.json --index-sha256 <selected-pin> --packet-root /packet --submission /output/submission.json`

Construction is source plus authentic stimulus/header metadata and invented checks only. Full recordings and prepared authentic observations are absent; no state effects, model fits or scientific scores have been computed. Observational running/pupil associations are confounded, not causal. Sorting/QC and filtered pupil preprocessing are retrospective. The required complete-window unit-observation assumption is unverified; zero released events do not prove observed silence. The canonical explanatory-gain component remains incomplete. Source completion alone is not a gradeable or research-qualified task.
