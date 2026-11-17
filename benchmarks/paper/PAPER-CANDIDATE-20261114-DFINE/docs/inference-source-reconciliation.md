# DFINE inference source reconciliation

This note records source inspection for the existing Figure 7e and Extended Data
6e–f task. Reproducing its original findings and exceeding them are separate
first-class outcomes; neither is established by this inspection. The note adds
no empirical result or benchmark readiness claim and does not change the
[improvement contract](../improvement.v1.json).

## The behavioral output must be selected explicitly

The paper's Methods, **Behaviour prediction accuracy—Motor datasets**, fits an
MLP from smoothed training factors to behavior after latent-model training. That
learned regression is then applied to the factors inferred in the test set. The
**Inference analyses with missing observations** section scores behavior at every
test timepoint, including times with missing neural observations. Figure 7e
requires separate filtering and smoothing results. See the [primary
article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11735406/).

At the registered official commit
`37d25e332753eaba49f42e91766d0db8e186aefe`,
[`DFINE.forward`](https://github.com/ShanechiLab/torchDFINE/blob/37d25e332753eaba49f42e91766d0db8e186aefe/DFINE.py#L171)
returns `a_filter` and `a_smooth`. These are the manifold factors obtained by
projecting the corresponding dynamic factors through `C`. The same method also
returns a convenience output named `behv_hat`, but that output has different
semantics:

| Configuration | Producer of `behv_hat` |
| --- | --- |
| `supervise_behv` is false | `None` |
| `supervise_behv` and `behv_from_smooth` are true | `mapper(a_smooth)` |
| `supervise_behv` is true and `behv_from_smooth` is false | `mapper(a_hat)` |

There is no `mapper(a_filter)` branch. In particular, setting
`behv_from_smooth=False` does **not** select causal dynamical filtering: `a_hat`
is the static encoder output. Using this convenience field for the filtering
curve would misidentify the output even if its matrix shape were correct.

A source-compatible future caller must use the post-training behavioral readout
with `a_filter` for filtering and `a_smooth` for smoothing. It must separately
authenticate how that readout was trained, its output dimension order, and its
frozen parameters. This statement identifies the required factor routing; it
does not establish that the currently distributed supervised mapper is the
paper's separately trained readout.

The registered
[`LDM.compute_forwards`](https://github.com/ShanechiLab/torchDFINE/blob/37d25e332753eaba49f42e91766d0db8e186aefe/modules/LDM.py#L142)
sets the Kalman gain to zero at missing observations and propagates the state
prediction. Its filtering recursion uses present and previous inputs. The
backward smoother uses future information. `DFINE.forward` computes both
outputs in one call; the mere presence of a filtered output does not enforce a
participant information boundary. A protected filtering interface still needs
to exclude future observations, dropped neural values, and evaluation behavior
from the participant's access.

## The source record narrows the session mapping

The Methods names seven Monkey I sessions from `20160622/01` through
`20160921/01`. The retained metadata for [Zenodo record
3854034](https://zenodo.org/records/3854034) contains exactly these seven Indy MAT
files in that inclusive date/session interval:

| Source file | Published bytes | Published MD5 |
| --- | ---: | --- |
| `indy_20160622_01.mat` | 908989308 | `c33d5fff31320d709d23fe445561fb6e` |
| `indy_20160624_03.mat` | 143970619 | `9aa921f0788f6ccd32a1b8808c18eabd` |
| `indy_20160627_01.mat` | 1135050817 | `de58797d649bdf2bec589c074ee991d2` |
| `indy_20160630_01.mat` | 382243800 | `197413a5339630ea926cbd22b8b43338` |
| `indy_20160915_01.mat` | 106555127 | `ef6a95c5a1a8d2126b90f5be0505e398` |
| `indy_20160916_01.mat` | 124026785 | `5587d27f46efa3c09a7f589f2addf3a9` |
| `indy_20160921_01.mat` | 109152855 | `788a0fc779bdfffa8388b1108e1d1ce5` |

The total published size is **2,909,989,311 bytes**. This is a uniquely supported
filename inference from the paper's interval and this record's inventory, not
an authenticated author analysis manifest or a claim that these files were
downloaded. The record's raw-broadband supplement links are separate assets and
are not required substitutes for its sorted-spike MAT files. The source
metadata gives `cursor_pos` in millimeters, cursor timestamps and spike times in
seconds, and `finger_pos` in centimeters with different axes. Substituting
finger coordinates directly for cursor coordinates would change the target.
The paper's velocity construction still requires an exact implementation.

## Publication-day code lineage

The complete commit history anchored at the registered revision contains three
commits: the [initial release on 11 December
2023](https://github.com/ShanechiLab/torchDFINE/commit/c278035be4b750caab6e0d2cd57e2e9a09484a15),
the [27 February 2024 commit labeled "bug fix in
repeat"](https://github.com/ShanechiLab/torchDFINE/commit/48a981259a795c3d1725a348c81a1552093724ac),
and the registered 18 August 2026 tutorial update. Both endpoint recursive
trees are complete and contain the same 17 file paths.

The publication-day and registered trees give identical Git blob identities
for `modules/LDM.py` (`1c5df19717b9002ff3e2a87db15f0295c5a1d52a`) and
`time_series_utils.py` (`c9fe46a0a625d1ba3e7f52bf035ca8b14f7bc3e8`). The
retained file bytes also match those Git blob identities. This establishes
release-to-release identity of the inspected filtering/smoothing and metric
implementations. It does not establish which caller produced the paper's
curves, its inputs, or its numerical results.

Six files differ between those trees: `DFINE.py`, `config_dfine.py`,
`datasets.py`, `modules/MLP.py`, `trainers/TrainerDFINE.py` and
`tutorial.ipynb`. Their historical content differences are not asserted here.
Retrieving the initial `DFINE.py` body through the raw-content endpoint failed
during TLS negotiation; the subsequent official API blob request returned a
rate-limit response. No source patch was recovered, and no native equivalence
test was run. A commit message alone does not define the scope or scientific
effect of its fix.

## What the inspected source does not recover

The complete recursive trees at both inspected commits contain a Swiss-roll
tutorial, model modules, trainers and utility code. Neither contains an
identified grid-reaching experiment driver, its fold/session manifest, a
missingness-mask export, or the numerical Figure 7e/Extended Data 6e–f curves.
The recovered article JATS lists supplementary-information and reporting-summary
PDFs, with no separately linked numerical source-data spreadsheet. Those PDFs
were not downloaded in this inspection. The separate
[correction note](correction-status.md) resolves only the scope of the 2025
publication-license correction.

No authentic MAT arrays, targets, trained weights or predictions were read for
this inspection. No author model, candidate model, fitting or numerical test
was run. The existing scorer remains a generated-control mathematical
component. Full ratio and mask identities, 100-step block alignment and tail
handling, top-neuron selection, ordered folds, preprocessing, readout selection,
native caller parity and original numeric curves remain unresolved. An
additional generic wrapper cannot supply those scientific identities.

The retained source evidence hashes are recorded in
[the source evidence inventory](inference-source-evidence.json). They identify
the inspected public-source bytes; they do not authenticate an empirical run.
