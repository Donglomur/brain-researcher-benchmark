## ALPHABAND-001

**Proposal:** A modern descriptive replication of the Berger alpha effect.

**Scientific scope:** Berger (1929), *Über das Elektrenkephalogramm des Menschen*,
motivates the eyes-closed versus eyes-open posterior-alpha contrast. The data here
are not Berger's original participants or recordings. This task measures that
qualitative contrast in five modern participants; it does not reproduce a named
numerical result, figure, or table from the original paper.

### Fixed public substrate

[PhysioNet EEG Motor Movement/Imagery Dataset v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/),
Schalk (2009), DOI [10.13026/C28G6P](https://doi.org/10.13026/C28G6P), provides
64-channel, 160-Hz EDF+ recordings under the Open Data Commons Attribution License
v1.0. Subjects 1–5, runs 01 (eyes open) and 02 (eyes closed), are the only inputs.
Also cite Schalk et al. (2004), *BCI2000: A General-Purpose Brain-Computer Interface
(BCI) System*, IEEE Transactions on Biomedical Engineering 51(6):1034–1043.

`environment/data_manifest.json` pins each recording to the SHA-256 published in
the dataset's versioned `SHA256SUMS.txt`; these are upstream checksums, not merely
local observed hashes. Docker builds download and verify the ten originals once.
The agent, reference solution, and verifier run offline with no host dataset cache
mount. Neither oracle code nor reference numerical answers are copied into the
agent image.

### Public measurement contract

The instruction specifies full-recording Welch PSD: 2-second segments, 320-point
FFT, periodic Hamming window, no overlap, per-segment DC removal, mean segment
aggregation, and common-average reference across all EEG channels. Normalize EDF
labels and average density over inclusive 8–13-Hz bins and O1/Oz/O2, in V²/Hz.
The headline is the arithmetic mean of the five individual EC/EO ratios, not the
ratio of pooled group powers. A whole-head ratio is a descriptive comparison.
Equivalent implementations are acceptable; MNE-specific APIs are not required.

EO precedes EC for every participant. The contrast is therefore descriptive and
does not separate eye state from recording order or establish population-wide
causality. Five participants are not a population-generalization sample.

### Verification and evidence boundary

The verifier checks every subject's positive EC/EO densities and ratios, exact
cohort membership, EC/EO arithmetic, headline/table consistency, and the public
PSD metadata. Numerical reference tolerance is separate from output consistency.
Reordered subjects and reasonable numerical rounding must pass; wrong channels,
units, missing/duplicate subjects, and inconsistent aggregates must fail.

The pre-existing bank records a mean occipital ratio of 19.641 and whole-head mean
of 4.374. Its contents are a prior reference, not proof of a fresh execution.
Fresh source-to-measurement and in-container oracle evidence, with exact command,
input hashes, actual outputs and verifier stdout, is retained separately by the
maintainer. Reference-copy regressions are labelled as such.

### Benchmark role and cost

**Easy control / qualitative replication.** Channel normalization is part of the
public contract, not a hidden scientific lever. No model-family difficulty claim
is made; frontier calibration has not been run on this repaired task. The previous
public numerical answers also preclude treating an unqualified future success or
failure as contamination-free evidence of hardness.

CPU-only: 2 CPUs, 8 GB RAM, no GPU. Build-time network access fetches ten short
recordings; runtime network access is disabled. Numerical and verifier dependencies
are installed in the image at pinned versions.
