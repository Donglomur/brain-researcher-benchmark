# Calibrated causal EEG windows

This operator component fills the sample-decoding gap after the existing
[original-file admission](../source-admission-v1/README.md). It returns selected
EEG samples in microvolts from an authenticated classic EDF recording. It does not
change the 686-record, 23-person task, event scorer, annotations or LOPO folds.

The operator must first authenticate the complete admission and its channel,
clock, normalization and rights review. A `RecordWindow` takes one admitted row,
authenticates its entire EDF against the row's original-file hash, checks header
and native-support agreement, and keeps that same file descriptor open. The
source-admission helper is loaded only after its exact committed hash is checked.
Use a context manager so the descriptor closes on success or error.

```python
with RecordWindow(
    original_edf, admitted_record,
    max_edf_bytes=declared_file_budget,
    max_window_samples=declared_window_budget,
    max_output_values=declared_value_budget,
) as recording:
    window = recording.window(start_sample, stop_sample,
                              available_through_tick=endpoint_tick)
```

The returned channel order follows the reviewed **indices**. Duplicate bipolar
labels remain distinct. Annotation, known dummy `-`, and reviewed non-EEG channels
are refused as predictors. The result contains sample bounds/rate, endpoint tick,
channel indices/labels, units and values. Patient fields, source filenames, source
hashes and annotation contents are omitted. That projection is not filesystem or
participant isolation; this Python object and its file descriptor stay operator
side. A protected delivery transport and opaque case identities remain separate.

## Calibration and timing

EDF stores channel-major samples within each data record. Calibration uses the
declared digital and physical extrema:

`physical = physical_min + (digital - digital_min) * (physical_max - physical_min) / (digital_max - digital_min)`.

The code converts `V`, `mV`, `uV` or `nV` to microvolts. Unknown or empty units and
invalid calibration are refused. Extrema are parsed as bounded exact decimals;
output is finite binary64. There is no filtering, resampling, rereferencing or
statistical normalization. See the [official EDF specification](https://www.edfplus.info/specs/edf.html).

Little-endian signed16 samples and negative amplifier gains are supported.
Classic EDF must declare continuous records. EDF+C and EDF+D are both refused
here pending separate annotation-clock qualification; no unreviewed gap is
flattened. These are explicit limitations of this component, not exclusions from
the benchmark cohort. See the [official EDF+ specification](https://www.edfplus.info/specs/edfplus.html).

Windows use half-open native indices `[start, stop)`. Under the explicit
recording-relative convention, sample `j` has timestamp `j / Fs`; endpoint tick
`t` admits only samples satisfying `j / Fs <= t / 10`. Integer arithmetic handles
noninteger endpoints exactly. At 256 Hz, tick 1 permits indices 0 through 25;
tick 5 permits 0 through 128. This is sample availability, not hardware or software
alarm latency. Reads crossing data-record boundaries retain channel layout and
never bridge separate EDF files. Window/value budgets refuse the request rather
than truncating support.

## Validation and remaining work

`python3 -I -S -B test_edf_window.py` exercises generated EDF bytes, including
asymmetric calibration, negative gain, signed endian decoding, mixed unselected
rates, duplicate labels, exact causal boundaries, future-sample perturbation,
metadata omission, file mutation, identity mismatches and budget refusals.

No original EEG samples were read during construction. The complete corpus still
needs actual header/montage/clock qualification, admitted preparation, a competent
EEG-derived reference, nuisance controls, protected participant execution and
scientific evaluation. If any cohort file requires an unsupported clock or unit,
full-cohort preparation remains blocked; callers must not drop it. A record-level
window helper does not establish a direct, viewer, tool-assisted or frozen-program
condition, predictive performance, clinical usefulness or benchmark readiness.

The [CHB-MIT publisher page](https://physionet.org/content/chbmit/1.0.0/) describes
montage variation, non-EEG channels, dummy channels and recording gaps. Existing
pinned manifests determine the task population; older descriptive counts on that
page do not replace them. Source observations above were read through official
web pages; no new raw-source capture or source-version authentication is claimed.
