# PETDVR-001: reference-Logan fixed-window sensitivity

This is an easy, original-public-data **method control**, not a hard reproduction
challenge. It retains OpenNeuro ds001420 snapshot 1.2.0: four deposited PETPrep TAC
tables from two people. It asks how a declared simplified reference-Logan calculation
changes with fit start and available scan duration, and requires source-bound numerical
evidence for every case.

## Paper and data relationship

[Logan et al. 1996](https://doi.org/10.1097/00004647-199609000-00008), Equations 6–7,
motivate the distinction between the efflux-adjusted and simplified reference graph.
We do not adopt a tracer-specific efflux constant or claim that a straight graph proves
the simplification valid for DASB. The fixed window grid and frame-average integration
are public task conventions, not a numerical reproduction of that paper.

[PET-BIDS 2022](https://doi.org/10.1038/s41597-022-01164-1) describes the dataset-format
context. Dataset DOI: [10.18112/openneuro.ds001420.v1.2.0](https://doi.org/10.18112/openneuro.ds001420.v1.2.0).
The exact published snapshot declares CC0; Cimbi and dataset authors are attributed in
the manifest. An older unversioned license statement is not used to characterize this
snapshot. Direct Git blob identities or verified Git-annex pointers plus MD5/size bind
the original files; measured SHA256 pins are additional integrity checks.

These are archived derivatives, not a rerun of motion correction, segmentation or TAC
extraction. There is no TAC-specific units sidecar or exact extraction revision. The
supplied reference belongs to the AGTM extraction stream and must not be relabeled as
the same uncorrected bilateral cortex average used by PETREF-001. The high-binding
composite's exact weighting is not established here.

## Repaired contract

- Public frame-average midpoint integration and unweighted intercept-bearing OLS;
  no hidden residual threshold, automatic t-star, six-frame fallback or upper/lower
  physiological answer band.
- All seven targets, four scans and ten declared windows: 280 fit records, including
  explicit insufficient/rank-deficient cases. Separate graph and concentration-ratio
  masks and all source frames remain auditable.
- Actual fit support, signed residuals, concentration-ratio dispersion/time slopes,
  signed paired changes and descriptive summaries are checked numerically.
- One scan is 53.6 minutes and three are 90 minutes; native comparisons retain this
  limitation. Even common50 ends at 48.6 versus 50 minutes on original complete frames.
- Independent original-source calculation and bank; complete coverage rather than
  accepting a fixed fraction of cells. Genuine equivalent calculations must pass;
  malformed, omitted, shifted, clipped and fabricated calculations must fail.
- Build-time pinned source acquisition; agent and verifier run offline. No fitted
  answer tables or reference bank in the environment image.

The obsolete proposal's equilibrium-aware headline, all-frames bias percentage, MA1
equivalence and tracer-validity claims are withdrawn. This version does not choose
which window is physiologically correct. It does not equate two repeat scans with two
independent people. A successful oracle establishes implementation consistency only;
Sol difficulty has not been measured for this repaired task.

See `REPAIR_STATUS.md` and the external execution receipt for validation state and
artifact identity. Local repair does not imply the upstream PR was pushed or merged.
