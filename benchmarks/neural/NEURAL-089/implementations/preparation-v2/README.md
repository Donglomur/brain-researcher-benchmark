# Exact-source LibriBrain preparation, version 2

This executable successor repairs two admission defects in the preserved
`../delivery-source/prepare.py`. It retains the original 90 recordings, native
88/1/1 split, fixed 39 phonemes, 306 channels, 250 Hz, 125-sample windows,
training-only population normalization and target-free query outputs. It does
not change the original scorer, programme or canonical task definition.

The predecessor accepted any caller-supplied manifest with 90 unique
single-participant run keys and the native split counts. It also accepted any
39 distinct class labels and any channel schema matching the supplied file.
Consequently a changed training run, swapped phoneme order or swapped channel
schema could pass source specification admission. Version 2 checks the exact
original manifest, class map and channel schema bytes before opening a key,
recording, annotation or output. The existing programme projection already
pinned the original manifest; this repair closes the earlier standalone
preparation boundary and additionally binds class and channel order.

The predecessor applied a timestamp tolerance derived from the last sample to
every timestamp. A generated 806-second float32 recording with 20 microseconds
of drift at 0.1 seconds passed that check, although the drift is thousands of
float32 steps at that early sample. Version 2 admits at most one stored-dtype
ULP around each rounded `sample_index / 250` value, while preserving strict
zero origin and monotonicity. This is a stricter clock admission rule; no
authentic recording has yet been checked against it.

The source definitions are reused from their existing task-local locations:

| Input | SHA-256 |
| --- | --- |
| `../phoneme-programme/source_identity/ORIGINAL_ASSETS.json` | `23489ecda2cfb13fcb425593fa9370f64e4188c8aca7f5c9d79bb4343e0ddcba` |
| `../delivery-source/classes.json` | `f0594452fbda0e081a02a152b9614b34eba0a4971dd30f8bc3eb1458ac9efd9a` |
| `../delivery-source/channel_schema.json` | `cc2970908d20281002c03f84cfffed221428143306f43bdb7e3b3dcf6afdf686` |

The unchanged I/O helper is copied from predecessor SHA-256
`06aa0cd400def6a1013dfde012b543ae60e0e3fe2f5fde80bcb7d3487b33c4ea`.
The parent preparer is preserved at SHA-256
`28021b978f1f5d644d2c2ad084ce04a7cd7e03a7c30eb0a626a733668d10b8c9`.

## Operation

After separate complete source acquisition and resource qualification, run:

```sh
python prepare.py --staged /operator/source-root --output /operator/new-packet \
  --key /operator/private-32-byte-key --max-output-bytes ACTUAL_RESERVED_BYTES
```

The three source definition paths default to the pinned files above. Explicit
`--lock`, `--classes` and `--channels` paths are allowed only for byte-identical
relocations. No online refresh or downloads occur. The existing NumPy/h5py
environment requirements remain those in `../delivery-source/requirements.txt`.
The preparation receipt adds the three source specification pins and the clock
rule; the participant inputs, target schema and primary macro-F1 are unchanged.
The historical programme still requires its own input, execution and method
qualification before adopting any new preparation receipt.

## Checks and remaining limits

`test_prepare.py` uses generated data only. It demonstrates the predecessor
counterexamples, rejects each altered source definition before asset access,
accepts exact relocated bytes, exercises float32/float64 clocks and chunk
boundaries, and checks a hand-computable population normalization, exact onset
window and label-free query export. No estimator is fit.

This is preparation software, not a prepared or empirically qualified
benchmark. The original full source comprises 58,651,836,720 recording bytes
plus 213,412,860 annotation bytes before potentially much larger overlapping
window outputs. No new download, authentic numerical preparation, inference or
score was performed for this successor. The one historical training-run
header/timing inspection remains historical evidence only. Complete source
preparation, native runtime feasibility and reference competence remain open.
Single-participant native-split results do not establish unseen-story transfer,
independent-event replication, or direct/viewer neural interpretation.
