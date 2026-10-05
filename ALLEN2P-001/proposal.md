# ALLEN2P-001 — single-field dF/F selectivity method control

This task retains the original public Allen Brain Observatory two-photon session
501271265 (VISp, 175 µm, Cux2-CreERT2, session A). It measures custom two-point
OSI/DSI threshold flags in all released cell traces and optionally evaluates a
specified split-trial sensitivity. It is an **easy/method control**, not an
established hard task or a reproduction of the paper's selective-neuron prevalence.

## Paper relationship and estimand

[de Vries et al. 2020](https://doi.org/10.1038/s41593-019-0550-9), Figure 3 and
Methods sections on stimuli, dF/F, event detection and response metrics provide
the source experiment and tuning context. The paper's detected-event analyses
use a responsiveness condition; this task instead averages archived dF/F over
explicit half-open source-frame windows and retains every cell in one field.
The paper's repeated-split signal correlations do not prescribe this task's
50-split selectivity procedure. No cross-area/layer/Cre or biological prevalence
claim follows from this field.

Both `same_trials` and `repeated_split_mean_ratio` are accepted when correctly
declared and computed. Same-trial preference selection is an in-sample statistic.
Splitting separates preference selection from evaluation but changes sampling
precision and ratio denominators too; it does not yield an unbiased truth or
isolate the size of selection bias. Signed and near-zero denominators can produce
large or negative finite ratios; these are retained and disclosed, not silently
clipped. Averaging ratios then thresholding differs from averaging split-specific
fractions; both are separately named, with no conflation or required direction.

## Source, offline packaging and terms

The single original released NWB is 565,631,796 bytes. Its local SHA256 is frozen
in `environment/source_manifest.json`; the build fetches and verifies exactly
that file, then the agent runs offline. S3's `VersionId=null` and multipart ETag
are not immutability or a published checksum. The official API file attachment
and Allen-owned mirror establish lineage, but only the mirror body was acquired.
No separate analysis/event output, raw movie or other session is used as input.

The NWB has 215 cell rows, 115,755 frames, 628 presentations (598 nonblank), and
40 nonblank conditions. Stored cell identifiers are not sorted. Two conditions
have 14 rather than 15 trials. `unit="frame"` on the dF/F dataset is a legacy
metadata inconsistency; use the DfOverF semantic path without added scaling.
Upstream image processing is unverified here; eye tracking failed.

[Allen's terms](https://alleninstitute.org/legal/terms-of-use), linked from the
[official AWS registry](https://registry.opendata.aws/allen-brain-observatory/),
carry research/noncommercial and attribution constraints, separate from the SDK's
software license. This repair's local validation is not clearance for public
data/image distribution. The manifest records these constraints, not a legal opinion.

## Verification design

The public contract fixes source row pairing, presentation timing, precision,
signed response definitions, ties, RNG axis, undefined support and aggregation.
Eight participant files expose source trial responses, condition means, selected
conditions and measurement components. The private bank is rebuilt by reading
the verified original NWB, not by keeping the legacy per-cell answer arrays.

The verifier checks complete source identities and numerical values and
recomputes each declared method's estimates and summary. It does not accept a
rank-preserving affine distortion, a copied headline with fabricated intermediates,
clipped metrics or a changed all-cell denominator. It does not grade prose
keywords, force split values lower, infer biological truth, or award partial credit.
Synthetic fixtures test mechanics only; genuine original-source positives and
independent numerical checks are separately required before recording completion.

## Evidence and resources

See `REPAIR_STATUS.md` for this revision's executed evidence, limitations and
pending gates. Earlier Step-0 values, robustness claims and unrelated historical
oracle rewards are not validation of this revision. No frontier/model calibration
has been run for the repair; published-source numeric answers also create a
contamination boundary for any future difficulty assessment.

CPU-only: 2 CPUs, 4 GB RAM, 0 GPUs; NumPy 2.2.6 and h5py 3.13.0 on Python 3.12.
Only the build requires network access to one pinned source asset. No heavy SDK
runtime, hidden estimator, or synthetic substitute cohort is required.
