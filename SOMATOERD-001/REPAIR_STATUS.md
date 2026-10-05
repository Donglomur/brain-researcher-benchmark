# Repair evidence — original-source validation before clean-commit Harbor

The prior first-pass patch and legacy numerical bank are not acceptance evidence
for this revision. Public method/metadata, offline source staging, complete
power receipts and independent checks have been rebuilt from original data.
No Sol/frontier run or publication is authorized/claimed.

Original OSF archive version 8: 610,074,171 bytes, published MD5
`9a191907b326b9402341ee7a0d1240d8` and SHA256
`f7008b866b9fd7ed19659b571b0c19a27125d339995c2ebcf6da4bbd4ebc7feb`
both verified. Stale HEAD size 617,674,189 was not used to change either hash.
Only ten explicitly allowlisted regular members were extracted; no symlink,
anatomy or derivative tree was followed. Dataset metadata identify PDDL/Lauri
Parkkonen; the conversion script is separately BSD-3-Clause.

Original FIF: 343,680,860 bytes, SHA256
`71bb33cb530fe6bf289c492deac5bc184da7ee0dbbc964203a59175cda32ffc3`.
Header/STI-only inspection finds 316 channels (204 gradiometers), sampling rate
300.3074951171875 Hz, first sample 237600 and 269400 source samples. There are
111 code-1 onsets; original relative sidecar samples align exactly after adding
first_samp. No source bads, projectors or annotations are recorded. These counts
are measured source properties, not inherited numerical acceptance bands.

Scientific scope: one already processed source recording, four fixed sensors,
total trial beta-power change. The upstream conversion reads `sef_raw_sss.fif`;
we do not independently validate SSS. The 1999 review anchors the calculation,
not this acquisition or numerical finding. No induced-only, contralateral
localization, precise onset, population or hard-task claim remains.

## Measured local validation

Original-data execution retained all111 events,4 sensors,16 frequencies and901
source-clock samples. The signed total-power change is **−17.727311581457055%**.
This is a conditional method output, not a population physiological estimate.
There are57,664 full mean-power rows and7,104 per-trial/channel/frequency window
rows, plus the full original event ledger. The baseline's near-stimulus wavelets
extend past stimulation; that fixed-window limitation is disclosed publicly.

The separate checker uses the same MNE FIF reader but independently detects binary
triggers, validates original sidecar events, slices epochs, constructs analytic
Morlet wavelets and runs SciPy convolution. All original selected epoch samples
match exactly; the full percentage curve differs by at most4.2633e-14 percentage
points. All mean/window powers pass source-baseline-scaled tolerances;18 direct
convolution checks pass. Upstream SSS, the original acquisition, reader and numeric
libraries are shared, not independent biological validation.

The bank was genuinely rebuilt after reloading original epochs and independently
recomputing wavelets/powers:551,662 bytes, SHA256
`98620683b7f83c6decdcc69c77318bc9f886c03cfe0e8e53945d2f7aca4d9df0`.
The full offline native matrix passes **217 tests**, zero skips, including genuine
independent outputs and51 altered-output negatives. One expected wrong-channel-
type synthetic fixture emits a unit-change warning; original-data runs do not.
The verifier does not require identical software versions or prose phrases.

A mistyped test filename prevented one initial matrix invocation from starting;
the failure log is retained and the corrected matrix above passed. Independent
checker review also added an explicit nonfinite-time guard and three fixtures;
the complete original-data independent run was repeated after that guard change.
No scientific settings, expected values or tolerances were changed to pass tests.

Pending at this commit: exact clean-commit offline Harbor oracle and regression
rerun against its actual image/output, then final Sheet update. Authoritative
post-commit results are recorded outside this worktree in
`tracking/pr_repairs_2026-10-01/pr-160/receipt.json` and its unedited command logs.
This keeps the tested clean commit separate from subsequent execution claims.
