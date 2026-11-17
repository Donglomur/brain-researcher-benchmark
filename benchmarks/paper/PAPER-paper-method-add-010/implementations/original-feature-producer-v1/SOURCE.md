# Selected original source route

Author repository revision: `cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0`.
The calculations below are reimplemented from the original method, with
explicit input validation and provenance. The complete author driver/YAML is
not vendored or imported as an executable side effect.

| Source | Locators and supported behavior | Cached source SHA256 |
|---|---|---|
| [Extraction driver](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/functional_connectivity_analysis/run_barycenter_pyspi_for_subject_averaged_epochs.py) | Lines37–53 fresh calculator copies, ROI pivot/load/compute;121–154 seconds→milliseconds, exact ON mask, category/condition iteration, Calculator defaults; Raw and Abs branches remain distinct | `4a6a0b8ba1fefa22750db296dca15fabf464f61deeb6c721fc2dc7b1f83b2bdd` |
| [Selected config](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/functional_connectivity_analysis/barycenter_sq.yaml) | Lines30–32: dtw, max, squared=True | `9e632969fcbf0711c4479fe9b7625b5ce5e9bd8fbd659930ac34d8838afd214a` |
| [Original classifier](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/classification/fit_pyspi_classifiers.py) | L1 logistic; SGKF10/seed127; unsorted file glob; per-direction four-category QC before pair selection; fold accuracy/AUC means and population SD | `5d84990e591d665777e90ae70a5ad1d75ba8058be559898a7b50c7a3f0855137` |
| [Mixed sigmoid](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/classification/mixed_sigmoid_normalisation.py) | Training location/scale; left-associative division by IQR then1.35; each transform batch's extrema | `7714edb2149e597728f7d7eb23294c9758473ed1af7f45c72b6236417659127e` |
| [Epoch averaging](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/MEG_preprocessing/combine_time_series_from_MEG.py) | Lines46–57 average epochs by stimulus/relevance/duration/time/ROI before column pivot | `bb25a92893f294e84294141dbdb30a89c6eb813a3409de5ee1ba53605987fe76` |
| [Regional extraction](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/MEG_preprocessing/extract_time_series_from_MEG.py) | Entry point335 passes downsample=False: the declared100Hz setting is inactive. Baseline -0.5..0s; dSPM inverse, SNR3; source ROI averaging and atlas mapping are upstream provenance, not rerun here | `017c29b3fdba1411b739487b7c348fb5846f767ba9708be0ef00e9008965469c` |
| [Requirements](https://github.com/anniegbryant/MEG_functional_connectivity/blob/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/requirements.txt) | Declared native package versions; not historical execution proof | `5fadd8dd86442a6910cf525c9d54ec8520b17b79628c34c0bd309bab5006c883` |

## Library semantics

[PySPI1.1.1 Data](https://raw.githubusercontent.com/DynamicsAndNeuralSystems/pyspi/v1.1.1/pyspi/data.py)
lines165–177 applies `scipy.stats.zscore(axis=1,nan_policy='omit',ddof=1)` then
`scipy.signal.detrend(axis=1)`, without another standardization.
[Calculator](https://raw.githubusercontent.com/DynamicsAndNeuralSystems/pyspi/v1.1.1/pyspi/calculator.py)
defaults `normalise=True` and constructs a new Data object for the author's
NumPy matrices. Data-load failure occurs outside the per-SPI exception boundary;
an exception inside the entire SPI multivariate computation yields an all-NaN
SPI table.

[Barycenter](https://raw.githubusercontent.com/DynamicsAndNeuralSystems/pyspi/v1.1.1/pyspi/statistics/distance.py)
lines199–243 calls native `dtw_barycenter_averaging(z[[i,j]])`, caches its result
for both pair directions, squares the resulting barycenter and takes `nanmax`.
It inherits Directed despite its undirected label. The
[dispatcher](https://raw.githubusercontent.com/DynamicsAndNeuralSystems/pyspi/v1.1.1/pyspi/base.py)
loops target j outside source i. The six first cache fills are `(1,0),(2,0),
(3,0),(2,1),(3,1),(3,2)` for rows CS,IPS,PFC,V1_V2. Computing all six preserves
failure propagation from unrelated ROI pairs. A NaN statistic without an
exception in another pair does not itself erase a finite selected value.

[tslearn0.6.3 DBA](https://raw.githubusercontent.com/tslearn-team/tslearn/v0.6.3/tslearn/barycenters/dba.py)
uses `dtw_barycenter_averaging_one_init`, the majorize/minimize implementation,
not its Petitjean/subgradient alternatives. Defaults: `barycenter_size=None`,
`init_barycenter=None`, `max_iter=30`, `tol=1e-5`, `weights=None`,
`metric_params=None`, `verbose=False`, `n_init=1`. Thus these equal-length inputs
use1000 samples, arithmetic-mean initialization, uniform weights and unrestricted
DTW. No approximation or shorter sequence is substituted.

The tagged source bodies were inspected through the primary-source web reader.
Selected PySPI1.1.0 Data/Barycenter semantics visually match1.1.1; the paper's
1.1.0 versus requirements1.1.1 discrepancy still does not establish historical
native parity. Official release pages link to PySPI1.1.1 commit
`b2f948d71e2b1bcc12901d86350a36ff7d8e6630`, PySPI1.1.0 commit
`5c878832d55d66509e01663acb46ea2b93d40762`, and tslearn0.6.3 commit
`99379466ec934fcf39dd4f30ec13c033f33f4a34`. These are inspected link targets,
not newly authenticated local package-body hashes. A source-only HTTPS download
attempt failed TLS before HTTP with zero body bytes. No dependency was installed,
and neither PySPI nor native tslearn DBA was executed. The broader author YAML includes `max_time`, which
ordinary upstream PySPI rejects; direct selected-max construction avoids that
unrelated routing defect without claiming the full author environment works.

## Released input identity

[Zenodo18294156 empirical.zip](https://zenodo.org/api/records/18294156/files/empirical.zip/content):
220609250 bytes; MD5 `c7d3a97c229d97ec174582653cd4a8ba`;
SHA256 `79308086f1c6eed01d1bee27d75220778a90283f4ef14aa535afb971d2764904`.
Existing intake/coordinate-census evidence supplies350 ZIP entries,94 selected
CSV members totaling345354727 expanded bytes, exact1ms timestamps and the two
absent target groups. This construction did not reprocess authentic CSV bodies.
The complete published participant roster is reused from the existing original
scorer and checked there against SHA256
`6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a`.

These source identities do not settle the registered earlier release, corrected
supplement or full-precision paper-result joins. Source code and generated
control evidence are separate from authentic reference execution and candidate
performance.
