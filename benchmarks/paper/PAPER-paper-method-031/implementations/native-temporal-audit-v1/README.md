# FAST native temporal audit

This independent arithmetic component distinguishes two **different pinned author
inference routes** that save arrays of the same shape. It computes the exact
window-to-frame weights, maps reflected input frames back to original identities,
reconstructs logged fixed-pixel output traces, applies the source uint16 export,
and checks the acquisition dependence introduced by full-stack centering. It does
not run a denoiser or score paper improvement.

The existing `initial-evaluator-v1` remains a prospective, recording-disjoint
measurement recipe. This component adds no split: source-permitted same-stack
self-supervision remains permitted. Electrophysiology, source pixel identities,
and clean synthetic references are neither opened nor invented.

This operator component can support both first-class paper outcomes: reproduction
of the original finding and exceeding it on the same task. Those outcomes need
separate scores. The component is not automatically delivered to participants
in the paper+data condition: it encodes author-code knowledge that must remain
distinguished from the paired paper+data+author-code condition. Neither outcome
nor paired participant delivery is qualified by these generated controls.

## Source distinction

At author commit `6f92663f7a36589507cac57c8d24cfd8adbce7b1`:

| Property | `test.py` CLI | `test_in_gui.py` GUI |
| --- | --- | --- |
| Original frames | `T` | `T` |
| Dataset tail | Reverse the last `min(T,100)` frames, repeating the endpoint | Same |
| Centering mean | All pixels of original **and appended** frames | Same |
| Window starts | `0` through `T-C` inclusive | `0` through `T-1` inclusive |
| Forward count | `T-C+1` | `T` |
| Reflected frames enter network | No | Yes when `C>1` |
| Saved frame support | Exactly `0` through `T-1` | Exactly `0` through `T-1` |
| Overlap reduction | Recursive half averaging | Recursive half averaging |

Here `C` is `miniBatch_size`, not the outer DataLoader batch size. Both routes are
analyzed under the pinned default outer batch size of one. The default `C=4` is
source configuration, not proof of the exact Figure 3 setting. For the paper's
reported 4,982-frame example, the schedules imply 4,979 CLI windows and 4,982 GUI
windows at `C=4`. These are calculated metadata counts, not observed author runs.

For a frame receiving four window predictions, source weights in invocation
order are `1/8, 1/8, 1/4, 1/2`, not `1/4` each. In the CLI the last original frame
receives one prediction; the GUI can update that frame four times. A shape check,
global frame count, or claim that both are “FAST” cannot establish route parity.
The last `C-1` original frames have different overlap support; earlier frames
have identical support. Actual numeric equality can still occur for particular
predictions and is not assumed or excluded by the support audit.

Both paths calculate their mean before inference over the entire augmented
recording. Thus even the first output requires the last original input under
these literal execution paths. A `C-1` frame lookahead declaration alone omits
that acquisition dependence. `acquisition_bounds` computes a necessary bound;
it does not measure training, transfers, inference, postprocessing, file output,
or queue delay. This observation concerns these pinned offline implementations,
not every possible FAST deployment or an independently implemented online path.

## Use

Only Python's standard library is required. The CLI reads dimensions, not data:

```sh
python3 -I -B benchmarks/paper/PAPER-paper-method-031/implementations/native-temporal-audit-v1/temporal.py \
  --frames 4982 --channels 4 --route gui --inspect-frame 4981
```

An optional `--output` writes a new JSON report and refuses to replace a file.
Reports contain no source filesystem paths or numerical observations.

The Python API provides:

- `TemporalPlan(T, C, route)`: validates the temporal extent, supplies exact
  rational contributions for each original frame, and maps each network window
  to its original input frame identities. GUI settings that exceed its fixed
  reflected tail are rejected; they are not silently padded further.
- `augmented_mean(frame_sums, pixels_per_frame)`: an algebraic reference for the
  full-spatial augmented mean. Frame sums must cover every spatial pixel; a mean
  over selected diagnostic pixels is a different computation.
- `reconstruct_traces(plan, windows, source_mean)`: accepts an iterator of
  `(window_start, channel_by_pixel_values)`. Values are the logged centered
  network outputs at a fixed external pixel roster. It rejects missing, extra,
  reordered, duplicate, nonfinite, or dimension-changing windows, returns all
  original-frame traces, restores the supplied mean and clips to `[0,65535]`
  before truncation to integer. It does not infer a pixel roster from predictions.
- `acquisition_bounds(plan, input_available_s, output_available_s=None)`: returns
  necessary acquisition delay for all original frames and rejects outputs
  preceding full-stack availability when a complete output timeline is supplied.

The arithmetic uses Python floats and exact fractions, not PyTorch's float32
reduction order. It is a software oracle for structural and algebraic checks;
bitwise native equivalence is unestablished. Do not replace native inference or
the native mean with this component while claiming a literal author run.
Reconstruction memory scales with `T × diagnostic_pixels`; native deployment
still needs its separately approved resource protocol. Pixel identities must be
frozen independently before any source-fidelity comparison.

## Verification and limits

`tests/test_temporal.py` has generated controls for a hand-calculated CLI/GUI
counterexample, nonuniform overlap weights, reflected endpoint identities,
all short-stack boundary cases, complete ordered window coverage, clipping and
truncation, augmented versus plain mean, full-stack acquisition dependence, and
immutable CLI output. No recording, weight, model, or target is used.

The earlier local complete FAST operator already contains CLI native inference;
this component does not duplicate its CUDA model runner. Its missing contribution
is the explicit GUI/CLI distinction plus a model-independent oracle with exact
frame ancestry and acquisition bounds. That operator's source provenance was
inspected without reading historical private target or prediction artifacts.

The exact Figure 3 author route, numerical baseline, pixel roster, ΔF/F recipe,
electrophysiology synchronization, aggregate, full registered real-calcium and
real-voltage coverage, matched controls and uncertainty remain unresolved. No
new native preparation, author calibration, candidate run, paper win or SOTA
claim is made. Neither canonical contract nor prior evaluator is changed.

Source pins and requirement mapping are in [provenance.json](provenance.json).
