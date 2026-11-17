# Original Figure 3 inference and provided-result verification

This additive component completes the inferential operations omitted by the
earlier source reducer. It reuses the unchanged original Figure3 reductions and
the reviewed original-input population-weight join. It adds the exact nine
Figure3b permutation contrasts and the Figure3c exponential parameters,
covariance and100-point fitted curve. No benchmark ID, improvement rule or
scientific qualification is added.

`load_author_panel` authenticates the original `analysis.zip` and all224 selected
author result members, then decodes them directly into the existing full panel.
No archive extraction or extra array copy on disk is needed. The224 NPY members
total6,339,760 bytes; the complete logical checksum/member/EOF admission charge
is24,856,518 bytes. File names alone do not authenticate an execution: these are
**provided author results**, not new predictions or independent AI reproduction.

`complete_summary` preserves the fixed Figure3b layer5 and time indices17–19,
within-session time means, equal14-session aggregation and complete lexical/
shuffle distributions. Figure3c retains its separate original group-selected
layer per context length. Figure3d keeps both33-layer controls. Figure3e retains
the weighted/unweighted population and unit maps, with weights recovered from
the separate authenticated word-aligned files. The579-versus567 Figure3f unit
join remains separately unresolved; it does not block these declared outputs.

The exact Figure3b schedule is six directed model comparisons with seed46:
contextual>syn, contextual>word2vec, contextual>sem_syn, syn>word2vec,
syn>sem_syn and word2vec>sem_syn; then each of syn, word2vec and sem_syn against
its own shuffle with seed20. Each test uses100,000 draws. Each contrast resets a
legacy MT19937 generator and each draw freshly concatenates the original two
arrays before shuffling. Ties count with`>=`; there is no add-one correction.
A private RandomState reproduces the seeded shuffle sequence without modifying
the caller's global RNG. Plotting jitter is not an endpoint.

These source tests flatten14 sessions by3 time bins into42 observations per arm.
They do not become42 independent people. There is no new pairing/sign-flip
scheme, cluster correction, multiplicity correction or contextual/time-shuffle
contrast. This is an explicit reproduction of the source procedure, not a new
validation of its assumptions. Nonfinite observations remain visible and their
contrasts are not tested: the literal source helper can return zero when its
observed difference is NaN, and that behavior is not accepted as significance.
No rows are dropped to make a comparison computable.

The Figure3c fit is exactly`curve_fit(a*exp(b*x)+c, [1,3,5,7,10], means,
p0=(-8,-0.08,0.08))` using SciPy defaults and the five unweighted selected means.
Parameters, covariance, warnings and the source100-point grid are retained.
Fit failures do not trigger retries, solver changes or a favorable subset.
Nonfinite covariance entries are explicit nulls with a finite-value mask.
The numerical versions must match the caller's declared runtime; this is not
proof of the original Python/NumPy/SciPy environment.

The performance endpoints remain the source prediction-score means and paired
candidate/reference deltas. A smaller p-value is never an improvement condition.
No p-value, fitted parameter or supplied author result grants a scientific win.

The complete original-release path requires float64 arrays and refuses implicit
precision conversion. The primitive permutation helper separately supports both
float32 and float64 for engineering comparisons. The supplied author metadata
names NumPy 1.24.3 and SciPy 1.10.1; generated tests in a declared current runtime
do not establish historical numerical parity.

The CLI combines the complete author panel with a hash-bound original input
preparation receipt. It checks all 196 member identities, 14 sessions, three
source archives, prepared-array shapes, original weight geometry and complete
read accounting. It reads only a bounded, stable ordinary file and rejects
duplicate JSON keys. The hash binds a separately trusted operator receipt; it
cannot independently prove execution or establish custody. It requires explicit
read, working-memory, permutation and
output allocations. The original input component and reducer dependencies are
hash-checked before use. A real reference-verification invocation requires its
own reviewed protocol after source acquisition and preparation; construction
does not execute it automatically.

```sh
python3 -I -B test_inference.py -v
```

The 23 generated controls include the actual 900,000-draw schedule, comparison to
the original helper at another100,000 draws, both source seeds/precisions, the
literal source exponential function and covariance, undefined-input/failure
behavior, a complete 224-member generated ZIP read without extraction, and
complete-receipt, float64, FIFO, symlink, extent, identity and JSON controls.
These are synthetic statistical controls, with no authentic result arrays,
neural model fits or AI attempts. The tiny attributed helper fixture preserves
the original three function bodies; trailing whitespace is stripped. Source:
Jing Cai, Sydney Cash and Ziv Williams, [Zenodo20128462](https://zenodo.org/records/20128462),
Figure3 notebook cells8/14, licensed [CC BY4.0](https://creativecommons.org/licenses/by/4.0/).
