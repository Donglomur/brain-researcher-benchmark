The required source is Zenodo21645651. Obtain both mainData1.mat
(2,408,952,933 bytes, MD5 f2d3b27ebbbd99a58c6ff62e8b473a58) and mainData2.mat
(3,002,001,774 bytes, MD5 1f163dee80ad4baf1574e581954f0213) from the exact routes in
SOURCE_IDENTITY.json. Neither recording is bundled/acquired. This exceeds this
construction's300MB retained-file cap; no acquisition is performed by this package.
The author code README references a separate README_DRYAD.md that is absent from
the authenticated code archive. The later versioned source notes resolve several neural/identity mappings; authentic
cohort geometry and complete native clocks remain unverified.

Future operator-only projection, after inputs and capacity are available:
1. In MATLAB R2025a, call export_source(DATA_DIRECTORY,FRESH_RAW_OUTPUT).
   It verifies both source MD5s, loads both partitions, resolves all declared GrC
   delay pairs and exact chronic cell matches, retains every recorded trial and
   writes little-endian C-order float64 tensors plus a complete v2 INDEX.json.
   The index preserves every source-session disposition and every oriented
   registration row, including structurally unmatched zero-sided rows.
   It does not run MainData.m, refit preprocessing, compute author figures or fit
   models. Ambiguous equal-max registration columns and nonfinite matched values
   refuse the whole cohort. The150MB projection cap refuses rather than trims.
2. Authenticate INDEX.json as an operator-selected descriptor. With NumPy2.2.6,
   run prepare.py --source-root RAW_OUTPUT --index-sha256 AUTHENTICATED_SHA256
   --output FRESH_PACKET. Linear interpolation and deterministic whole-condition
   splitting produce public one-second arrays and private two-second arrays.
   Training-only scale, absolute mean trajectory and fixed piecewise warped mean
   are prepared from exactly the public calibration+validation support without
   scoring predictions. The warp interpolates the public grid and never extrapolates. A fresh private HMAC key makes opaque identities; the key
   is excluded from any candidate delivery. Identity and support remain operator-private;
   binding-v2 captures the exact identity-map descriptor and grade validates its
   public axes, reconstructed graph and repeated-session support. Rebuilds have fresh IDs and bindings and cannot
   be mixed. Binary output is capped70MB plus bounded JSON; actual totals must be
   checked before retaining both packet and export under the cumulative300MB cap.
3. Bind complete generated public/private descriptors into a versioned delivery
   successor; preserve this partial source export. Do not label the current
   package bundled or locally gradeable before those actual files exist.

Unresolved facts that must be reported rather than guessed: actual session/mouse
and matched-cell counts; registration column orientation when maxima are equal;
source trial order chronology; complete clock coverage and units; optional fields
and nonfinite values; final projection size and MATLAB loading memory. The native
exporter is source-reviewed only. Earlier Python interpolation/scorer had generated controls; this successor has
AST/metadata/shape-only checks only, with numerical checks retained but unrun.
A matched GrC with unavailable mandatory samples is not silently removed.

Original processed data are publicly released, so candidate isolation is local
rather than proof of no previous exposure. Rights/attribution for redistribution
remain separate from the missing local source data. Source code provenance is
preserved in source/MainData.m and source/README.md; cite the published paper and
versioned dataset for any future use.

The source-only v2 report includes every declared selected pair and its full trial
support; any unsupported required pair refuses the entire preparation. It does not
create an empirical report for failed acquisition or claim zero biological gaps.
All declared structural exclusions are preserved in the census/registration rows.
No component-balanced sensitivity is supplied until a separate normalization and
estimand are selected; the exact existing primary retains recurrent-pair weighting.
