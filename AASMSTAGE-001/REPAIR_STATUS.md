# Original-source repair: locally validated, final-container evidence separate

Six subject0–5/recording1 Sleep-EDF pairs form an easy tutorial-derived
collapsed-R&K method control. Not AASM rescoring, a Kemp classifier finding,
clinical validation or demonstrated Sol difficulty. Pooled class-recall mean
and pooled epoch accuracy are distinct legitimate estimands; no required gap,
class ordering, score threshold or variability is an acceptance condition.

## Source and prospective method

All twelve original EDFs, 298,590,434 bytes, were authenticated against the
published PhysioNet SHA-256 registry and baked into an offline portable image.
Source-manifest SHA256:
`241be998b50465f17431dba963499dbb34c355a2e17533a1dd0d659f4e837cbb`.
The public method was frozen before original EEG values/features/fits:
`5a935b2a61676fafab304fd28343c9720d11e1b7f3c3f5c7f2b12b2744527793`.
No old numerical bank or oracle output supplied the replacement reference.

851 original annotation rows yield 5,829 complete candidate chunks after the
public annotation-index crop: 5,828 mapped epochs and one unsupported movement
interval. Original TAL/sample/channel identities and calibration are retained.
Matching source header clocks and null annotation origin do not introduce an
extra time shift. Header prefilter text is preserved without claiming modern
anti-alias quality. Earlier failed header helpers remain in the external audit.

The previous instruction requested Welch while the oracle implicitly selected
multitaper. The replacement publishes Welch-256/Hamming/mean-removal details,
bin-mean normalization, absolute PSD diagnostics, six LOSO folds, all forest
parameters, float32 fitting inputs, own-probability argmax and undefined metrics.
Every source row, feature, held-out probability and derived summary is checked;
no prose-keyword or secretly exact near-tie label gate remains.

## Original-source checks

Native MNE-Welch, independent direct-EDF/NumPy-FFT, and separate source-only
direct-EDF/SciPy-FFT routes passed pilots and full six-fold runs. All 5,828 epoch
keys, truths, float32 forest inputs and held-out probabilities agree. Maximum
feature difference is 1.67e-16 within prospectively fixed tolerances. Native and
independent raw epochs are exact; selected PSD differences are within declared
diagnostic roundoff bounds. All six saved-tree states agree, and independent
tree replay and bootstrap-identity checks pass without fit warnings.

These routes share the pinned scikit-learn forest-training implementation.
Independent decoding, spectral arithmetic and tree replay do not establish an
independent implementation of training or scientific generalization.

The freshly source-built reference is 16,196,995 bytes, SHA256
`49e416e3f36eecd2cbcc9e85489fd8198327b96ff2d6c62f550380e5b6bb90f3`.
Both nine-file outputs validate against it after its independent construction.
The historical 2,456-byte bank is preserved outside the task and in Git history.
The runtime contains the intended original input files and public method
contract; oracle code, reference arrays and fitted models are not baked in.

## Controls and local regression

279 task tests pass with zero skips: 57 verifier-authoring, 35 source-builder,
14 pre-read file-safety, 33 oracle, 42 staging, 97 genuine-output and one grading
check. Genuine cases include six positive/equivalence variants, one public
contract check and 90 effective negative controls. A legitimate near-tie label
flip with consistently recomputed metrics is accepted. Tests do not require
every hypothetical wrong control to differ when publicly equivalent.

A separate actual method-omitted multitaper run holds source epochs, calibration,
LOSO memberships and forest seeds fixed. All 58,280 features differ beyond the
public Welch bounds; 622 labels change. Numerical feature validation rejects it
before metadata, and source-bound probability validation independently rejects
it. This isolates the estimator component, not a full historical-oracle replay.
Its 886-bin length-normalized PSD is not physically interchangeable with Welch
density; PSD-sum differences are diagnostic, not physiological power changes.
Three additional manufactured-array control-driver tests also pass.

After all original computations, two non-numerical pre-read checks were added
to reject non-regular method/manifest inputs instead of blocking on a FIFO.
Source, method, numerical functions, bank and acceptance tolerances are unchanged;
all 14 relevant failure/identity fixtures pass. The unused legacy
`solution/crop_contract.py` has no caller in the repaired pipeline.

## Delivery boundary

The local native evidence above is not itself a Harbor result. Clean-commit
Harbor, final-image regression, byte-identical public/private output and image/
source/task identities are recorded separately under the parent repair tracking
directory; consult that execution receipt for final-container status. Failures
and earlier evidence are retained. No Sol run, push, merge or public data/image
release is implied by this local repair.
