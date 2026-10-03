# SOCIALBRAIN-001 frozen pre-signal analysis contract

Status: `frozen_pre_signal_v2`. These external public documents bind the already approved operators and tolerances before the first BOLD numerical pilot. This freeze is not execution authority; separate bounded pilot/full gates remain necessary. No task files or source payloads were changed to prepare it.

## Fixed identities and structural facts

- Source manifest: `9458c48ac61e1e8b0ee36d513ebf6e7613e889a9895747ca46d4c7bd50af8d0b`; closed 330 members / 942,572,457 bytes, plus its identical internal manifest.
- Method: `fb75a7cc8858de75f4269175d57c41cb70bf182409c0c68410931976672c5a12`.
- Output schema: `f1388ffa06e5a04a684287724e5b86e914896980f4e0c7fa3366c8d1bd2f23c4`.
- Shared reporting kernel: `89db8ca04db493d5f8522246200b7c8b11562856b2fb977f201748b1ebb1f4d6`.
- Exact anatomical template: `421a10e872fd6cadae7f61d358dffbcc1795a497d61ee76c5dda2503e1a1e9e6`.
- Authenticated structure retains all 155 literal `sub-pixar001`–`sub-pixar155` participants: 122 children and 33 adults, 168 frames each, 26,040 total. Original `Child_Adult` labels govern membership, not a new age cutoff or the dataset description's older 50-child summary.
- All fifteen selected confound columns are finite at every frame. The frozen missing-token list is empty; no imputation occurs. The first FD entry, including a finite zero, is observed and enters the accurate `math.fsum/count` FD mean.

Structural receipt `3930bad5d496457116ca00a299637d3dbaba8e1f108f7d1e09ed2157cdced56f` originally reports `structural_issues` for unknown units and unresolved header clock. Those flags are retained, not relabelled as clean headers; the following approved documentary interpretation resolves them.

## Spatial and clock interpretation

BOLD shape is 50×59×50×168 with signed-byte storage, common 4-unit selected-affine spacing, raw zooms [4,4,4,1], and unknown spatial/temporal units. Every original header is retained. There are 155 distinct original scaling pairs: convert stored values to float64, then use that file's effective slope and intercept, without inventing common scaling.

Pinned Nilearn 0.12.1 release code/description state 4-mm derivatives; the original processing README documents MNI152NLin2009cAsym normalization and the downsampling matrix. The exact template has shape 197×233×189, unknown raw units and the release-documented 1-mm convention. These documents establish operational millimeter coordinates without rewriting headers or asserting verified individual registration or identical template editions.

The released code documents a 2-second TR. Raw temporal zoom 1 with unknown units is not a measured one-second TR, nor is the documentary 2-second value recovered header timing. Detrending uses original frame indices; no temporal filter or measured movie-onset/slice-reference alignment is claimed.

Template-only geometry receipt `fdb5b32e7509c219954d7be15b3d4aebf867b9a4358e27d1d706533b35570d50` records one shared grid, exact independent/oracle sphere and GS support agreement, ROI counts [48,48,48,44,48,48,57,57,44,44,57,57], and GS count 21,781. No BOLD values, cleaning or connectivity were computed by that gate.

## Preserved operators and numerical authority

Keep the twelve stated 9-mm overlapping spheres, both no-GSR/GSR arms and four signed metrics. Preserve reached Nilearn 0.12.1 sphere seed additions, float32 template normalization, cubic resampling, morphology, C-float64 signal arithmetic, nuisance QR and explicit `(Q @ Q.T) @ Y` projection. Keep final sample-standardization `SD < eps64 -> 1` on active columns. No filter, censoring, added arm, bootstrap, subject omission or available-edge averaging is introduced.

Original bytes determine supports, canonical GS/nuisance designs, cleaning ranks and activity. Raw ROI/GS arrays and diagnostics are receipts, never feedback inputs. Accepted source-close cleaned series alone determine signed edge Pearson, clipped Fisher edge-family means, child ranks/FD adjustment and adult arithmetic means. Rounded CSV/JSON cells never become downstream inputs.

Canonical residual activity uses exact-constant guarding and stable scale-first centering/norms: positive raw centered norm and residual centered norm strictly greater than `1e-12` times it. Canonical inactive clean columns are zero; tolerated inactive receipt jitter is ignored, never reactivated. Each family retains its fixed 15/15/36/36 edge set and becomes null if any required endpoint is inactive.

Source fidelity remains raw/GS `1e-5 + 1e-6*abs(reference)`; clean `1e-7 + 1e-7*abs(reference)` plus active centered relative L2 ≤ `1e-6`, with no absolute floor. Continuous derived receipts use `1e-6 + 1e-6*abs(expected)`; domains, masks, counts, statuses and null patterns remain exact. These tolerances were selected before original endpoints.

A separate canonical continuous-child conditioning guard prevents source-constant metrics from acquiring association support through receipt jitter. Active accepted continuous child values require centered relative fidelity ≤ `1e-6`. No canonical outcome-rank, r, p or rank-residual-support target is imposed: accepted near ties determine their own ranks and may legitimately change their own null status.

FD adjustment uses the declared shared `gesvd` projector for [1,rank(source mean FD)], strict `max(n,2)*eps64*smax` support and actual rank q. Center ranks before projection; require projected centered norm strictly above `1e-12` of its input centered norm. Constant FD gives q=1. This is a disclosed numerical recipe, not a universal rank-equivalence claim.

Contributing scaled voxels in the union of ROI and GS supports must be finite before reduction; unused voxels need not be finite. No wrapper-driven signal imputation is allowed. The grid-inclusive support digest, software reference and artifact byte limits are unchanged.

## Complete/null outputs and scoring boundary

Exactly five required named artifacts carry keyed evidence: `signal_evidence.npz`, `network_connectivity.csv`, `age_effects.json`, `run_metadata.json`, and `findings.md`. They retain every participant, frame, ROI, arm and metric. Coherent axis/key permutations and harmless bounded extras are permitted.

Each child metric keeps all 122 slots. Missing participant support makes both child endpoints null with the defined count. Otherwise ordinary and partial statuses may differ; df is 120 ordinarily and 122−q−1 after FD adjustment. Supported perfect correlation retains signed r with p=0; no infinite receipt or hidden epsilon denominator. Each adult metric requires all 33 values for its equal-person arithmetic mean, including legitimate constant/zero means; otherwise it is null with a count.

The public and private reporting kernels are byte-identical disclosed semantics. The grader authenticates its private copy, independently reconstructs original primitives, and never imports editable public helpers as authority. Generic header/table primitives and numerical libraries are shared and explicitly disclosed. No acceptance cache, historical answer bank, sign/effect/p-value band or prose/difficulty classifier is used.

Production performs one source-bound validation of submitted artifacts and checks authoritative failure markers before and after. Equivalent/mutation authoring QA remains outside scoring; an arbitrary valid submission need not have extra numerical or byte-cap headroom for QA perturbations.

## Evidence and claim boundary

Manufactured tests qualify code branches; opaque authentication establishes byte identity; structural inspection establishes the reported headers/tables; template-only comparison establishes geometry agreement for the frozen support recipe. None establishes scientific signal validity. BOLD numerical agreement, full execution and delivery remain separate reviewed gates.

The estimand is descriptive sensitivity of shared-movie, cross-sectional connectivity/age associations. A changed GSR statistic or a passed verifier does not establish neural specificity, artifact removal, causal development, population replication, the original paper's complete preprocessing or measured model difficulty.
