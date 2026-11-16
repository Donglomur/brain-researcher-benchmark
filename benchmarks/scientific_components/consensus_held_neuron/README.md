# CONSENSUS held-neuron source correction

This is a portable source correction for the existing
`PAPER-CANDIDATE-20261114-CONSENSUS` task. It produces corrected source files;
it does not fit the model or qualify a reproduction of Figure 2b.

The owned applicator is byte-identical to the independently reviewed correction.
Its inputs are three exact files from
[v1lm_nn](https://github.com/marineschimel/v1lm_nn) revision
`eec6021e8b9f9031eb775fc1a10a07e583cf0e29`. The complete file and branch
identities are in [SOURCE_INPUTS.json](SOURCE_INPUTS.json). Obtain those originals
in an external owner-controlled source tree. No upstream code, rendered source,
neural arrays, targets or original experiment outputs are bundled here.

## Apply the correction

Python 3 standard library on Unix is sufficient for this source operation.
The generated interface checks use Python 3.11.6; native OCaml/Owl dependencies
are not installed or qualified by this package.

```sh
python3 -I -S -B correct_sources.py \
  --fit-source /external/v1lm_nn/examples/fit_single_animal.ml \
  --analyze-source /external/v1lm_nn/examples/analyze_fitted_model.ml \
  --analysis-source /external/v1lm_nn/lib/analysis.ml \
  --output /external/fresh-corrected-source
```

The output parent must exist and the output directory must be new. The tool
authenticates all three originals and their replaced spans before creating
output. It writes the two example files, `lib/analysis.ml` and a source-only
`CORRECTION_REPORT.json`. It rejects missing, changed or already-corrected
originals; it never silently applies the patch to a different revision.
Each original is limited to 128 KiB and must be an ordinary non-symlink file.
A write failure may leave a partial source tree, without a success report.
The owner is responsible for keeping originals and rendered outputs outside
public packages and for resolving upstream rights.

## What changes

The same ordered all-other-neuron list replaces the first/interior/last
branching in all three consumers. It excludes the target from recognition
observations and keeps the observed/target C, c_mask, bias and gain projections
aligned. It preserves all time rows and the one-column target slice. The shared
four latent-population scales and every byte outside the three branch spans
remain unchanged.

Under explicit-index Owl `L` semantics, the original interior list includes the
held neuron and omits other neurons. Exact historical Owl semantics and final
paper-pipeline use are not established. This corrected successor does not prove
that the published findings are invalid and is not historical parity.

## Check the portable interface

```sh
python3 -I -S -B test_portability.py
python3 -I -S -B test_correction.py
```

The first command checks the complete source manifest, relocated CLI behavior,
refusal of wrong complete preimages before output creation, and explicit
handling of absent versus incorrectly supplied owner sources. It needs no
upstream body or third-party package.

The second command runs the three unchanged invented projection checks:
all target positions, the original conditional counterexample and aligned
parameter/target noninterference over a declared seven-animal/three-fold
invented census. The other three source-application checks are explicitly
skipped unless the owner supplies the pinned source tree:

```sh
CONSENSUS_SOURCE_ROOT=/external/v1lm_nn \
  python3 -I -S -B test_correction.py OwnerSourceIntegration
```

A supplied but missing or wrong tree fails; it is not silently skipped. Skipped
owner-source integration is not a passing qualification. All six scientific
test method bodies preserve the reviewed implementations. None compiles or
executes OCaml, loads neural data or validates native Owl behavior.

The full registered endpoint remains seven animals, three folds, both recurrent
variants and the condition PSTH; the reported 246-neuron count is not forced.
Native runtime, complete input/campaign and reference binding, target isolation
across queries, full-pool historical PSTH/selection, cached order and dropped
trials remain unresolved. Complete upstream license notice/scope is also
unresolved despite the retained opam MIT declaration. This package adds no
benchmark ID and makes no readiness or scientific-result claim.
