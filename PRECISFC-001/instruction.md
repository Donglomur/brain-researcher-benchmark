# Within-person connectome similarity under frame censoring

Estimate how frame selection changes cross-session connectome similarity in six
Midnight Scan Club participants. This is a descriptive computational method control,
not a reproduction of a named result in Gordon et al. (2017), *Precision Functional
Mapping of Individual Human Brains* (doi:10.1016/j.neuron.2017.07.011). Within-person
similarity alone does not establish individual identification.

## Inputs and public analysis contract

The complete offline bundle is `/app/data/precisfc`. Its `source_manifest.json`
authenticates 36 original released files: processed volumetric BOLD and temporal
masks for MSC01, MSC02, MSC05, MSC06, MSC08 and MSC09, each at func01–func03.
These are OpenNeuro ds000224 release 1.0.4 derivatives, not unprocessed acquisitions.
The bundle also contains the published Power264 integer coordinates, original
4dfp point transform, acquisition metadata and qualified coordinate/timing lineage.
Do not fetch another dataset, modify originals or silently repair an input mismatch.

Read `/app/method_contract.json`. It is the authoritative public definition of
geometry, frame selection, stable numerical rules, output schemas and acceptance
tolerances. Its SHA256 is
`497b436132ee5723c3f7209489d77477fe2412ade1190f9aa95d0baf7bf9cda6`;
the source-manifest SHA256 is
`4f7fc73e548cfdf744fabbc382cebdd1edff968fe6edd7c1ca846958a1fbb967`.
Equivalent implementations are welcome; no hidden estimator or desired outcome
is required. Authenticate all source files before analysis.

## Analysis

1. Map the published integer MNI coordinates into the released 711 physical
   coordinate system using the public stored transform. Extract equal-weight
   means from original in-FOV voxel centres within 5 mm, using the original sform.
   Do not guess an identity mapping, add an axis flip, resample, add a brain mask,
   or rescue an empty sphere with its nearest voxel. Record exact membership and
   source peak-absolute values, not just correlations.
2. Compute both `all_frames` and `censored` arms for every run. The second keeps
   exactly source-mask entries equal to one. Both arms use the released already
   processed data; neither is a raw-data or causal motion-removal baseline.
3. Follow the public stable constant/numerical-zero rules. Use one common ROI
   intersection across both arms of all 18 runs, and its common edge set for every
   comparison. Form Pearson connectivity and Fisher-z values with the stated
   clipping rule. No extra detrending, filtering or nuisance regression is needed.
4. For each person and arm, correlate the common-edge Fisher-z vectors for each
   of the three session pairs, then average all three correlations. Give equal
   weight to each person in the primary all-six mean. Session pairs overlap;
   people, not edges or pairs, are the independent units.
5. Separately report conditional duration-QC means on the same edge support.
   The original headers say 1.0 second, whereas acquisition metadata and documented
   frame-preserving processing support 2.2 seconds. Explicitly use the public
   **acquisition-frame indexing assumption**, preserving both reported values and
   leaving the headers untouched. Retained duration is `n_retained * 11/5`
   seconds. Include a person in conditional QC only if `11*n_retained >= 3000`
   in each of their three sessions. Do not exclude a person by ID or outcome.
6. Preserve undefined estimates and diagnostics. Fewer than two common edges,
   constant vectors, incomplete pairs or an empty QC population are not zeros.
   They can be valid outcomes of a successfully completed analysis.

The coordinate bridge is supported by documented tool code and observed headers;
the exact historical export binary/IFH and individual registration accuracy are
not established. The timing override is a disclosed assumption, not corrected
header truth. Duration QC describes retained frames, not continuous clean time
or independent information. Discuss these limits without asserting a required
direction, size, subject ranking, exclusion narrative or causal explanation.

## Deliverables and grading

Write these nine artifacts to `${OUTPUT_DIR}` (default `/app/output`), using the
complete public schema in `/app/method_contract.json`:

- `session_qc.csv`: all 18 run identities, frame counts, both timing values and QC.
- `roi_geometry.csv`: 264 coordinate mappings, voxel counts and boundary diagnostics.
- `roi_status.csv`: each run/arm/ROI's support, norms, status and common membership.
- `connectivity_arrays.npz`: keyed full-precision ROI means, source peaks, original
  frame/mask and voxel identities, and both arms' connectivity arrays.
- `session_pairs.csv`: all 36 keyed pair measurements with numerical diagnostics.
- `reliability.csv`: both arms and duration-QC status for every person.
- `reliability_stats.json`: primary and conditional means, counts and null reasons.
- `run_metadata.json`: exact method/source identity and truthful input/software observations.
- `findings.md`: a short nonempty interpretation; prose keywords are not graded.

CSV rows and explicit NPZ axes may be coherently reordered. Full-precision means
must satisfy the public pointwise **and centred-signal fidelity** conditions;
pointwise-close invented temporal variation is not acceptable. The verifier then
recomputes support, connectivity and summaries from your accepted means, rather
than enforcing hidden reference labels at numerical boundaries. Keep genuine
undefined values coherent throughout. Grading is binary: complete source-bound,
internally consistent outputs receive 1; there is no proportional-scoring promise.

Use fresh output destinations. A failed source or numerical precondition must
stop analysis with an explicit reason; it is not a passing complete submission.
Do not overwrite an existing result, private evidence, source file or symlink target.
