# Source-bound single-person repair — local validation

This commit retains ERRMON-001 as an **easy descriptive methods control**, not
ERP CORE's 36-person ERN finding, a population/causal/clinical inference or proof
that Sol cannot solve it. The historical reference/export stage of MNE's modified
participant-001 release remains incompletely documented.

## Authenticated substrate and prospective recipe

- OSF version-1 archive: 92,046,226 bytes, published MD5/SHA256 verified.
  Three unchanged original members: 123,590,262 bytes total; upstream license
  README and release date retained. Member digests are locally measured.
- Source manifest SHA256:
  `31b2d095d29abb0236d2439b67c1a7fc7c301c2562ee46de74f399934095df60`.
- Public method SHA256:
  `e5725d66b28fdb429315721693dd740bc66cbf1cc3d6b92a2689e8a03e26fd1a`.
  Frozen before original EEG-value analysis after metadata and peer review.
- Offline runtime contains source and public method, not solution/tests/bank.
  No automatic source retries or implicit host caches. The initial archive
  acquisition stopped safely at an unallowlisted OSF storage redirect; after
  inspecting the exact content-addressed object, a narrowly scoped allowlist
  amendment succeeded. The zero-byte failed attempt remains preserved.

## Numerical and verifier evidence at commit

All 802 original annotations are accounted for: 400 paired/retained trials
(54 error, 346 correct) and two pre-stimulus orphan responses. All trials use the
same 820-sample epoch, 205-sample inclusive baseline and 103-sample measurement
window. The observed signed contrast is about −5.906579 microvolts, **not a
required sign, hidden target amplitude or paper replication result**.

Two separately implemented routes agree on all 328,000 epoch entries, with a
maximum difference of 2.84e-12 microvolts. A third, separately executed builder
uses only original source inputs and agrees within 3.65e-12 microvolts. It shares
MNE reading/filtering and verifier ledger/arithmetic; the independent route uses
an analytic Hamming FIR and full FFT convolution. Low-level numerical libraries
and FIF calibration are shared. These are not three wholly independent stacks.

The rebuilt 2,576,750-byte source-primitives bank has SHA256
`91ef6b0ae107a57a980331a71441e86a2370f0881f97a3e6047d3eecb518426e`.
The obsolete 35,234-byte bank (SHA256 `c13453fca50176b773ab10bc52eedef027b61c8162d030073bca0ade93fb9d96`)
was preserved externally, never used as a target, and replaced only after
original-source agreement and control checks passed.

Actual source-rereading stimulus-locked and EOG-inclusive-reference controls each
change all 328,000 primitive samples beyond the public tolerances. Both fail
numerical source fidelity before metadata comparison. No minimum effect gap or
desired direction was imposed. Other tests cover within-condition cancellation,
false scalar claims, incomplete/reassigned trial support, units, nonfinite data,
source identity and null handling. Legitimate ordering, float32/rounded voltage,
integral floating-point keys, alternative tool-version/warning representations
and free prose remain acceptable.

**347 native tests passed in 6.58 seconds, zero skips**: 211 source-free mechanics,
one complete grading check, and 135 genuine-source/equivalent/mutation cases
(six positives and 129 negative/control cases). Source-free acquisition,
extraction, metadata and independent-filter tests are separately recorded; they
are not extra independent scientific observations.

## Delivery boundary

The first clean-commit Harbor attempt at `054ae406b14ab9fde375a504d8e2818baa3a8a15`
obtained reward 1.0 but did not harvest outputs because `artifacts` was omitted
from task configuration. Its subsequent full-image check correctly failed on
missing harvested files (344 passed, one failed). Both records are preserved;
neither is used as final delivery acceptance. This follow-up explicitly exports
the seven-output directory, source manifest and public method, and adds two
source-free packaging regressions. The scientific contract is unchanged.

At commit, native validation is complete. Clean-commit Harbor oracle reward,
final immutable-image regressions and native/Harbor byte identity are subsequent
gates recorded externally so they bind this exact task digest without a
self-referential evidence commit. Do not infer those gates passed merely from
this file. Local tracking is under `tracking/pr_repairs_2026-10-01/pr-178` in the
repair workspace; original-run receipts are under `pr178-native` in the run
workspace. No Sol/model calibration, push, merge, data/image publication or
external deployment is claimed.
