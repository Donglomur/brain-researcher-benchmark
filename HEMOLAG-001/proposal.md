# HEMOLAG-001 — proposal

## Topic → paper (from the BLOCKED-reserve stroke hunt)
Topic: **stroke** (previously BLOCKED — no reachable data). Anchor: Siegel et al. 2016, *PNAS* — "The
effects of hemodynamic lag on functional connectivity and behavior after stroke." Data: OpenNeuro
**ds003999** post-stroke resting-state, reached via the S3-HTTPS + dipy-affine + CompCor pipeline
(provenance in `data/`). Second task on OpenNeuro clinical data (after TRANSDX-001).

## The un-cued trap (hemodynamic-lag / signal-timing axis — an EMPTY lane)
The task asks to map post-stroke "disconnection" from resting FC — without mentioning perfusion timing.
The trap: hypoperfused tissue has a **delayed BOLD response** (hemodynamic lag of seconds), and standard
**zero-lag** correlation is corrupted by it — a lagged region looks weakly connected because its signal
is time-shifted, not because it is neurally disconnected. Measuring FC at the optimal lag
(cross-correlation peak) recovers a substantial share.

Validated (ds003999, 25 patients, TR=3s): regions with >1s lag have zero-lag FC 0.17 vs 0.34 (deficit
0.165); lag-correction recovers ~36-39% of that deficit; regional lag predicts the recovery (r≈0.3). So
~40% of the apparent "disconnection" in lagged regions is a perfusion-timing artifact.

## Distinctness
A genuinely NEW axis — **no built task touches hemodynamic lag / signal-timing confounds of FC.** Not
motion (DEVCONN), not volume-conduction (EEGVC), not GSR (SOCIALBRAIN). Within-patient design (Siegel's
own), so no scanner-confounded control group. Fills a completely empty lane.

## Honest risks (for the difficulty gate — flagged, not hidden)
- **Modest magnitude**: only ~5% of regions show >1s lag and the recovered fraction is ~36-39% — the
  weakest-numbers task in the suite. This is largely a **TR=3s limitation**: lag can only be corrected in
  whole-TR (3s) steps, so sub-3s delays stay uncorrected; a finer-TR acquisition (Siegel used ~2s +
  interpolation) would show a larger, cleaner effect. The recovered fraction is a reported **lower bound**.
- Small N (25) + lightweight preprocessing (affine + CompCor, not fMRIPrep). Connectomes/timeseries
  shipped as data (full pipeline exceeds the oracle timeout).
- Kept (rather than dropped at Step-0) per the written standard: it sits in an **under-crowded lane**
  with a **real measured signal**, so the stage-4 difficulty gate is the proper culler.

## Grading
`test_connectivity_computed` — a reduced-connectivity result is present. `test_recognises_hemodynamic_lag`
— findings.md names the hemodynamic-lag / perfusion-delay / BOLD-timing / lag-correction issue AND that
reduced zero-lag FC does not by itself mean neural disconnection. Oracle passes; a naive "these low-FC
regions are disconnected" report fails.
