# Initial CALC–CTRL map-array evaluator

This is a complete owner-side calculation component for the registered central BOLD/CMRO2 comparison: it validates a frozen 40-person map packet, computes the within-person contrast, and reports the distinct source reductions for the positive and negative BOLD PLS masks. It is not a native notebook runner, a PLS implementation, an authenticated empirical reference, or a scientifically qualified benchmark. No authentic participant map was acquired or evaluated during construction. The immutable task contract remains authoritative, including all holds.

## Fixed scientific semantics

The contract SHA-256 is `dc4aa310b2265d05b3cfa88b7f8093ebc82cbac96ca6d67628c9c83b899dcd64`. Primary source is [BOLD signal changes can oppose oxygen metabolism across the human cortex](https://www.nature.com/articles/s41593-025-02132-9), with [author code at revision 1b22c2c](https://github.com/NeuroenergeticsLab/two_modes_of_hemodynamics/tree/1b22c2cb03bab0d5cf70da6a45c4d720194dc523), specifically the Fig. 2B section of `D_Fig2BD.ipynb`. Data identity is OpenNeuro `ds004873`, snapshot `2.0.6`, Git revision `eef50ff140a9863c412428b0bd1a14f46f5cd342`.

The only implemented contrast is CALC minus CTRL, using all 40 source-selected participants in their fixed source order:

`019, 020, 021, 023, 026, 027, 028, 029, 030, 031, 032, 033, 034, 035, 036, 037, 038, 039, 040, 043, 044, 046, 047, 048, 049, 050, 051, 052, 054, 055, 058, 059, 060, 061, 063, 064, 065, 066, 067, 068`.

IDs are serialized as `sub-p019`, etc. The first 30 have all conditions; the last 10 have CALC/CTRL and measured CALC CBV. Participant `053` is excluded by the source list. The 75 metadata rows, separate control study, replication subjects, and other contrasts are not interchangeable samples. Missing, duplicated, substituted, or reordered participants fail validation; there is no subset score.

For each participant and frozen voxel, CMRO2 percentage change is `100*(CALC-CTRL)/CTRL`. The primary CALC input is `desc-CBV_cmro2`; CTRL is `desc-orig_cmro2`. BOLD is already the released `task-calccontrol_space-MNI152_desc-fmriprep_BOLD_percchange` map and is never normalized a second time. These percentages are calculated within person before any group reduction. The CBV correction uses measured information from 10 participants and a regional surrogate for the other 30; this evaluator consumes corrected maps and does not reconstruct or qualify that physiological correction.

For each signed source mask, outputs retain both reductions because medians do not commute:

- `source_spatial_median_of_voxelwise_subject_medians`: take the median across all 40 participants at each voxel, then the median across voxels. This matches `percchange_median_pos/neg` and `pos_median/neg_median` in the Fig. 2B source.
- `participant_spatial_medians`: take each person's spatial median, matching the separately stored `df_percchange_subj`. Its group median is reported separately as `median_of_participant_spatial_medians`.

An explicit sensitivity uses the source's original-map convention: **first 30 CALC `desc-orig`, last 10 CALC `desc-CBV`**, always against CTRL `desc-orig`. The preprocessing notebook does not establish CALC `desc-orig` availability for all 40. Last-10 sensitivity values and receipt hashes must equal the primary measured-CBV values. This is a prospective comparison; it is not an all-40 uncorrected analysis. The `CMRO2_mode` selector in the pinned D notebook does not affect its Fig. 2B loader, so this component does not imply that toggling it reconstructs a second published figure.

## Packet and trust boundary

The package contains `evaluator.py`, `provenance.json`, and `tests/test_evaluator.py`. It needs Python 3 and existing NumPy; no installation, network access, NIfTI loader, or model is used by the evaluator. An owner supplies `manifest.json` and `maps.npz`. The required CLI digest must come from owner state frozen before evaluation, outside candidate control. `load_packet` verifies that manifest digest and the declared NPZ digest. `evaluate_packet` is an in-memory calculation API; by itself it validates semantics but does not authenticate file bytes. Use `load_packet` first on any external packet.

The manifest has these exact fixed fields (the test fixture illustrates syntax but contains conspicuously fictitious engineering receipts and must never be used as empirical evidence):

| Field | Value |
|---|---|
| `schema_version`, `task_id`, `contract_sha256` | `1`, this task ID, immutable contract hash above |
| `dataset`, `dataset_version`, `dataset_git_revision` | `ds004873`, `2.0.6`, pinned dataset revision above |
| `official_code_revision`, `contrast` | pinned author revision above, `calc-control` |
| `primary_lineage` | `calc_desc-CBV_vs_control_desc-orig` |
| `original_sensitivity_lineage` | `calc_desc-orig_first30_desc-CBV_last10_vs_control_desc-orig` |
| `mask_policy` | `frozen_source_PLS_BOLD_reproduction_only` |
| `spatial_null_policy` | `withheld_pending_geometry_preserving_null_qualification` |
| `bold_units`, `cmro2_units` | `already_percent_change`, `umol/100g/min` |
| `subject_ids` | exact ordered list of 40 full IDs |
| `data_file`, `data_sha256` | `maps.npz`, SHA-256 of its bytes |
| `source_receipt_status` | `operator_attested_not_independently_authenticated` |
| `preassessment_freeze_receipt_sha256` | owner-frozen assessment/mask/voxel selection receipt |
| `physiology_and_cbv_lineage_receipt_sha256` | owner calibration, Hct/O2sat, CBV and processing lineage receipt |

`grid` contains `space: MNI152`, `shape: [91,109,91]`, `voxel_size_mm: [2,2,2]`, `index_order: C_flat_sorted`, `affine_sha256`, and `voxel_indices_sha256`. The voxel-index digest hashes the sorted index vector encoded as little-endian signed int64. The affine digest identifies the common owner-verified affine; this array component does not read NIfTI headers. Source-to-array extraction, exact mask support, orientation and registration are still externally verified obligations. These fields bind a receipt; they do not prove its truth.

`map_receipts` has all 160 `(subject_id,map_key)` records, each with the exact source-relative `path` produced by `source_map_path`, an explicit SHA-256, positive `bytes`, and the common `affine_sha256`. Last-10 primary/sensitivity records refer to the same measured-CBV map. `mask_receipts` has exactly `whole_brain`, `positive`, and `negative`, with `path`, SHA-256 and affine hash. Fixed paths are:

- `derivatives/task-all_space-MNI152_res-2_SNR_YEO_group_mask.nii.gz`
- `results/N40_BSR_meanPLS_func_clusterBSR_res-2_calccontrol_GMmask_pos_bin.nii.gz`
- `results/N40_BSR_meanPLS_func_clusterBSR_res-2_calccontrol_GMmask_neg_bin.nii.gz`

The NPZ has exactly seven arrays, loaded with `allow_pickle=False`:

| Array | Shape and meaning |
|---|---|
| `voxel_indices` | integer `[V]`, all frozen whole-brain mask voxels in sorted C-order flattened MNI grid |
| `positive_mask`, `negative_mask` | boolean `[V]`, nonempty disjoint source signed masks on those voxels |
| `bold_percent_change` | finite numeric `[40,V]`, source BOLD percent maps |
| `cmro2_control_orig` | positive finite numeric `[40,V]`, CTRL original maps |
| `cmro2_calc_cbv` | positive finite numeric `[40,V]`, primary CALC corrected maps |
| `cmro2_calc_source_original` | positive finite numeric `[40,V]`, first-30 original plus last-10 corrected |

The input is the complete frozen whole-brain mask support, not a union chosen after examining task effects. Source mask support and its hash must be checked by the owner against the actual image, because the NPZ cannot establish that correspondence. Invalid/nonfinite voxels fail the packet; the evaluator does not silently remove participants or voxels, shrink the mask, insert epsilon denominators or select a favorable map. A failure reopens the extraction/validity policy hold. The source masks are selected using the source BOLD contrast and are appropriate only for the explicitly exposed reproduction description. They do not become independent confirmatory masks by being packaged here.

## Prospective descriptive additions and uncertainty

The evaluator also reports Pearson correlation between the two group-median spatial fields within each mask and the fraction of paired nonzero group-median voxels whose signs oppose. Exact-zero pairs are counted explicitly and excluded from the sign-fraction denominator. Constant-map Pearson and an empty nonzero denominator return JSON `null`. These are descriptive extensions, not the source PLS endpoint, firing-rate measurements, or spatial inference.

A fixed-seed paired participant percentile bootstrap resamples whole participant rows identically across modalities and voxels, recomputing the source group statistic each time. Defaults are 2,000 replicates and seed 0; the CLI exposes these engineering settings. Bounds 1–10,000 prevent accidental unbounded computation and do not establish adequate scientific replication. This bootstrap describes participant resampling conditional on fixed exposed masks; it neither accounts for re-estimating masks nor replaces the source 3,000 PLS permutations/bootstraps. Spatial autocorrelation is preserved within rows, but no spatial null distribution is established. Spatial p-values remain null. IID voxel permutations, effect-chosen masks, favorable map selection and significance claims are not supported. A later spatial test requires a separately frozen geometry-preserving null and an independent audit before inference.

Run from this implementation directory:

```sh
python3 evaluator.py /owner/manifest.json --expected-manifest-sha256 OWNER_FROZEN_DIGEST --output /owner/contrast.json
python3 -m unittest discover -s tests -v
```

The JSON result always retains `reward: null`, `research_qualified: false`, `full_contract_complete: false`, and detailed holds. No pass threshold, target tolerance or binary reward is invented. Output files are local owner artifacts and should remain outside source control.

## Source dependencies and unresolved work

The C notebook performs mean-centered PLS and emits the positive/negative BSR masks consumed by D. The whole-brain SNR/Yeo group mask is an input to both A/C; its complete generation was not established by inspecting the named notebooks. The paper describes GM probability threshold 0.5, cerebellar and low-SNR exclusions, while native qBOLD masks have additional physiological exclusions. Fig. 2D has different BSR/cluster thresholds and manually joined regions; those ROI results are outside this fixed Fig. 2B component.

Independent source inspection found mismatched BOLD normalization routes: A's released percent maps use voxelwise baseline temporal medians, while C's raw-intensity PLS cell uses a scalar median with no axis. C also has notebook-state hazards (`sub-r` spelling and a cell without a fresh `sub` assignment). This implementation consumes A/D's percent-map route and does not silently repair or qualify native C execution. B Fig. 1 has a 40-slot allocation filled by 30 subjects in some paths; its padded-median behavior is not imported here.

Authentic map and mask acquisition/validation, physiological calibration/robustness, native execution, PLS reconstruction, numerical figure agreement, independent replication, geometry-preserving spatial nulls, protected assessment and information boundaries, meaningful difficulty, measured end-to-end resources, and target submission qualification remain open. Raw mqBOLD reconstruction and new independent cohorts remain outside initial scope. Public paper/data/results and saved notebook outputs remain exposed. Data are recorded as CC0; upstream code is CC BY-NC-SA 4.0. This independently written component does not redistribute source notebooks or remove their noncommercial/share-alike obligations when they are used.
