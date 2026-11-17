# Fresh checkout: source checks, data, then qualified execution

This directory is the explicit shared-runtime source variant of the existing NEURAL-095 task. A fresh checkout can run its source controls and inspect/render its source deployment. Complete candidate execution additionally requires the exact admitted image, provisioned inputs, an operator's real current bindings and completion of the runtime qualification described in [INSTALL_RUNTIME.md](INSTALL_RUNTIME.md). The public image is not currently distributed by this package.

## Check the package without Docker or scientific data

From the repository root, using Python 3.11 or later:

```sh
cd benchmarks/neuroscience/neural-095-four-cell-runner-shared-runtime-v1
python3 -I -S -B test_configure.py
```

The existing seventeen generated controls use only the standard library. They authenticate the 55 source templates, exercise the actual closed-runtime source composition and 45/52-member owner/candidate closures, and check refusal of altered scope, unsupported images, extra environment fields, symlinked sources and malformed configuration. They do not invoke Docker, download anything, read original neural data or fit a model. The accepted scientific calibration is reused unchanged.

Do not move individual files out of `source/`; its nested `authoring/` paths are required by the original import/depth guards. Runtime source files are loaded from the rendered deployment, not from unpublished sibling repositories. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) pins those 55 templates. [RUNTIME_INSTALL_INPUTS.json](RUNTIME_INSTALL_INPUTS.json) separately pins the eleven bundled runtime-context source files; wheel/image bodies are excluded.

## Render explicit local source bindings

Copy `operator.example.json` to `operator.json` and replace every marked transport/daemon value with actual operator bindings. Preserve the fixed Linux ARM64 image ID. The deliberately incomplete example cannot execute or masquerade as an observed machine. Then choose a fresh, short deployment directory with an existing ordinary parent:

```sh
python3 -I -S -B configure.py --operator operator.json --destination /srv/dmfc
```

`/srv/dmfc` is an example, not a default. On macOS, choose an ordinary short path outside the `/tmp` symlink. Rendering writes the source tree and an unadmitted payload only; it does not probe Docker or read data. See [README.md](README.md) for the complete candidate preparation/attach/dry-run commands and [OPERATOR_ADMISSION.md](OPERATOR_ADMISSION.md) for the unchanged real-capacity and one-operation request schema.

## Provision the existing complete task

The sibling [neural-095-four-cell provisioning guide](../neural-095-four-cell/PROVISIONING.md) supplies the exact unsigned DANDI source URL, immutable recording hash and converter command. Its [publication record](../neural-095-four-cell/PUBLICATION.json) records complete remote hash verification of the three evaluator release assets on 2026-11-15. This guide reuses that record; it does not make a new live-availability claim. The public release contains development-derived reference information and is not secret-test material.

Use the unchanged sibling converter with `--out /srv/dmfc/data` for the example deployment. Preserve all 748 TRAIN trials, all 258 query trials, all 40 held-in units and four strictly pre-Set bins. Candidate mounts receive only the five public files in their relevant cue-only/neural view. Keep the original NWB, generated query targets, evaluator references and all evaluation outputs outside candidate access. The sibling's attribution and derivative notices remain applicable.

The complete task has four cells and five fixed comparators; it is one existing benchmark. The protected runner implements source/ownership protocols, while the data converter and offline scorer are separate existing components. Public source/configuration tests are not proof of neural understanding, frontier improvement, runtime containment, a protected test population or Terminal-Bench readiness.
