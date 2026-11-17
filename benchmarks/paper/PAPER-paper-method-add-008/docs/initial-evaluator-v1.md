# Initial real-recording curation evaluator

This component reconstructs the pinned author's curation table from complete native unit-label exports for the four named sorters, and streams the Kilosort4 spike-location export into a full Bombcell-`good` drift raster. It produces useful post-native analysis artifacts. It does not execute a sorter, apply either curation model, measure spike accuracy, supply a numerical drift-robustness score, or complete this benchmark's scientific contract.

The immutable contract is `task.json`, SHA256 `6350dbe7e3039ba9625ab4a5e28a31975b63cd8d2c09fbbb9c21ddd2eb0b10c6`. The primary code revision is [`d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1`](https://github.com/SpikeInterface/sorting_components_benchmark_paper/tree/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1); the paper is [eLife version 3](https://doi.org/10.7554/eLife.110588.3). `source-provenance.json` maps implemented behavior to individual primary files and contract fields. No historical result or source file has been changed.

## Precisely bounded population

The author batch source names the Duszkiewicz A3702 recording from DANDI000939. This implementation prospectively binds only the canonical inventory item `af795820-bc09-4494-9da8-d2aa9aad4724`, path `sub-A3702/sub-A3702_behavior+ecephys.nwb`, size 2,007,197,177 bytes, version `0.250207.0025`. The source script includes `ses-191126` in its filename, whereas the frozen inventory does not. They have **not** been established as byte-identical recordings. A source-path resolution receipt and empirical content SHA256 are mandatory owner declarations; validation of that receipt remains an admission hold. The 31 inventory assets are not silently selected as a study population. Other paper datasets and the synthetic suite are outside this component.

The assessment owner freezes the whole-recording frame count, sampling frequency, channel IDs, the four native artifact hashes, every native unit ID and spike count, curation model and implementation hashes, complete dependency-lock digest, effective sorter-parameter digests, and measured-resource declarations. Every sorter must appear, including a successful zero-unit result. The full recording and channel inventory are shared; this interface has no per-sorter crop or selection mask. A failure is not converted to an empty successful sorting.

The owner must create and retain the manifest and pass its expected digest independently of candidate exports. Canonical hashing is UTF-8 JSON with sorted keys, compact separators and nonfinite numbers forbidden. This is an identity boundary, not cryptographic attestation of a native run. A candidate-supplied manifest plus its own digest provides no protection. Protected references, execution isolation, exposure review and independently audited native receipts remain future owner responsibilities.

## Source-faithful analysis and prospective validation

`evaluate_curation` requires every native unit exactly once and reconstructs the author's columns: total units, Bombcell good/MUA/noise, UnitRefine SUA/MUA/noise, and number of SLAy proposed merge groups. Bombcell good includes `good` and `non_soma_good`; MUA includes `mua` and `non_soma_mua`. The SLAy column counts groups, not member units or implied unit reductions. It reports all-unit proportions (null for a zero denominator), full label distributions, a curation-label cross-tab and six paired count-difference records. These supplementary summaries are descriptive conventions; curation labels are not reference truth, and agreement between two curators is not cross-sorter spike agreement. There is no ranking, winner or binary reward.

`export_good_unit_raster` uses only Kilosort4 units whose Bombcell label is exactly `good`, matching the author's drift-plot selection. `non_soma_good` contributes to the quality table but is excluded from this raster. Input CSV covers all Kilosort4 units' complete spike inventory, including units excluded from the raster. The exporter checks finite coordinates/amplitudes, ordered in-range integer samples, per-unit counts and duplicate unit/frame events, and writes seconds plus depth and amplitude for each retained spike. It does not decimate or infer numeric drift robustness from the visualization. The source display uses scatter decimation; retaining every qualifying spike allows later rendering without losing data during evaluation.

Strict JSON keys, string unit IDs, nonoverlapping merge groups of at least two distinct units, finite positive resource declarations, complete spike counts and atomic CLI outputs are prospective engineering policies. They make omissions and malformed exports fail closed; they are not claimed as author scientific estimands. Model outputs must already exist in the exports. No threshold tuning, model downloads or native execution occurs here.

## Source defects preserved as holds

The pinned batch script concatenates SpyKING CIRCUS2 and Tridesclous strings because commas are missing, points its analyzer directory at `raw_data`, and derives one dataset's output names from another dataset's protocols. Protocol dictionaries use `tridesclous2A` while curation paths use `tridesclous2`. The manifest keeps the source protocol key separate from the logical sorter name, without claiming a native repaired runner.

Kilosort's analyzer preprocessing is common reference followed by bandpass, while the other sorters reverse those operations. This component preserves the declared source order and explicitly leaves common-preprocessing comparability unresolved. Tridesclous's no-motion dictionary omits an explicit motion-correction setting; its dependency default is not frozen by this package. The source metadata pins Kilosort 4.1.2 but provides a lower bound for SpikeInterface, and curation-model hashes are not supplied by the source. Native export manifests must declare Kilosort 4.1.2. The owner records effective dependency and model pins; their official-reference qualification is still open.

Real unit yield and curation quality are proxy outcomes susceptible to optimization and curation-model exposure. All reports unconditionally retain `scientific_qualified=false`, `full_contract_complete=false`, `native_reference_verified=false`, and `spike_accuracy_estimated=false`, even for inputs labeled native. Exact native execution, full protocol/configuration audit, model/data/code rights and public exposure, common-preprocessing reconciliation, numeric drift and spike-agreement endpoints, independent reference/control execution, resource audit, difficulty and submission qualification remain open. No scientific run, data acquisition or empirical comparison was performed.

## Run and inspect

Python 3 standard library is sufficient. From this implementation directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 example_control.py /tmp/modular-sorting-input
python3 evaluator.py \
  --owner-manifest /tmp/modular-sorting-input/owner-manifest.json \
  --expected-manifest-sha256 "$(cat /tmp/modular-sorting-input/manifest.sha256)" \
  --curation-json /tmp/modular-sorting-input/curation.json \
  --drift-spikes-csv /tmp/modular-sorting-input/all-kilosort-spikes.csv \
  --output-directory /tmp/modular-sorting-output
```

Both directories must be new. The example is explicitly generated engineering data with placeholder native hashes/resources. Its purpose is to show the exact input schema and exercise the analysis path, not establish empirical identity or native resource costs. Do not use its manifest as an authentic assessment manifest. The CLI produces `report.json`, `source_curation_table.csv` and `good_unit_raster.csv`. The report pins the canonical curation input, exact consumed raster bytes, and both output CSVs by SHA256. These hashes trace the calculation; they do not attest native origin. Output appears only after all validation succeeds; existing output directories are rejected. Direct Python streaming callers must discard partial output on an exception and record their own input/output artifact hashes.

Independent controls check non-somatic category aggregation, merge-group counts, all-unit denominators, zero yields, all four comparators, exact raster selection, complete spike populations, native artifact binding and atomic rejection of malformed inputs. They establish engineering behavior only. The independently derived five-label control gives Bombcell counts 2/2/1, UnitRefine counts 2/2/1, two proposed SLAy groups containing five units, and one retained `good` raster spike.
