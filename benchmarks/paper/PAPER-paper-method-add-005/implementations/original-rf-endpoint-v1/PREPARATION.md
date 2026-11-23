# Operator preparation for the source RF comparison

`preparation.py` fills the interface between an admitted native AJILE event tensor and `endpoint.py`. The earlier reconstruction converter validates labels but omits them from its saved extraction, and its training selection retains native row order. Those exports cannot be silently reused for the original RF task. This additive component leaves them and the registered contracts unchanged.

`prepare_arrays` accepts one operator-extracted variable in events/channels/time order, including its final label channel, native event-day coordinates, time and channel coordinates, unique row IDs, participant, source-file digest and explicit input kind. The caller must authenticate the file and verify native variable dimensions. The additive local NetCDF adapter below supplies extraction; no downloader or automatic scientific execution is provided.

The implementation follows the pinned [AJILE loader](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/ntd/datasets.py): read labels at original time index zero, select inclusive signal times from -2 to +2 seconds, concatenate training days in sorted order and hold out the latest day. Range-based training masks determine channel normalization; every event remains in the RF inputs. `source_condition` uses the RF experiment's observed-channel mask without multiplying by quality flags. Its mask seeds and source channel counts reuse the existing endpoint.

The source's dictionary indexer uses the last channel coordinate as a positional index. The adapter requires integer coordinates whose last value addresses the final channel; it refuses an alternative convention instead of silently interpreting it. It also refuses singleton train/test event partitions because the source loader squeezes their event axis before three-dimensional operations. [Xarray's indexing guide](https://docs.xarray.dev/en/stable/user-guide/indexing.html) documents dictionary positional indexing. This guard does not establish the native archive's actual coordinate convention or original xarray version.

Returned `arrays` contains the RF endpoint's prepared fields except the three frozen imputation tensors. The returned metadata records row/time selection, array identities and source lineage. Both are operator-private: they contain held-out signals and labels. `train_quality`/`test_quality` are diagnostics, not permission to filter trials or expose held-channel quality to candidates. Normalization keeps source intermediate precision; the endpoint performs its established float32 conversion. A declared source digest is not authenticity proof.

Use `source_condition(prepared, dropout=..., repeat=...)` only within a separately qualified isolated case run. It returns float32 concatenated mask and observed signal tensors, plus source mask-choice order. It supplies no process isolation: different masks can reveal one another's targets.

Eight generated tests cover label position, interleaved-day sorting, full row retention, analytic population moments, inclusive time selection, test-only perturbation invariance, excluded-range training rows retained for decoding, hidden-value invariance, quality-independent conditioning, existing decoder-input compatibility and malformed metadata. Seven initial methods passed in one shared-pool run; one affected method passed again after tightening coordinate/unsigned-clock guards. Independent review identified the source loader's singleton-partition squeeze behavior; a fail-closed guard and an eighth generated method covering both singleton partitions were added and that new method passed separately. No native data, xarray file read, RF fit or imputation model was run.

The original event/day roster, first-six-days/day-seven correspondence, source environment, original channel coordinates and units, checkpoint lineage, deterministic-neural baseline, numeric published Fig.3E panel, secondary endpoints, candidate isolation and paired scientific decision remain unresolved. This is a source preparation component for future reproduction and same-task improvement, not a claim that either outcome is ready or achieved.


## Local NetCDF adapter

`native_preparation.py` connects an admitted local source NetCDF file to
`prepare_arrays` and writes `prepared.npz` plus `preparation.json` in a new
operator-only directory. Use an existing environment with NumPy, xarray and a
compatible NetCDF backend. It does not install dependencies or obtain data.

```sh
python native_preparation.py /operator/EC01_ecog_data.nc /operator/EC01-prepared \
  --expected-sha256 SOURCE_SHA256 --participant EC01 --kind authentic_input
```

The expected digest must come from the operator's admitted inventory. The adapter
checks it before opening the dataset and after extraction. A digest match alone
cannot establish archive authenticity, participant identity or scientific
admission. The file must remain immutable while preparation runs.

The pinned source uses `open_dataset` defaults and `Dataset` positional indexing.
The adapter accepts exactly one data variable with dimensions ordered
`events, channels, time`, with explicit one-dimensional coordinates. It rejects
multiple variables, absent coordinates and reordered axes instead of guessing a
variable or transposing the source. Existing preparation checks retain original
label time index zero, the inclusive signal interval, sorted earlier-day training,
latest-day testing, every event and unmasked RF observations. Xarray's default
CF decoding remains enabled; unsupported decoded coordinates fail validation.

Row IDs combine the source file digest with each zero-based native event position.
They bind order within these file bytes; they are not recovered historical event
names. Metadata also records coordinate identities, xarray version, native layout
and the saved NPZ digest. Neither the labels nor the missing-channel truth in this
bundle may be supplied to candidates. Add the three frozen, case-specific imputer
outputs through the existing trusted operator workflow before `score-case`;
preparation alone is not a complete scoring input.

`tests/test_native_preparation.py` uses tiny generated NetCDF3 files to check the
pinned source's xarray positional extraction, label timing, retention of a
quality-excluded training event, decoder reconstruction, schema/digest rejection,
NPZ round-trip identity, no-overwrite behavior and cleanup after a write failure.
This does not calibrate another NetCDF backend, the historical xarray environment,
authentic archive layout, paper-day mapping, models or scientific outcomes.

All five generated NetCDF controls passed in the available mixed environment (NumPy 2.4.6, SciPy 1.17.1, xarray 2025.6.1, pandas 3.0.3): 0.408 seconds in unittest, 2.33 seconds process wall time, 155,222,016-byte maximum RSS. This qualifies these software controls only.
