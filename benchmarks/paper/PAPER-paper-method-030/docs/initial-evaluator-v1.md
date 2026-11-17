# Paired optical/electrical aligned-trace evaluator

This package implements a complete **prepared-trace assessment endpoint** for CellMincer's paired BeRST experiment. It computes published prominence-tolerant peak recovery, lagged correlation, false events, and a documented residual-spectrum diagnostic; compares raw, a fixed smoothing control, CellMincer, and a matched PMD or Noise2Self result on exactly the same test recordings. It does not train or run a denoiser, read TIFF/ABF, derive native ROIs, or establish authentic reproduction. Scientific qualification remains **unknown**.

## Source and population

The authoritative task remains `PAPER-paper-method-030/task.json`, SHA-256 `6de9351af83dcd990e576873f65802b6df7df963dbdf3c008100b1d87dc0806e`. The [published article](https://www.nature.com/articles/s44303-024-00055-x), accessible as [primary full-text XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11618097/fullTextXML), defines equations 21–23. Exact retrieved article/metadata hashes and source revision locators are in `source-provenance.json`. The author code snapshot is `8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942`; its [standard manifest](https://raw.githubusercontent.com/cellarium-ai/CellMincer/8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942/configs/manifest/miller-ephys-standard.yaml) specifies one 5,000-frame segment at 500 Hz. Native payload shape is not verified here.

`population.json` maps **all 22 raw TIFF/ABF basename pairs** in the saved task inventory, preserving object names, bytes, and GCS generations. These yield nine groups from recording-date and cell-number names. Raw-prefix metadata was independently rechecked without downloading objects. Neither matching filenames nor metadata proves biological independence, exact paper-subset membership, or payload correctness. The paper trained deep models on up to 26 datasets and selected 22 activity-bearing recordings for evaluation. The missing four training identities and precise historical selection remain unresolved. Supplied CellMincer/N2S/PMD/SUPPORT outputs and processed electrophysiology are excluded as fresh input.

## Mathematical endpoint

For each EP prominence `p`, the code obtains peaks and global prominences from `scipy.signal.find_peaks`. Flat peaks use the midpoint index (rounded down); peaks at boundaries are excluded. Inclusion uses `prominence >= threshold`. These extraction conventions are prospective where the paper does not specify them.

The published metric counts a predicted peak as matched if **any** EP peak lies at absolute time difference **strictly less than 2 ms**; recall counts each EP peak with any predicted neighbor. This is existential matching and deliberately allows many-to-many matches. At 500 Hz a one-frame difference is exactly 2 ms and fails the displayed paper inequality, despite the prose's “one-frame discrepancy” description. A numerical guard of the smaller of 1 ps or one millionth of the tolerance prevents floating-point subtraction from admitting the exact boundary. This discrepancy is retained, not silently converted to an inclusive tolerance.

`F1*(p)` maximizes the harmonic precision/recall mean over predicted prominence thresholds in `[p−0.2, p+0.2]` mV. The finite search evaluates both endpoints and values immediately above each internal predicted prominence, covering every possible eligible peak set. This optimization is the paper's **grader-side oracle metric**, not a candidate fitting permission; the optimizing threshold is not released in the report. Empty precision/recall denominators produce null, both-empty F1 is null, and one-empty F1 is zero. Those empty-set conventions are explicit prospective policy.

The package reports seven thresholds, `0.5, 1, 2, 3, 5, 10, 20 mV`, individually. This is a prospective grid, **not a reconstruction of unidentified Figure 3e bins or quadrature**. F1 aggregation uses a common EP-positive recording support at each threshold for every method; it exposes excluded counts. All recordings contribute to separately reported fixed-threshold false-event rates at every prominence in the grid, including silent EP recordings; the 20 mV spike profile is also separately named. No undefined empty case can silently improve F1 by changing a method's denominator.

Pearson correlation is computed on overlap at lags −5 through +5 frames, with positive lag meaning the optical signal is delayed. Zero-lag correlation is separately named; lag maximization is not substituted. Constant EP is excluded using common reference support. A constant candidate on nonconstant EP makes that cell and its overall correlation aggregate **undefined**, preventing candidate-dependent omission. RMSE in mV is also returned per recording.

The spectrum uses residual `optical−EP`, STFT length 64 and overlap 48 from the article. The periodic Hann window, no boundary extension/padding, no detrending, SciPy `scaling='spectrum'`, and `1e−12 mV²` log floor are prospective choices. A required evaluator-frozen EP-power ceiling excludes windows by the sum of EP STFT powers. The same EP mask applies to every method. Powers are converted to dB **before** averaging across eligible windows; raw-minus-method is then the noise reduction. Frequencies and their gains remain explicit; the mean above 100 Hz is separately labeled. No eligible windows yields an undefined diagnostic. The original window/boundary/ceiling choices remain a historical reproduction hold.

## Held-out and private-reference contract

The evaluator-owned panel assigns every frozen recording to train, validation, or test, using all three splits. Entire date-cell groups must stay together; missing, duplicated, unexpected, or relabeled recordings fail. This prospective held-out design differs from the paper's all-recording self-supervision. It is not a historical split claim. Acquisition/culture/animal-level independence cannot be inferred from filenames and remains unverified.

The operator supplies already aligned, calibrated **5,000-sample mV traces at 500 Hz**, with one frozen alignment evidence SHA-256 per recording. Native preparation must establish shared raw-derived soma ROIs, channel/polarity/units, clock mapping, filtering, and calibration. The paper uses raw-only ROI selection, one-second optical median detrending, 51-point cubic Savitzky–Golay EP filtering at 50 kHz, peak correspondence plus interpolation, and optical-to-EP affine L2 fitting. This endpoint deliberately requires calibration frozen independently of test EP. It does not claim that such calibration already exists or that it reproduces the paper's EP-fitted transform.

Private EP and raw reference traces go only to the grader's `--private-reference` file. Candidate submissions contain method outputs and explicit exposure declarations: no electrical-target access and fitting cells confined to train. The code validates declarations; it cannot prove process isolation or access honesty. An isolated broker, authorized native conversion, content-verified alignment evidence, and authentic fresh-output lineage remain admission requirements. Never place private EP in a candidate packet. Per-recording grading output contains reference-derived counts and should remain evaluator-controlled during protected evaluation.

CellMincer plus at least one matched `pmd` or `n2s` trace is mandatory. Their names do not certify execution or competence. Raw is a trusted grader reference. The three-frame, edge-extended `boxcar3` is a fully implemented weak engineering control, not a substitute for a historical baseline. All methods must cover every test recording. Recordings are averaged within cell, then eligible cells receive equal weight; sample or recording count does not create additional biological replicates. Defined/total counts remain visible. No aggregate p-value or empirical uncertainty is claimed.

## Interface and commands

Existing NumPy and SciPy are required; no packages were installed. Validation used Python 3.11, NumPy 2.4.6, and SciPy 1.17.1 via `/opt/homebrew/bin/python3.11`. The workspace's default `python3` lacks SciPy; select an existing suitable interpreter explicitly.

```sh
/opt/homebrew/bin/python3.11 -m unittest discover -s benchmarks/paper/PAPER-paper-method-030/implementations/initial-evaluator-v1/tests -v
/opt/homebrew/bin/python3.11 benchmarks/paper/PAPER-paper-method-030/implementations/initial-evaluator-v1/evaluator.py \
  --panel panel.json --private-reference protected-reference.json \
  --submission submission.json --output assessment.json
```

Paths above are relative to the repository root. The tested CLI writes strict JSON, emits no private trace arrays, and rejects incomplete input before writing a result. The output file must be in an evaluator-controlled location. Tests create temporary generated inputs; there are no authentic inputs or downloadable datasets in this package.

The panel has `task_id`, the SHA-256 of the exact `population.json` bytes as `population_sha256`, `recordings` objects with `recording_id`, `cell_id`, and `split`, `methods` such as `["cellmincer","n2s"]`, `alignment_policy: "externally_frozen_no_test_ep_fit"`, and `spectral_policy: {"ep_power_ceiling_mv2": <positive number>}`. The ceiling must be frozen on training/validation evidence before viewing test results; this package supplies no invented historical cutoff. Unknown spectral-policy fields fail.

The private-reference object contains `reference_access: "grader_only"`, `units: "mV"`, `sampling_rate_hz: 500`, and `recordings` mapping **exactly all test IDs** to `ep_mv`, `raw_mv`, `alignment_source: "frozen_external_calibration"`, and `alignment_sha256`. The submission contains the same units/rate, `method_access` mapping every requested method to `electrical_targets_accessed: false` and `fit_cell_ids`, plus `recordings` mapping exactly the same IDs to each method's numeric vector. Shapes must match exactly; NaN/infinity fail. The executable fixture in `tests/test_evaluator.py` is the full machine-readable example, clearly marked generated.

## Requirements and remaining holds

| Registered requirement | Implemented scope | Remaining gate |
|---|---|---|
| Paired TIFF/ABF family | Complete saved 22-pair map with generations and cell grouping | Payload, channel, units, ROI, and historical 26/22 identity validation |
| Signal/event fidelity | Published fuzzy F1* kernel; separate lag correlation, RMSE, false events, residual spectrum | Native alignment and unidentified original numerical conventions |
| Raw and baseline comparison on same cells | Exact method/test coverage, raw/boxcar controls, required PMD or N2S output | Fresh authentic denoiser generation and equal observation budgets |
| Whole-cell separation and private targets | Full panel validation, same-cell split rejection, explicit exposure checks | Isolated execution, actual calibration lineage, biological independence |
| Reproduction/improvement qualification | No scientific reward or qualification emitted | Authentic native reference, expected results, resource measurements, independent empirical assessment |
| Rights | No dataset or author-code payload redistributed | Public GCS access does not establish dataset reuse/redistribution rights |

Generated controls verify algorithms, adversarial coverage, and CLI behavior only. Native training, dataset acquisition, and authentic scientific runs remain at zero. Canonical specification, historical records, registry, catalog, and task counts are unchanged.
