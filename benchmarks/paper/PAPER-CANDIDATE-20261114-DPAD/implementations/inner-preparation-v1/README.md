# DPAD inner-CV array preparation

This operator component prepares the two inner selection folds from already
preprocessed, authenticated **outer-training** arrays. It supplies the missing
array stage before native architecture fitting; it does not prepare raw spikes,
fit a model, add a scorer, or establish the original Figure 6 experiment.

`iter_inner_preparation(y, z, sample_ids, channel_layout, scaling=...)` yields
two folds. Inputs and outputs use time-by-channel float64 arrays. The caller
must explicitly choose all four mean-removal/z-score flags. No publication
configuration is guessed. Channel identities and units, including the four
position/velocity roles, are preserved without conversion. The paper's fourth
dataset reports 77–99 single units and 2D cursor position plus velocity. The
required behavior IDs/order (`position_x`, `position_y`, `velocity_x`,
`velocity_y`) are this component's caller-admitted representation, not a
recovered historical column ordering. An upstream caller must establish and
document the original-column mapping; this component neither discovers nor
reorders columns. The dimension-general author helpers do not impose this
restricted dataset profile, and the width check does not recover the selected
electrodes.

The source chain is the pinned author implementation at
`41f108bc90252ced19fe3c8eda7eaff2e87c57b3`:

- `fitDPADWithFlexibleNonlinearity` reads `iCVF2` from the method code.
- `pickMethodHyperParamsWithInnerCV` calls `doCVedModelFit` with
  `CVFoldInds=None` and those two folds.
- `doCVedModelFit` uses unshuffled `genCVFoldInds`: a ceiling-sized first
  selection block, then the tail. The separate `prepare_fold_inds` floor-tail
  helper and the tutorial's rounded first fold are not substituted.
- `prepareTrainingAndTestData` learns transformations on training rows only.
  `learnScaling` uses masked-array mean and sample standard deviation
  (`ddof=1`). A z-score request also removes the mean. Constant channels retain
  zero standard deviation and are centered without division, exactly as in
  `applyGivenScaling`. Raw and scaled selection arrays remain separate.

The admitted component profile is finite continuous observations, no missing
markers, no discarded samples, no external input, no shared train/selection
rows, and at least two training rows per fold. Unsupported inputs reject
without dropping observations. This restriction is explicit; it is not claimed
to reproduce every branch of the author's general missing-data implementation.

Outputs are operator/reference material. They are **not a participant packet**:
they contain selection behavior and do not enforce inference causality or
access isolation. The caller must keep them outside participant delivery.
The iterator allows one fold to be consumed at a time, but no full-panel memory
qualification is claimed.

The existing seven-session, 1,960-author-case and 280-candidate-case scorers are
unchanged. In particular, their historical outer-fold profile still requires
sample counts divisible by five. This inner component does not change that
rule, authenticate historical outer folds/electrodes, or invent a way to round,
discard or pad original observations.

Raw 10-ms binning, Gaussian smoothing, 50-ms downsampling, exact alignment and
boundary treatment remain unresolved. Compatible source-method references are
permitted when independently qualified; this component alone is neither a
reference fit nor a reproduction/improvement result.

The one generated check compares the emitted arrays and statistics with only
the selected, authenticated pure author functions, without importing DPAD,
TensorFlow, a data loader or any model. It also checks held-selection
perturbations, odd-length tails, sample-SD and constant channels, identity
preservation and unsupported-input refusal.

## Source and local checks

The reference is [ShanechiLab/DPAD, pinned source revision](https://github.com/ShanechiLab/DPAD/tree/41f108bc90252ced19fe3c8eda7eaff2e87c57b3)
and the [Nature Neuroscience paper](https://www.nature.com/articles/s41593-024-01731-2).
`SOURCE_BINDING.v1.json` identifies the exact code bodies and caller locations.
The component and portable controls are independently authored; they vendor no
author source code, source-derived numerical fixture, original data or model.
The portable fixture is deterministic generated arithmetic.

With NumPy installed, run `python -B test_inner_preparation.py` from this
folder. The five portable controls need neither network access nor private
files and write no output artifact. The separate private seven-control source
parity campaign passed against authenticated author helpers. The portable
file was derived afterwards and requires its own integration check; its final
bytes are not covered by that earlier execution.
