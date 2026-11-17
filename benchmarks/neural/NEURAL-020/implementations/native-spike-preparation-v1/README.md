# Native Area2 spike preparation

This component fills the source-to-tensor boundary of NEURAL-020. It authenticates the exact Han training NWB, reads its complete 826-trial/65-unit spike population and source labels, and produces the public training/query and private gold packets accepted by the preserved `initial-evaluator-v1`. It neither reads the separate test NWB nor changes the two active/perturbed co-bps endpoints.

**Qualification: generated software controls only. No authentic NWB conversion, source-split admission, reference fit or participant trial has been executed for this component.** Native execution still requires a frozen operator protocol and the shared native-compute lease. Source availability does not imply that the registered whole-block split can be satisfied. All existing scientific holds remain.

The native command hashes the complete 1,822,876,234-byte source before HDF5 decoding and checks its subject, session, complete dimensions, heldout flags, and ragged spike/observation arrays. It reads no behavior streams. Its output directory must be new and outside a Git working tree; it contains private target values, source IDs and absolute clocks. Only the explicitly public NPZ pair may be delivered to a participant under a separately qualified transport.

## Source conventions and explicit restrictions

The implementation derives from `nlb_tools/nwb_interface.py` at commit `42f8410b88e12db136910fa2f888b025ea0aa2ae`. The unmodified MIT source fixture and license are included for reproducible generated parity checks. Production conversion does not execute that fixture.

- Spike times become source-global 1 ms indices by rounding `seconds * 1000` to six decimal places and truncating. Multiple spikes in a millisecond are counts, not binary events.
- Observation intervals use `ceil(round(start*1000, 6))` through `floor(round(stop*1000, 6))`, exclusive at the right. The upstream loader applies the first unit's mask to its entire heldin/heldout group. This adapter requires equal intervals **within each group**, permits distinct masks between groups, and rejects other layouts.
- Rebinning at 5 or 20 ms sums observed 1 ms counts and zero-fills unobserved milliseconds, then marks the coarse bin missing if its **leftmost** millisecond was missing. This intentionally retains the pinned upstream convention, including partially observed coarse bins. It does not reinterpret counts as Hz or assume a full-bin observation rule.
- Trial windows are sliced on the global clock using movement onset `[-100, 500)` ms and the upstream 1 µs endpoint guard. The actual first bin is the ceiling of the nominal window start on the source-global grid. A rare fractional onset for which the guard yields fewer than 600 ms worth of bins is rejected; no row is padded, shortened or dropped.
- All 826 rows are retained, including explicitly excluded splits. Counts are complete 600 ms windows with same-role overlap retained. This matches the registered fixed-window tensor boundary and the upstream **evaluation** overlap behavior. It does not claim parity with upstream training tensor creation, which can truncate overlapping trials. Protocol/scientific admission must resolve this distinction before an authentic comparison.
- Source float16 counts must preserve integer identity at the 1 ms and rebinned levels; otherwise conversion fails explicitly. Final packet arrays use float64.
- Recording blocks are the union of actual source observation intervals across all units. Each complete actual-bin window must lie within one block. The preserved evaluator rejects a block shared by train and evaluation roles, as well as overlapping train/evaluation windows. These restrictions may reject the native split. The adapter never changes native split labels, exclusion roles, condition labels, unit masks or trial identities to force acceptance.

The `private_native_audit.json` retains native movement events and actual source-clock bin left edges. The existing metadata window fields now describe the actual count-support interval, so overlap checks apply to the data actually delivered. Public packets retain the original nominal relative grid, opaque trial IDs, explicit unit axes and spikes-per-bin units; native clocks and bump labels remain private. The grid is relative to the source-rounded alignment event, as in pinned NLB, with sub-bin event quantization documented here.

## Operator interface

Use an existing pinned Python environment containing NumPy, pandas and h5py. The generated exact-source controls use Python 3.9.6, NumPy 1.26.3, pandas 1.3.4, and h5py 3.11.0. The previous evaluator remains a package-relative dependency and is checked against its recorded SHA256. No dependency installation or network request occurs.

```sh
python native_prepare.py --nwb /private/source/sub-Han_desc-train_behavior+ecephys.nwb \
  --protocol /private/frozen-protocol.json --bin-width-ms 20 \
  --output-directory /private/new-neural020-packet
```

`frozen-protocol.json` has exactly two fields: `protocol` is the six-field protocol object required by the predecessor evaluator; `exclusions` maps every native split assigned role `excluded` to its explicit reason. The operator must freeze the split mapping, selection rationale, condition policy, access policy and resource budget before execution. This component supplies no fabricated authentic split policy. A conflicting native block assignment is an error requiring scientific review of the original contract, not an automatic retry with different exclusions.

Outputs are `public_training.npz`, `public_query.npz`, `private_gold.npz`, `private_protocol.json`, `private_native_audit.json`, and a `private_receipt.json` binding their file hashes and packet identity. The native audit distinguishes a pure generated snapshot conversion (`source_file_authenticated: false`) from the byte-authenticated command (`true`). File authentication alone does not qualify the scientific benchmark.

The old scorer and its 22 controls are preserved. The new tests independently execute four byte-pinned upstream methods on generated NWB-like objects, compare both 5 and 20 ms grids/counts, and exercise source-specific failures and complete 826-by-65 packet projection. A generated HDF5 fixture verifies exact-byte rejection and native ragged field extraction. Run them through the reviewed shared two-slot test pool during the parallel build. No synthetic value is represented as an authentic observation or model result.

All 12 generated controls passed using the existing source-compatible environment. The first generated run under pandas 3 passed the new adapter and packet checks but could not run upstream resampling: the old method's in-place `nan_to_num` received a read-only pandas array. A subsequent launch exposed the existing preparation environment's x86-only compiled dependencies; the final run used `arch -x86_64`. Both failed attempts are preserved in external records. The source fixture was not patched; source parity requires the existing pandas 1.3.4 preparation environment. This is source-library compatibility evidence, not a native scientific result.

## Pins

| Input | SHA256 |
| --- | --- |
| Exact Han training NWB, DANDI 000127 / 0.220113.0359 | `639b1a03ab813f96fec76681110a1634942476badc0fd4c93d406c24701f5db2` |
| Upstream `nwb_interface.py`, 39,359 bytes | `5f77fe3d25d120934c44c8ac1c26f07303eeec9db4821c69406726b141f66121` |
| Predecessor `evaluator.py` | `4a6263059ca21aadfeec97bf405ba4f8a454da6a1d92d7f205cb468a25916d23` |
| Preserved historical target definition | `8b922ac0214da6a1cb1ca5c0320cab90aaf6dab0e51f8ce44a552b0ecfcc718a` |

Source: [pinned organizer loader](https://github.com/neurallatents/nlb_tools/blob/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/nwb_interface.py), [Area2 defaults](https://github.com/neurallatents/nlb_tools/blob/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/make_tensors.py), [versioned acquisition](https://dandiarchive.org/dandiset/000127/0.220113.0359). The exact local code cache and previous independent source review were reused; no new source download was needed.
