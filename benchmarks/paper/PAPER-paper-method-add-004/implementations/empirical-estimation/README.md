# iSTTC empirical four-estimator producer

This implementation fills the missing computation between frozen empirical spike recordings and the existing [empirical diagnostics](../empirical-diagnostics/README.md). It produces all **23,100 unit-by-method fits for 5,775 units across 26 mice**, including failed fits. It belongs to `PAPER-paper-method-add-004`; it adds no benchmark ID.

The complete selected capability is per-unit four-estimator fit production for the Figure 7C reconstruction. It does not implement the Figure 7C GLMs, other panels, an improvement study, or the entire paper. Authentic cohort/QC admission, historical numerical parity and scientific reproduction remain unqualified. Source tests use invented inputs; they do not demonstrate biological results.

## Source-grounded computation

The [paper's Figure 7](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013385) specifies 50 ms bins/lags, 25 ms iSTTC tolerance and 20 lags. The pinned [official source](https://github.com/iinnpp/isttc/tree/e78cfd2b2ea79b7a7e707db7b79e218212497e43) supplies the selected algorithms. [SOURCE_BINDING.json](SOURCE_BINDING.json) records exact files, notebook cells, hashes and important differences from the driver defaults.

| Output method | Calculation on the complete assigned recording or trials |
|---|---|
| `acf_full` | Bin the full 30-minute recording at 50 ms; `statsmodels.tsa.stattools.acf(..., nlags=20)` |
| `isttc_full` | Author `acf_sttc` on the full 30-minute recording: 1,500-tick lag and 750-tick tolerance at 30 kHz |
| `pearsonr_trial_avg` | Bin the same forty one-second trials into twenty bins; author `acf_pearsonr_trial_avg` |
| `sttc_trial_concat` | Author `acf_sttc_trial_concat` on the same trials, with 90,000-tick offsets and the pinned within-trial shift and normalization rules |

Both full-recording curves have 21 points (lags 0–20); trial curves have 20 (lags 0–19). The pinned `fit_single_exp` fits every curve starting at index 1 and returns tau in 50 ms lag bins. The adapter preserves its exponential form, bounds, fit budget and failure behavior. It does not pad trial curves to 21 points, shift trial boundaries, alter the fitter, refit a calibration, or select favorable units. Finite negative R-squared values and nonpositive tau remain available to the unchanged downstream diagnostic rules. Nonfinite fitted fields become null with a reason. A source/interface mismatch stops production; it is not reclassified as a scientific fit failure.

The upstream full-ACF notebook explicitly supplies the selected 50 ms/25 ms parameters. Some `run_allen_mice_data.py` defaults instead use a 1,501-tick full-signal lag, 1,500-tick tolerance or 100 trials. This adapter selects the paper and the matching notebook configuration. It is not a byte-for-byte replay of that driver's default workflow or historical saved outputs.

## Inputs and outputs

`produce(cohort, recordings, windows, backend)` returns `(estimates, receipt)`. It accepts the unchanged complete [cohort schema](../empirical-diagnostics/cohort.schema.json), an ordered stream of normalized recordings, and every row produced by the existing `empirical_bridge.py windows` command. Each recording is exactly:

```json
{"schema":"isttc_empirical_spikes_v1","unit_id":"OPERATOR_UNIT_ID","fs_hz":30000,"signal_ticks":54000000,"spike_ticks":[0,1500,30000]}
```

This JSON is an **adapter transport**, not an invented claim about Allen's original file format. The operator must bind each row to the actual original unit, first thirty-minute spontaneous interval and complete cohort. Timestamps are sorted integer 30 kHz ticks in `[0, 54000000)`. Duplicate timestamps and empty signals remain inputs. No floating-point timestamp rounding, source acquisition, QC selection or original-file conversion is performed here.

There must be exactly one recording and one window record for every cohort unit, in the cohort's frozen order. IDs are checked on every row; they are not joined by position alone. Every window is half-open, one second long and inside the recording. The producer independently regenerates the unchanged bridge's complete prospective sampling sequence from the declared seed. Altered windows cannot masquerade as that draw. Repeated/overlapping windows are retained, and each trial's times are reset to its own start. This does not recover historical RNG or preclude an external operator from selecting a seed after seeing data; prospective seed selection/custody remains an admission requirement.

The result follows the existing [estimates schema](../empirical-diagnostics/estimates.schema.json). Every method is attempted for every admitted unit. Missing/extra/reordered or malformed input stops production without returning a partial table. Scientific fit failures retain their coordinates. The receipt binds the cohort, every normalized recording, windows, estimates, selected source and observed dependency versions. Its hashes establish content consistency, not original-data authenticity or independent custody.

## Future operator command

The official helper source must exist in an operator-supplied checkout at the selected revision. The adapter verifies the exact three helper files before executing their bytes. It does not download dependencies, copy author scientific source into this package, import upstream driver/notebook state or install anything. NumPy, SciPy, scikit-learn and statsmodels must already be available in the selected Python environment. Their observed versions are recorded; publication-time dependency parity is not asserted.

From this implementation directory, a future admitted run can use:

```sh
python3.11 -I -B producer.py \
  --cohort /ABSOLUTE/COHORT.json \
  --recordings-jsonl /ABSOLUTE/RECORDINGS.jsonl \
  --windows-jsonl /ABSOLUTE/WINDOWS.jsonl \
  --author-checkout /ABSOLUTE/PINNED_ISTTC_CHECKOUT \
  --output-directory /ABSOLUTE/FRESH_OUTPUT
```

The output directory must be absent. Only after all inputs close and the full table validates does the producer create `estimates.json` and `receipt.json`. Require both complete files, their matching hashes and a successful process exit: filesystem publication is not an atomic transaction or a durability guarantee. Record streams are read one unit at a time; cohort metadata is limited to 16 MiB, each spike JSONL record to 64 MiB and each window record to 32 KiB. These logical limits are not hard process memory, CPU or wall-time enforcement. Native fits can be expensive; the pinned fitter's `maxfev=1_000_000_000` is intentionally unchanged. A future execution owner must supply admitted resource limits and lifecycle handling.

## Source controls and remaining science

Run generated controls without scientific dependencies:

```sh
python3.11 -I -S -B -m unittest discover -s . -p test_producer.py
```

The source controls exercise complete generated populations, exact backend calls, trial boundaries, missingness and rejection behavior. Any separately recorded small real-backend interoperability check uses invented spike data and does not qualify authentic empirical execution or numerical equivalence to the paper.

Original 5,775-unit/26-mouse identities and the eight-area membership still require source admission, including the paper amplitude-cutoff criterion of 0.01 versus the retained acquisition default of 0.1. Covariates retain the existing `lv_df.pkl` mapping; the producer does not replace them. Full-recording fits are method-specific pseudo references, not biological ground truth. Reproduction gives both full recordings and trials to the producer; a future constrained-data improvement contract must withhold full-recording references. No improvement metric, paper-pass tolerance or qualified-result claim is added here.

See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE) for this component's GPL-3.0 distribution boundary. Paper, data and dependency rights remain separate.
