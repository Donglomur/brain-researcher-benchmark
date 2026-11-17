# Initial ISD evaluator: source kernel and prospective paired-state boundary

This additive package implements the paper's central integration/segregation computation, participant-level state contrasts, simpler connectivity/global-amplitude/motion comparisons, and phase-randomized controls. It is a construction deliverable. No empirical reproduction, scientifically qualified benchmark, registered grader, or numeric target is established. The canonical task remains unchanged.

## Scientific contract and sources

The canonical task is `PAPER-paper-signal-add-012`, SHA256 `66d8975ed4f868e9289d6824b0152105a6f8deaeca9d2efd97b2a8cbb4474aae` (20,725 bytes). Its endpoint is integration, segregation and ISD state contrasts from real participant time series. Its documented initial scope covers the labeled sedation/sleep conditions in Datasets 3–5, with matched GSR/noGSR and complete participants. This package does **not** finish that population-wide contract.

Primary article: [Jang et al., Nature Communications (2024), DOI 10.1038/s41467-024-53299-x](https://www.nature.com/articles/s41467-024-53299-x). Source semantics were inspected in [ISD_calculation.m](https://raw.githubusercontent.com/janghw4/multilevel-integration-segregation-balance/fba91ec089cb5d582c183bbdc6599c706a38f437/ISD_calculation.m) and [main.m](https://raw.githubusercontent.com/janghw4/multilevel-integration-segregation-balance/fba91ec089cb5d582c183bbdc6599c706a38f437/main.m), revision `fba91ec089cb5d582c183bbdc6599c706a38f437`. The demo's random arrays are not reference data.

The author does not identify a BCT revision. This implementation adopts a **prospective dependency reference**, `brainlife/BCT@b7f59ebcf0b4f4979ab3914e30c61eaf345b11d5`, under `BCT/2019_03_03_BCT/`: [charpath.m](https://raw.githubusercontent.com/brainlife/BCT/b7f59ebcf0b4f4979ab3914e30c61eaf345b11d5/BCT/2019_03_03_BCT/charpath.m), [distance_bin.m](https://raw.githubusercontent.com/brainlife/BCT/b7f59ebcf0b4f4979ab3914e30c61eaf345b11d5/BCT/2019_03_03_BCT/distance_bin.m), and [clustering_coef_bu.m](https://raw.githubusercontent.com/brainlife/BCT/b7f59ebcf0b4f4979ab3914e30c61eaf345b11d5/BCT/2019_03_03_BCT/clustering_coef_bu.m). These immutable URLs were inspected, but remote payload byte hashes were not measured. No MATLAB/BCT code is vendored or executed.

| Requirement | Implementation and evidence | Remaining limit |
| --- | --- | --- |
| Exact original metric | `isd_from_fc`: strict FC > k/100, k=1..100; average noGSR efficiency, average GSR nodal clustering, difference | Original BCT version and native MATLAB parity remain unknown |
| Regional BOLD to FC | `correlation_matrix` applies columnwise Pearson correlation to time × ROI arrays; rejects undefined ROI correlations | MAT variable names, condition axes, preprocessing and authentic values not validated |
| Matched preprocessing | NPZ loader checks exact dimensions and separate ROI/sample identity arrays for GSR/noGSR | Declared IDs need authentic source audit |
| Participant pairing | Manifest requires every roster member in both selected states; no intersections, truncation, exclusion, or cross-cohort pooling | Roster authenticity and all-state coverage remain open |
| State uncertainty | Equal-participant after-minus-before differences with paired Student-t 95% intervals | Prospective recipe; no historical primary contrast or normality qualification claimed |
| Simpler comparators | Reports noGSR mean/absolute FC, GSR mean FC, global-signal/ROI amplitude, and supplied mean framewise displacement; same participant contrasts | Motion preprocessing, thresholds and incremental predictive information not established |
| Autocorrelation null | Independently randomize phases by ROI, share phases across GSR/noGSR, retain DC/Nyquist; compare ISD to null mean | Preserves discrete **circular** autocorrelation and spectrum, not general nonstationarity; not a published null-count prescription |

## The self-loop convention is consequential

The author main script passes Pearson matrices directly into ISD. Their unit diagonals survive each threshold below 1. BCT's clustering neighborhood includes the node itself when that diagonal is present, and sums the neighbor-induced adjacency including its diagonal. Therefore segregation can exceed 1. This package preserves that behavior and never clamps segregation or ISD. Shortest-path efficiency excludes diagonal pairs and includes unreachable pairs as zero inverse distance in the denominator.

For three fully connected ROIs (both FC matrices all ones), integration is 0.99, segregation 1.485, and ISD −0.495. With off-diagonal correlations exactly 0.5, there are 49 active thresholds; the corresponding values are 0.49, 0.735, −0.245. These are hand-derived engineering controls, not reported participant results. A loop-free implementation would silently change this source recipe. Whether the paper's empirical processing actually used this diagonal convention must be resolved before scientific qualification.

## Runnable local interface

Only existing NumPy and SciPy are required; no installation or model service is invoked. From repository root, with a Python environment containing those packages:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s benchmarks/paper/PAPER-paper-signal-add-012/implementations/initial-evaluator-v1/tests -v
python benchmarks/paper/PAPER-paper-signal-add-012/implementations/initial-evaluator-v1/evaluator.py /absolute/path/manifest.json --output /absolute/path/report.json
```

`evaluator.py` also exposes `isd_from_fc`, `paired_timeseries`, `phase_randomized_pair`, and `paired_effect`. The library can analyze generated small matrices for engineering tests; this is separate from admitting authentic cohort inputs. The CLI's report always contains `scientifically_qualified: false` and the scientific holds.

The JSON manifest has the following fields (all required except `engineering_control`, which defaults to false):

```json
{
  "schema_version": 1,
  "task_id": "PAPER-paper-signal-add-012",
  "cohort": "Dataset-3",
  "engineering_control": false,
  "participant_ids": ["all source-verified cohort IDs, in declared order"],
  "roster_source": "source/version and complete cohort roster evidence",
  "contrast": {"before": "baseline", "after": "deep"},
  "tr_seconds": 2.0,
  "n_timepoints": 448,
  "n_rois": 450,
  "length_policy": "require_equal_no_truncation",
  "motion_policy": "report_all_no_exclusion",
  "normalization_provenance": "audited MAT variable, participant, condition, sample and ROI mappings",
  "surrogate_count": 100,
  "surrogate_seed": 2024,
  "recordings": [{
    "participant_id": "source-verified ID",
    "condition": "baseline",
    "path": "relative/paired_recording.npz",
    "sha256": "SHA256 of the NPZ bytes",
    "tr_seconds": 2.0,
    "mean_framewise_displacement_mm": 0.1
  }]
}
```

This is a field illustration, **not** a usable data manifest or verified TR/motion/null-count prescription. Supply all 14 Dataset-3 IDs and both selected state records for each. Exact TR, motion derivation, and primary contrast need a frozen prospective protocol and authentic audit. D3 conditions admitted are baseline/light/deep/recovery. One declared contrast is evaluated per invocation, and results are never presented as coverage of all D3 states or all Datasets 3–5.

Each NPZ requires `no_gsr`, `gsr` (time × ROI), `no_gsr_sample_ids`, `gsr_sample_ids`, `no_gsr_roi_ids`, and `gsr_roi_ids`. IDs are unique 1D string/integer arrays, with exact matching order across preprocessing variants and common ROI order across the cohort. Object arrays/pickle are not accepted. Paths must stay within the manifest directory. The file digest, finite values, nonconstant ROIs, dimensions and identifiers are checked before metric evaluation. Mean framewise displacement is supplied from independently audited preprocessing; the evaluator cannot infer motion from regional BOLD.

For Dataset 5, all 33 participants are required, with conditions N1/N2/N3/awake, but only equal observation lengths are currently accepted. The source describes variable stage lengths: this boundary therefore cannot generally admit the released Dataset-5 population until an independently reviewed length policy is implemented. It never truncates to a convenient common length. Dataset 4 is rejected: its 17 × 3 and 6 × 2 subcohorts, two-condition labels and participant overlap need resolution. The library kernel remains available for subsequent adapters, but that does not remove these holds.

An explicit `engineering_control: true` permits small generated dimensions/rosters and labels the output `engineering_control_only`; it never establishes cohort coverage or qualification. Production-shaped input yields `unqualified_source_metrics`. Neither mode emits a benchmark reward.

## Validation and scope of evidence

The standard-library unittest suite uses independent rational graph expectations, a separate breadth-first path oracle, odd/even FFT spectrum preservation, paired interval arithmetic, CLI round-trip, record-order invariance, missing/duplicate participant checks, source population rejection, digest mismatch, TR mismatch, unsupported policies, and sample/ROI/constant-array failures. Generated arrays stay small (at most 16 × 4 for spectral checks); there are no authentic participant runs, archive transfers, installations, model calls or native scientific campaigns.

The first test attempts found no installed pytest in the available interpreters. Tests were made self-contained with standard-library unittest; no dependency was installed. These checks establish engineering behavior only. Reference and scientific holds include full MAT binding/populations, original dependency and diagonal reconciliation, authentic runtime and numeric tolerance, rights/access parity, protected references, baseline/candidate replay, complete D3–5 conditions, variable-length policy, Dataset-4 overlap, prediction with whole-participant/cohort holdouts, and transition timing. No predictive model or transition/ETC branch is implemented.

## Reuse and attribution

The evaluator and tests are newly written Python source with `SPDX-License-Identifier: GPL-3.0-only`, conservatively preserving the author's recorded GPL-3.0 code terms for this source-guided implementation. They are not a vendored MATLAB translation. BCT routines were consulted for scientific conventions; the referenced mirror's root license is MIT and attributes brainlife.io, while routine headers credit Olaf Sporns, Mika Rubinov and Jonathan Clayden. No BCT source text is redistributed. Data metadata records CC BY 4.0 for Figshare article 26367193 / file 47912122, but no data are shipped, acquired or relicensed. The paper's reuse/figure terms and component rights remain a separate qualification requirement. See `provenance.json` for the precise identities and limits.
