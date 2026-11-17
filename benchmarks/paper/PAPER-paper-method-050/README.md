# Density-based longitudinal neuron tracking in high-density electrophysiological recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-050`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 29754 bytes; SHA-256 `fcd65edd8550ca28997a59ad5199df24179aea1c304ad4140177ba1d45b707d3`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Converts pinned spikeInfo HDF5 references into numeric arrays and computes paired full-population tracking-yield/PETH diagnostics with complete declared unit and animal accounting. Native schema/time units, real animal grouping, UnitMatch half-waveforms, PETH exclusion from every matching path, Figure 5 day/rate/three-method comparisons, true identity labels, protected lineage and scientific qualification remain open.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1016/j.patter.2026.101590)
- [Code](https://doi.org/10.5281/zenodo.20019488)
- [Code](https://doi.org/10.6084/m9.figshare.30596258.v2)
- [Code](https://github.com/jiumao2/pyDANT)
- [Code](https://github.com/jiumao2/pyDANT/blob/96060c1dd816181f32f089aaa686801aeae821bb/pyDANT/Preprocess.py)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC13494646/)
- [Code](https://raw.githubusercontent.com/jiumao2/pyDANT/96060c1dd816181f32f089aaa686801aeae821bb/LICENSE)
- [Code](https://raw.githubusercontent.com/jiumao2/pyDANT/96060c1dd816181f32f089aaa686801aeae821bb/README.md)
- [Paper](https://doi.org/10.1016/j.patter.2026.101590)
- [Source](https://zenodo.org/records/20019488)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
