# Source-code OPM geometry reconstruction

This component reconstructs the four original-code actual/virtual OPM distance panels and their paired slope diagnostic from complete, operator-supplied per-sensor distances. It also implements the native channel-coordinate transform and nearest-scalp-vertex arithmetic. It does not perform MRI segmentation or rigid registration, certify supplied geometry, admit candidate helmet designs, or establish a paper reproduction or improvement score.

Paper reproduction and paper improvement are separate outcomes. This new source-code reconstruction component supports the former; both scientific scores remain unset. The preserved beta-amplitude evaluator remains a distinct downstream neural-analysis component. Neither a stronger age correlation nor a smaller permutation fraction is an improvement reward.

## Source recovered

The complete [author geometry script](https://github.com/LukasRier/RierRhodes_2024_Neurodevelopmental_OPMMEG/blob/0eb3a56af3d0e3a44b0f65c364e999f69cd4563f/RESULTS_head_size_confound.m) is 30,031 bytes, Git blob `e76f02ad69870449377e040c091b2a9d2c822cf4`, SHA-256 `8d6638e36e11dcd6102c577f80e88374bb1c74a0f0aec24965b38ace750628b0`. The repository revision is `0eb3a56af3d0e3a44b0f65c364e999f69cd4563f`. A complete, non-truncated 195-entry Git tree was retrieved and the script was recovered from the normal public source page. The page response was capped, but its entire `rawLines` array reconstructed the exact Git blob, including original line endings. No third-party source is vendored here.

| Source lines | Recovered rule | Component |
|---|---|---|
| 30–64, 125–158 | Children 001–027 and adults 101–126 excluding 120/123, in that order, both geometry arms | Exact 51-row panel; both excluded IDs retained separately |
| 69–73 | Largest included adult head, only when larger than every child; first maximum wins | Explicit reference validation; reject undefined branch |
| 603–631, 709–737 | Keep X-channel centers, divide TSV positions by 100, reshape transform as MATLAB does, apply rotation block and translation | `source_sensor_centers` |
| 627–638, 771–782 | Mesh coordinates converted to metres; nearest scalp **vertex**; arithmetic mean, despite variables named `median` | `nearest_vertex_distances`; per-person means converted to mm |
| 675–782 | One reference participant's sensor locations for every virtual head, against each rigidly moved scalp mesh | Identical ordered reference sensor IDs required for every virtual row |
| 414–506 | Four pooled participant fits: actual/virtual proximity versus age/head circumference; intercept, slope, Pearson r/p | All four fits, never pooled sensor observations |
| 510–547 | 10,000 paired within-person label swaps; actual-minus-virtual slope; strict upper-tail fraction without plus-one correction | `paired_slope_control`, source sign/tail retained |

The recovered code independently establishes its 51-person geometry cohort. It does not resolve whether this exact code panel underlies the paper's wording “all participants.” The previous contract intentionally did not infer geometry exclusions from the neural analysis. That uncertainty must now be reconciled with this direct source evidence, rather than silently changing the canonical contract.

The [complete author tree](https://api.github.com/repos/LukasRier/RierRhodes_2024_Neurodevelopmental_OPMMEG/git/trees/0eb3a56af3d0e3a44b0f65c364e999f69cd4563f?recursive=1) includes generic helmet information/location tables and mesh files under `Helmet_info/`, along with `sub_info.mat` and `sub_info_adults.mat`. These templates are not a substitute for participant-specific registered scalp meshes and sensor transforms. The tree alone does not establish the contents of the two Zenodo participant archives.

## Boundary and use

Dependencies are the existing Python 3.11+, NumPy, and SciPy environment. No installation is performed. From repository root:

```sh
python3.11 benchmarks/paper/PAPER-paper-signal-add-005/implementations/geometry-reproduction-v1/geometry.py /absolute/manifest.json /absolute/report.json
```

During the parallel construction wave, route this command and all tests through the shared `test_pool.py` as directed by the coordinator. Authentic geometry processing requires the separate frozen native protocol; a generated-fixture test does not grant that authority.

The manifest requires `schema_version: 1`, the exact `task_id`, `source_revision`, and `source_code_sha256` above; nonempty `geometry_provenance`, `head_circumference_provenance`, and `age_provenance`; `excluded_participants: ["sub-120", "sub-123"]`; `reference_participant_id`; a nonnegative integer `permutation_seed`; and exactly the 51 included `participants`.

Each participant contains `participant_id`, `age_years`, `head_circumference_source_value`, and both `actual` and `virtual` objects. Each arm contains equal-length `sensor_ids` and `nearest_scalp_vertex_distances_m` lists. These are physical sensor identities, not three separate observations per triaxial sensor. Actual sensor counts may differ by participant. Every virtual sensor list must exactly equal the actual reference participant's list in the same order. No source participant or sensor is silently dropped. Input ordering is canonicalized to the author's children-then-adults order before randomization.

The distances supplied to the report must have been computed from authenticated registered geometry. `source_sensor_centers` accepts already parsed native channel TSV rows and the native transform; `nearest_vertex_distances` accepts their output plus the scalp vertices converted to metres. These functions do not assert that arbitrary arrays have the correct physical frame. Geometry provenance must bind the original files, mesh selection, units, transforms, and reference identity. The manifest SHA-256 binds its scalar inputs, but prose provenance is not independent authentication.

The report retains each person's mean and both sensor counts. Its head predictor is explicitly an unresolved native perimeter unit. The source `regionprops` path (lines 644–655) computes slice perimeters in image-pixel coordinates, then selects the maximum perimeter. It does not explicitly apply voxel spacing. Previously reviewed paper text describes the perimeter at the largest-area axial slice. This component accepts the source scalar as supplied and does not relabel it millimetres or quietly implement the paper's different slice-selection rule. Age metadata also needs reconciliation: the script computes `KidsDatasets.Age_yrs` but reads `KidsDatasets.Age` (49,60).

The companion slope test keeps the source's sign and strict `null > observed` upper-tail expression. Its NumPy PCG64 seed is a declared prospective replay policy: the original MATLAB script records no RNG seed or historical masks. The 97.5th percentile uses NumPy's midpoint/Hazen interpolation. Native numerical parity, including percentile interpolation and random draw identity, remains unqualified. This diagnostic is not an improvement score or a newly validated statistical test.

## Limits that remain consequential

- Participant scalp meshes, sensor availability, transforms, rigidly moved MRIs, original head scalars, reference identity, and authentic distance vectors have not been acquired or processed here.
- The virtual branch specifies FieldTrip segmentation and 5,000 vertices per brain/scalp/skull mesh (741–773), but neither historical segmentation outputs nor rigid-registration settings are recovered. Nearest-vertex distance depends on this discretization.
- The script cannot be treated as an executable reference without repair: `clearvars` precedes a use of undefined `project_dir` at line 5. Its intervening CTF example requires an external CTF dataset, interactive fiducials, and contains other undefined variables. The CTF helper uses brain vertices at lines 860–866 and is not the OPM scalp comparator. Its hard-coded `109` reference is not evidence that the earlier dynamically selected OPM reference is 109.
- The source also opens an interactive ANCOVA tool (549–554) and plots age versus head circumference (557–565). Those ancillary analyses are not implemented here; the delivered boundary is explicitly the four OPM proximity panels and paired slope diagnostic, not every analysis in the script.
- The [article](https://elifesciences.org/articles/94561) Appendix 2 interpretation is inherited from the prior primary-source audit. New raw-XML access failed and the publisher response was a challenge page, so a fresh full-text verification is not claimed.
- Reproducing source-code panels is a useful first-class route, but publication fidelity still needs these discrepancies resolved and authentic original inputs. A physically feasible same-task candidate domain and a justified improvement summary remain unresolved. No arbitrary sensor relocation, hardware redesign, new cohort, stronger association, or lower p-value is admitted as improvement.

Tests use small generated coordinates and a schematic complete cohort. They check X-axis selection, cm-to-m and MATLAB-order transforms, vertex-versus-triangle geometry, rigid translation invariance, arithmetic mean, all four panels, full cohort identity, reference sensor support, paired swapping and strict tail behavior, order invariance, and file binding. They establish software behavior only. No authentic data preparation, native author run, candidate trial, scientific reproduction result, improvement result, or current-SOTA claim is made.
