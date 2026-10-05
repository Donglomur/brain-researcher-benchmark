# WMMD-001: source-bound human diffusivity method control

This revision retires the former hidden high-b trap and unsupported
"unbiased MD" acceptance band. The task requests one of three public conditional
estimators on the original unsmoothed human CFIN acquisition: DKI all shells,
DTI b<=1000, or DTI all shells. Every declared configuration is acceptable.
There is no planted biological truth and no requirement to reproduce the
rat/Rician results of Veraart et al. (2011; DOI 10.1002/mrm.22603).

## Paper connection and data

Hansen & Jespersen (2016; DOI 10.1038/sdata.2016.72) describes the public CFIN
dataset; University of Washington ResearchWorks handle 1773/38488 supplies the
three original CC0 image/gradient files. The source manifest binds 173,719,934
bytes with published MD5 and locally verified SHA-256. Docker acquisition checks
all three before the task runs offline. Jensen & Helpern (2010;
DOI 10.1002/nbm.1518) provides the signal-model background.

The full native 96x96x19x496 signal is retained, without smoothing/rescaling.
The same low-b DTI-FA>0.5 ROI conditions all choices. This deliberately limits
the interpretation to an estimator-conditioned single-scan method case, not a
new cohort finding, exact named-paper result or ground-truth bias experiment.

## Public contract and verification

Instruction and a source/geometry/model-specific metadata template disclose
masking, shell selection, two-pass WLS, signal floor, eigenvalue floor, coefficient
order/units, fitted S0, prediction and residual definitions. Participant chooses
one model; authors validate all three. Equivalent implementations of that
specified estimator can pass. Broadly different estimation methods would define
a different target and are not silently treated as equivalent.

The verifier checks the complete exact ROI, every MD and FA, raw coefficients,
S0, raw-source residuals, numerical floor diagnostics and recomputed summaries.
It accepts reordered rows, not missing/duplicate/fractional/out-of-ROI
coordinates, unit guessing, a magnitude-shifted correlated map, arbitrary FA or
self-consistent fabricated summaries. It does not grade prose keywords or impose
an expected model ordering, MD plausibility band, or residual quality cutoff.

Independent authoring validation uses an independently constructed design matrix,
all-row tensor/prediction/summary algebra and 256 SciPy GELSD refits per model.
The full ROI definition still shares DIPY's mask/low-b TensorModel routines:
that dependency is disclosed, not called an independently validated segmentation.
Sixteen pinned DIPY helper comparisons provide implementation cross-checks.

## Evidence and limits

See REPAIR_STATUS.md for this head's measured validation. Prior unpinned and
partial-coverage results are superseded; they are not current acceptance evidence.
A clean local commit and offline oracle reward do not establish model difficulty
or scientific truth. This is labeled an easy/method control, with no new Sol or
other frontier run claimed. Local repairs are not pushed or merged automatically.

CPU limit 2, memory 8 GiB, no GPU; build-only original-source network access and
offline analysis. The reference bank remains verifier-side and is not copied
into the agent image. Scoring is all-or-nothing.
