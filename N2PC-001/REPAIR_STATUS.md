# Local repair evidence — fixed12 N2pc method control

This repair is an original-data, twelve-person lateralization method control,
not the paper's cleaned N=35 result or a demonstrated hard task. The public
200–300 ms endpoint differs explicitly from the paper's recommended 200–275 ms.
No Sol/frontier calibration has been run.

All 24 OSF version1 raw SET/FDT originals (1,051,981,416 bytes) were authenticated
against published SHA256 and MD5 and baked into the offline runtime. Transport
failures, the separately gated unchanged subject13 recovery, and a structural
parser failure/correction remain preserved in external receipts. Neither a
missing person nor an unavailable source was silently replaced.

Source-first structural inspection established 1024 Hz, 33 channels, 7,716
source events, 3,847 target candidates and one subject8 discontinuity. The
public operator and precision were fixed before original signal analysis.
Manufactured near-zero arithmetic exposed a sign-count ambiguity; before any
original signal decoding, the count rule was clarified to follow numerically
accepted submitted person values. All amplitude tolerances remained unchanged.
Current method SHA256:
`1da14bc2c9dc043a881c82f3b540c9f82fc71737ce2b0e829c62f8a9a23d319c`.

The oracle uses MNE's EEGLAB reader and segmented FIR. The grader independently
authenticates original bytes, decodes little-endian FDT, constructs the analytic
Hamming/sinc filter and reconstructs complete keyed prebaseline epochs before
recomputing signed outputs from accepted submitted samples. Shared bounded MAT
metadata scanning and low-level NumPy/SciPy dependencies are disclosed; this is
not a claim of fully independent software stacks.

Native original-data evidence:

- The predeclared subject8 pilot passed both paths and all eight artifact checks.
- Full12 validation passed: 3,847 retained epochs, 1,923 left/1,924 right;
  maximum primitive difference 6.66489086142974e-12 microvolts.
- The whole task suite passed **285 distinct cases**, zero failures/errors/skips:
  284 manufactured cases and one full original-source production grade.
- Including the extra -205 baseline sample and count-weighting target fields
  were each rejected numerically after coherent recomputation. Original
  annotation/epoch files remained byte-identical; the genuine output stayed
  unchanged. These are component diagnostics, not model-difficulty evidence.
- A pristine image check authenticated all originals and public documents
  without source decoding, solution/tests mounts or derived answer assets.

The old numerical bank was preserved externally as opaque bytes before removal,
never loaded as an answer target; obsolete cache helpers remain Git-recoverable.
Discontinuity segmentation is a disclosed correction, not promised equality to
the old bank. Units are an explicit EEGLAB/MNE convention, not independently
measured physical calibration. Ocular/behavioral/ICA cleaning is not claimed.
Node CC-BY and resource-page CC-BY-SA notices remain distinct; no license
precedence or redistribution-rights conclusion is implied.

This document records **pre-commit native evidence**. Clean-commit Harbor and
final-image acceptance are recorded separately after the commit in
`tracking/pr_repairs_2026-10-01/pr-185/final_receipt.json` in the local audit
workspace. Their success must not be inferred from this document alone.
Harbor is configured to retain all eight outputs and source/method manifests.
No push, merge, PR comment, model calibration or public data/image release.
