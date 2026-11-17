# Source and prospective choices

Primary article: https://www.nature.com/articles/s41586-024-07309-z
and https://pmc.ncbi.nlm.nih.gov/articles/PMC11078732/ .
Official code: https://github.com/rutishauserlab/SBCAT-release-NWB at
a25e8cc3f61630a428f190381745257d4506f148 .
Official data: https://doi.org/10.48324/dandi.000673/0.240118.2135 .

The author LFP demo fixes subject4/session1/channel49 and a supplied stratified
trial mask. Its cfc_tort_comodulogram pools trial samples for18-bin Tort MI with
Hamming FIR/Hilbert transforms. Frequency-dependent high-frequency passbands and
the theta/high-gamma summary are preserved here. The demo disables surrogates;
the paper used200. The original helper shuffles trial order with a nonfixed seed.
Neither demo provides full clinical masks or the new patient-level adjusted
accuracy endpoint. The paper reports additional waveform/harmonic checks not
implemented by these example helpers.

Prospective differences are explicit in public/TASK.md: full anatomical
hippocampus-plus-co-located-unit eligibility, endpoint-safe finite filtering,
matched covariate/caliper support, deterministic surrogates without fixed points,
MI subtraction rather than surrogate-SD z-scoring, patient hierarchy and new
accuracy contrast. Harmonic PLV/slope and temporal-half diagnostics do not certify
cross-oscillator mechanisms. No author result scalars are used as grading gold.

The2026ripple repository expects a different NWB schema. This implementation uses
the inspected2024acquisition/LFPs and intervals/trials paths and rejects unexpected
rate/shape/coding rather than guessing. A per-unit multi-electrode ragged mapping
outside verified one-electrode associations remains unsupported. The actual
44-file panel may expose further schema cases; no native preparation was run.
