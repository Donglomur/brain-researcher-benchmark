# Participant delivery for the fixed Indy transfer

This component recovers the eleven exact public source files listed in the
historical delivery manifest and exports them together with the four pinned
public inputs. The recovered `packet_io.py` provides complete-support loading;
`reference_core.py` and `REFERENCE_PROTOCOL.json` provide the unchanged seven
reference recipes, including chronological folds, ten-bin histories and
equal-day pooled weighting. Recovery does not refit them.

The source files are byte-identical to their historical manifest entries.
`SOURCE_PINS.json` records each identity. Historical documents are retained
verbatim: their old execution-service descriptions are not current availability
claims. The generated participant README explains the current route.

Run with existing public inputs and an external output directory:

```sh
python3 export_public.py --inputs /absolute/public-inputs --output /absolute/new-delivery
```

The exporter uses Python's standard library. It opens only `source.npz`,
`calibration.npz`, `assessment.npz` and `manifest.json` from the input directory;
extra files are never traversed or copied. Their fixed hashes cannot be
overridden through the CLI. It verifies all four bytestrings and the recovered
source files before creating output. It then writes a fresh `public/` directory
with read-only files and a final `receipt.json`, verifies the written file hashes,
and records no machine-local paths. On a write failure the new directory may
remain incomplete: only a matching final receipt marks successful export.
File modes are an operator convention, not a sandbox or access-control proof.

Mount only the resulting `public/` directory for a numerical participant. The
directory preserves 18,691 source labels, 2,991 calibration labels and all
22,091 target-free assessment endpoint IDs. `endpoint_bin` becomes submission
`case_id`; the output velocity axes are x/y in m/s and refer to the trailing
20 ms interval. Do not reinterpret endpoint IDs as count-row offsets: assessment
counts have origin 3000, and the first prediction at endpoint 3010 uses rows
0 through 9. The fixed source/reference recipe uses past bins, while this
full-batch delivery permits later assessment counts to be inspected.

The existing `registered-runtime/external-artifact-v1` component separately
scores completed prediction files with operator-only assets. Neither exporter
nor public input adapter provides frozen-program execution isolation, direct
interpretation, a typed viewer, or tool-controller qualification. The full ridge
panel performs 51 fits and requires a separately allocated scientific run; it
is not part of delivery verification. No dependencies are installed here.

The panel remains one exposed Indy day pair. It does not cover other sessions
or Loco. Its assessment counts expose NEURAL-024's future-neural targets; never
combine the mounts or claim NEURAL-024 hidden after prior NEURAL-023 access.

Original data: [O'Doherty et al.](https://doi.org/10.1088/1741-2552/aa9e95),
[Zenodo 3854034](https://doi.org/10.5281/zenodo.3854034), CC-BY-4.0. Dataset
bodies, targets, predictions and historical numerical results stay outside Git.
