# Paired pretest authoring materials

`prepare_authoring_views.py` prepares both access-condition development views
from the selected full-panel pair. It reuses the accepted
`FullPanelAPI.prepare_development_view` once per condition and writes
`AUTHORING_HANDOFF.json` only after both exact development manifests match.
It does not start an authoring process, train a model, release an inference
view, or score a submission.

The views retain the admitted TRAIN/VALID arrays, validation targets and
permitted behavior. They exclude only
`inputs/mc_maze/test/eval_input_20ms.h5`, the supplied TEST held-in panel.
The distinct file `inputs/mc_maze/test/train_input_20ms.h5` is training data
and remains available. `paper_data_author_code_and_weights` additionally
contains the fixed official source and ten allowlisted opaque assets;
`paper_data` does not.

## Trusted operator preparation

Use a checkout containing this component and the already authenticated pair
identified by `MATERIAL_BINDING.json`. The selected pair SHA256 is
`c4ae0e6509fc74bd68561b0031aae38bf74a08c5f053718bd9349effd9720b22`.
The script accepts a trusted operator JSON request with exactly these fields:

```json
{
  "repository_root": "/absolute/path/to/checkout",
  "component_root": "/absolute/path/to/checkout/benchmarks/paper/PAPER-SMC-RNN-2024/implementations/full-panel-improvement-v1",
  "pair_path": "/absolute/path/to/accepted-materials/pair_manifest.json",
  "output": "/absolute/path/to/fresh-pretest-views",
  "max_bytes": 33554432,
  "reserve_bytes": 42949672960
}
```

Paths above are placeholders. The output parent must exist; the output itself
must be fresh, outside Git and the original pair, and have no symlink ancestors.
The complete material cap is fixed at 32 MiB. `reserve_bytes` is an explicit
nonnegative disk reserve; the example uses the construction run's 40 GiB floor.
Select and account for the operation's resources before reading original
materials. This command does not supply a native resource controller.

```sh
python3 -I -B \
  "$REPOSITORY_ROOT/benchmarks/paper/PAPER-SMC-RNN-2024/implementations/full-panel-improvement-v1/prepare_authoring_views.py" \
  --request "$AUTHORING_REQUEST"
```

The retained exporter requires its scientific Python dependencies for array
admission; a source-only CI environment does not qualify original-data execution.
The trusted operator authenticates the complete accepted pair, including the
unlabelled TEST input, while constructing views that exclude that input.
Never expose the original pair or its parent to the authoring process.

The output contains one directory per condition and the paired handoff. Each
condition directory has `development_manifest.json`. The handoff records both
manifest identities and extents; the outer output directory is operator
metadata, not a shared authoring root. A failed second view leaves a completed
first view and no successful paired handoff. The output remains claimed: do not
retry into it or discard the failure. The existing exporter owns cleanup of
its transient staging directory.

## Transition to a controlled authoring episode

Directory preparation is not process isolation. Give each controlled authoring
process or tool session access only to its matching authenticated development
root and a separate fresh work/output root. Do not expose the opposite
condition, original pair, protected targets, TEST behavior/future observations,
or score feedback. Select one explicit matched authoring/development resource
policy for the two conditions and retain actual cumulative usage and custody
records. The later inference execution profile does not measure earlier work.

After observing owned authoring closure, use the existing `freeze-method`
interface in [Operations](OPERATIONS.md) to snapshot each program and selected
artifacts. Its plan binds the seed, full adaptation/cross-trial procedure,
program hash and permitted behavior/official-asset actions. Authenticate both
frozen methods before either TEST-input release. The existing
`FullPanelEpisode` performs this paired ordering for its method inputs.

After that boundary, the frozen method may actually adapt to the complete
574-trial by 35-bin by 137-held-in-neuron supplied panel. Program freeze is not
parameter freeze. The endpoint remains original 20-ms MC_Maze with ten unseen
future bins, all four metrics (`co-bps`, `vel R2`, `psth R2`, `fp-bps`) and the
retained SMC/LFADS/NDT references. The reproduction and stricter conditions are
unchanged. Report fixed-panel transductive results, without an inductive or
5-ms leaderboard claim.

## Observed construction and source controls

One selected local material operation completed on 2026-11-19: 68 view files /
30,383,017 bytes plus a 2,204-byte handoff, totaling 69 files / 30,385,221 bytes.
The exporter exited 0 in 5.642 seconds (5.747620 seconds including caller
capture). Both expected manifest hashes matched. Saved evidence records known
process/group closure, a free native lease and no remaining temporary stages.
A separate saved-result review accepted the metadata and stat inventory without
replaying payload reads. [Material evidence](AUTHORING_MATERIAL_EVIDENCE.json)
contains the portable result summary and evidence identities; the actual data
and private operator records are not published here.

Six generated-fixture controls cover allowed TRAIN/VALID retention and access
differences, early capacity/path refusal, partial-failure preservation, changed
manifest refusal and changed exporter-source refusal. They use the real accepted
view-copy path with original-pair admission mocked. Run them from the checkout:

```sh
python3 -I -B \
  benchmarks/paper/PAPER-SMC-RNN-2024/implementations/full-panel-improvement-v1/test_authoring_views.py
```

The adjacent accepted fixture helper and component are the default. Explicit
`SMC_FULL_PANEL_CONTRACT_ROOT` and `SMC_FULL_PANEL_REPOSITORY_ROOT` overrides are
available for source-only operator projections. The existing component-wide CI
discovery command includes these six controls; do not count a second duplicate
command. [Control evidence](AUTHORING_CONTROL_EVIDENCE.json) distinguishes prior
accepted controls, their retained fixture/assertion failures and the portability
check. None of these results establishes actual authoring isolation, historical
blindness, authoring resource measurement, model/runtime qualification, an AI
result or scientific improvement.
