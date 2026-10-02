# EYESTATE-001 local repair — native validation passed

This revision retains real ABIDE PCP data as the user-approved **confounded
protocol-label prediction method case**, not a reproduction of a paper finding
or an identified biological eye-state effect. It is an easy/method-control
candidate; Sol difficulty is unmeasured. Local code changes are not pushed.

## Source and prospective method

- Authenticated 1,036 unchanged original files, 406,540,381 bytes, by fresh
  conditional HTTPS retrieval and equality with read-only cached SHA-256.
  Phenotype is the named S3 version of `Phenotypic_V1_0b_preprocessed1.csv`;
  ROI versions are literal `null`, not an immutable upstream release. ETags
  are opaque conditional identifiers, not presumed published checksums.
- Complete 1,112-row source ledger: 77 unavailable derivatives; all 1,035
  named arrays finite, 200 columns, 78–316 frames. Source header order `#1`
  through `#200` is preserved, without invented anatomical labels or TR.
- Source selection is not newly quality-filtered: 46 people have constant
  columns, up to 118 of 200. All remain under the predeclared no-extra-QC
  rule with explicit per-person diagnostics. Uniform brain coverage is not
  established.
- Twenty named SITE_ID groups, 18 single-label and two mixed-label; 700 open,
  335 closed. These are metadata groups, not 20 independent scanner systems.
- Public source manifest SHA:
  `d4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb`.
- Public method SHA, frozen at 2026-10-02 08:31:08 UTC **before original
  connectivity or fits**:
  `1ca199337071a0342c0445a2d9f85021b16b6909723a1913e16d00111f39ab18`.
- The initial LinearSVC pilot failed after 528.07 seconds, reaching 30,000
  iterations with a convergence warning and failing the unchanged certificate
  (`G=5.12e-5`, limit `1.05e-6`). Candidate, failure records and v2 files are
  preserved; it is not counted as an oracle pass.
- V3 changes only the supplied solver and its honest execution documentation
  to an equivalent Cholesky-dual BVLS recipe. Frozen at 2026-10-02 08:51:20 UTC,
  before any original BVLS fit, SHA
  `28e752741e0763a422e54243146dbad967abc92e936e3f4c5979173b916f489d`.
  Cohort, source, features, splits, objective, certificate and all acceptance
  tolerances remain unchanged. No prediction accuracy selected this change.
- The v3 BVLS pilot failed safely in 14.39 seconds: raw solver success/status1,
  71 iterations, no warnings, but six coefficients were negative at roundoff
  scale (minimum about -4.24e-22). No certificate was evaluated after that
  failed precondition. Raw candidates and v3 files remain preserved.
- V4 explicitly retains raw coefficients, rejects nonfinite/malformed output,
  and projects `alpha=max(raw_alpha,0)` before recovering the candidate and
  applying the same certificate. No epsilon or correction-size threshold.
  Frozen before original projected-BVLS fitting at 2026-10-02 08:56:37 UTC,
  method SHA `2cc71a311a25ec5de5bf14d5e2d10097b7e609eba93ea8be273f63f7de08a4a0`.

The revised contract makes population-SD standardization, Ledoit-Wolf
correlation, original-row split allocation, train-only scaling and the
intercept-penalized squared-hinge objective explicit. The replacement reference
uses BVLS tolerance 1e-12 and cap 30,000, without a fallback. Each submitted model
must satisfy the public source-derived primal-dual gap bound and reproduce its
own held-out scores; no hidden reference model/labels or forced score ordering.
Pooled OOF balanced accuracy is primary; equal-site recall is separate.

## Verification design and current boundary

Eight source/derivation artifacts replace aggregate-only scoring. The verifier
reconstructs canonical float64 features directly from authenticated originals,
checks model optimality on the correct training rows and recomputes all support,
confusion, pooled and baseline metrics. No giant derived answer bank is added
to Git. The historical numerical bank is preserved outside the task and is
not used to choose or score this revision's outputs.

Source authentication, structural inspection and local portable staging passed.
The projected-BVLS oracle completed all 30 folds in 183.04 seconds; an independent
original-source implementation using manual feature/scaler arithmetic and a
Cholesky/NNLS solver completed them in 106.93 seconds. Both emitted all eight
artifacts and 2,070 held-out prediction rows, with no warnings. These routes
share the mathematical dual and low-level numerical libraries; independence
does not mean independent data or a separate scientific replication.

The full canonical-source acceptance check passed in 59.30 seconds. Maximum
feature differences are 2.22e-16 (oracle) and 2.44e-15 (independent); maximum
own-score replay difference is 2.89e-15. Every model satisfies the unchanged
certificate. All 30 optional raw/projected dual records match retained private
checkpoints. There is no cross-route parameter, prediction or accuracy gate.

Actual source-derived Pearson and all-subject-scaling component substitutions
are both rejected numerically by the primitive and complete graders. Pearson
differs on 20,522,140 of 20,596,500 feature values; global scaling differs on
596,997 means, 596,996 variances and 596,993 scales (597,000 each). These are
explicit component controls with no refitted models or new accuracy claims.

All **313 native tests pass**, with zero skips, failures or errors: 227 source-
free checks, one grading check, six genuine/equivalent positive cases and 79
negative/control cases. The complete suite took 211.60 seconds. Final-image
and clean-commit Harbor/artifact checks remain separate pending executions at
this commit checkpoint. Source-free fixtures alone are not original-data
validation. Authoritative receipts
are under `tracking/pr_repairs_2026-10-01/pr-179` in the local audit workspace;
the final receipt, when present, binds the commit and execution artifacts.

The source remains subject to the official ABIDE noncommercial, attribution,
share-alike and registration conditions. The usage page links CC BY-NC-SA 3.0;
public S3 access is not commercial-use clearance. Historical preprocessing and
atlas-export lineage remain qualified. No data/image publication, external PR
write, causal/paper claim or model-agent difficulty calibration is part of this
local repair.
