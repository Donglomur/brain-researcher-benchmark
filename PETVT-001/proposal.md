# PETVT-001: conditional arterial-input sensitivity

This repair retains seven baseline participants and released ds005619 1.1.0
gtmseg TAC/manual-blood sources. It replaces historical outcome matching with
an explicit two-assumption methods application. Blood sample times do not
resolve the activity decay-reference time: both already-image-reference and
sample-time-reference interpretations remain assumptions, not conclusions
inferred from model agreement or fitted magnitude.

The public protocol fixes an equal-weight 68-region cortical composite,
30-minute unweighted Logan/MA1 fitting, exact transformed-input piecewise-linear
integration and frame-duration tissue integration. All seven people and all
28 fit slots remain visible. Signed estimates and unavailable input/rank/
denominator support are retained. There is no answer band, required direction,
model-agreement requirement or historical reference-array target.

The human SF51 study and classical estimators supply context, not target
answers. This composite graphical-model application is not a reproduction of
the paper's regional two-tissue-compartment fits. The small cohort and unresolved
input-reference assumption do not establish tracer validity or genotype effects.

## Sources and verification

The manifest fixes 31 original Git blobs (481,091 bytes) at snapshot 1.1.0,
commit `358a370c010a792484585b80d28adb699ec28927`. Acquisition checks Git blob
and SHA256 identities. Originals and public contracts are exposed in the image,
with no fitted answers. Runtime and grading are offline.

Every blood row stays in the ledger. Exact duplicate-time, identical plasma/
parent pairs are coalesced without averaging; no undocumented padding deletion
is allowed. This representation rule was frozen after a bounded structural
equality diagnostic and before fitting.

Independent source parsing, composite/integral construction and result replay
replace the old answer bank. Both routes use the declared SciPy least-squares
solver; independent SVD software is not claimed. Accepted source-close
coefficients drive each endpoint and summary once. Public conditioning protects
the MA1 quotient without a second canonical V_T gate. Complete-seven summaries
report missing support instead of changing denominators.

## Validation status

Manufactured math/parser/source/replay/entrypoint qualifications passed before
original fitting. Independent static review identified and corrected a CSV
coefficient-receipt tolerance mismatch and an RSS-only overflow status mismatch.
The fixed-subject original pilot passed independent route checks, followed by
the full seven-person oracle and independent grade. The clean image passed
187 tests: 168 manufactured cases, four genuine/representation positives,
14 effective rejection controls and one production source-bound test. Its
40-file application inventory was independently audited as opaque hashes,
with no fitted outputs or private code baked into the image. Clean Harbor
delivery is recorded separately in external receipts; model difficulty has
not been calibrated. Historical outputs and failures are external audit only.

Difficulty is provisional. Passing demonstrates implementation of the declared
sensitivity analysis, not resolution of the true blood-reference convention or
external scientific validity.
