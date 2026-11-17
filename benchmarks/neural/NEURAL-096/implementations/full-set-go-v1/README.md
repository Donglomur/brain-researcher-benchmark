# Complete observed Set–Go intervals

This source-preparation route retains every spike in the complete native Set–Go interval for all **204 nominal-800-ms source train/validation trials** from Haydn's 20161211 recording. It uses all **54 released source-training units**, preserving their 40 held-in / 14 held-out NLB labels. This is a new observation packet for the current retrospective question; the historical 177-trial, 40-unit pre-Set calibration remains separate.

The authenticated local preparation produced a 640,017-byte packet containing **81,311 spikes**, full trial and unit identities, exact native spike timestamps, 20 phase-bin counts, and each bin's actual exposure in seconds. No recording download, model fit, effect estimate or solver trial occurred. The implementation validates whole-interval observation support before reading spikes. An unsupported selected trial blocks the whole packet; it is never silently dropped.

The packet is **not a completed scientific benchmark**. A full-trajectory reference contrast, nuisance analysis, defensible blocked uncertainty, participant delivery and scientific qualification remain unresolved. The six observation segments are not verified randomized assignment blocks. Three prior × effector × direction cells in the final two segments are empty; those zeros are retained and explicitly reported. Deleting segments could measure sensitivity but cannot, by itself, supply a calibrated confidence interval or randomization test.

## Prepare the original source

Use Python with NumPy and h5py. The recorded preparation used Python 3.11.6, NumPy 2.4.6 and h5py 3.16.0. No equivalence with the historical paper's GPFA implementation is claimed.

```sh
python prepare.py \
  --source /absolute/path/to/train.nwb \
  --output /absolute/path/outside/git/full-set-go-packet \
  --reserve-bytes 64424509440
```

The source must be the exact 14,119,912-byte [DANDI 000130 training asset](https://api.dandiarchive.org/api/assets/c90cbccc-31a5-4815-88e6-822d8c5ca68c/download/), version `0.241017.1448`, SHA256 `6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198`. It is CC BY 4.0. Output must be new and outside a Git worktree. `--reserve-bytes` is an operator storage reserve, default zero for portable use; the construction wave explicitly used 60 GiB. Output is capped at 20 MiB. Resource limits in `PROTOCOL.json` describe the reviewed construction run; a calling operator must enforce execution limits separately.

`observations.json` records the complete 1,160-row selection census, all 204 selected trial identities/events, unit identities, six native observation segments, and all support cells including zeros. Selection uses source split plus exact nominal `ts == 800`; it does not filter on outlier status, behavior, neural activity or overlap of prior clock ranges. No `tp`, outcome/outlier column, separate test asset, protected reference or earlier solver answer is read.

`observations.npz` uses a closed eight-array representation:

| Array | Shape / meaning |
| --- | --- |
| `counts` | `(204, 54, 20)`, uint32 spike counts |
| `phase_edges_seconds` | `(204, 21)`, native recording seconds |
| `exposure_seconds` | `(204, 20)`, positive bin durations in seconds |
| `spike_times_seconds` | All retained native float64 timestamps, trial-major then unit-major |
| `spike_offsets` | `(204*54 + 1,)`, offsets into the timestamp vector |
| `trial_ids` | `(204,)`, ascending native Set-time order |
| `unit_ids` | `(54,)`, original source-unit order |
| `nlb_heldout_unit_flags` | `(54,)`, original NLB labels |

Every interval is half-open: a spike at Set is included and a spike at Go is excluded. Phase edges use exact rational interpolation of the supplied binary64 endpoints, followed by one rounding; the stored edges define bin membership. Counts divided by exposure give rates in spikes per second per source unit. Phase normalization changes speed information, so the original timestamps, event duration and real exposures are retained. No smoothing, latent fitting or feature selection occurs.

`receipt.json` binds source bytes, implementation hashes, output hashes, dependency versions, actual field reads and costs. It explicitly sets `scientific_qualified` and `full_task_completed` to false. The recorded preparation took 0.280 child CPU seconds and 0.284 seconds wall time; the worker reported 55,902,208 bytes peak RSS. These are source-preparation measurements, not model performance.

## Scientific interpretation

The [original study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6805134/) jointly manipulated prior and effector in blocks and randomized response direction. Observed cue runs and recording segments do not recover every experimental assignment boundary. Behavioral `tp` and neural Set–Go timestamps also have different endpoints; this packet uses the released native `set_time` and `go_time` directly. It does not replace Go with `Set + tp`.

The target is retrospective and response-conditioned. One already exposed monkey/session cannot establish cross-animal generalization, prospective behavioral prediction, a unique causal timing mechanism, or a language model's native neural understanding. A positive prior contrast is not a better answer than a negative or unsupported result.

## Engineering checks

```sh
python -I -B -m unittest discover -s /absolute/path/to/full-set-go-v1 -p 'test_*.py' -v
```

Generated controls independently check endpoint membership, raw count conservation, exact edge rounding, observation gaps, complete support cells and malformed numerical inputs. A wider-than-binary64 check is explicitly skipped on platforms where NumPy's widest float is only 64 bits. These controls do not establish a scientific effect.

An independent saved-packet audit recounted all 220,320 trial/unit/phase cells from retained timestamps and verified the complete 204-trial roster against earlier source metadata. It did not reread the original NWB spike vectors; the 14 additional unit IDs were checked against prepared metadata, whereas the 40 held-in IDs also matched the earlier source audit. `AUTHENTIC_PREPARATION.json` preserves these limits and exact execution-file and receipt hashes. Source was uncommitted during execution, so no execution commit is invented.
