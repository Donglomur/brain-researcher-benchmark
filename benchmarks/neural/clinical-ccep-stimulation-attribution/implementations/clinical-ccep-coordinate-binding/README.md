# CCEP endpoint admission and unresolved coordinate binding

This component supports the prospective NEURAL task `clinical-ccep-stimulation-attribution`. It does not change the task, its five-patient support, four classes, metric or split.

`coordinate_gate.validate_endpoints(electrodes, stimulation_pairs)` validates the complete supplied pair list against original electrode rows. It reproduces the retained author helper’s ASCII-hyphen normalization and exact case-sensitive matching, then adds explicit admission checks: globally unique raw and normalized contact names, two distinct uniquely matched endpoints, and six finite selected coordinate values. It preserves pair order, repeated observations and reversed pairs. It returns endpoint row references and normalized identifiers, without computing a midpoint or returning coordinates or labels.

The helper is deliberately stricter than the author’s unchecked mean of matched rows. A failure rejects the supplied input; it does not silently drop observations or classify unknown anatomy. Unselected contacts may retain missing coordinates. Input authenticity and full study/census coverage remain caller obligations; validation of a supplied list does not authenticate its completeness.

The endpoint function is a pure, bounded, standard-library operation with no file or network access. Its only selected execution is the generated test suite. It has not been run against native electrode or stimulation rows.

## Coordinate and version holds

The authenticated default sidecars all declare millimetres, but their frames differ:

| Subject | Default frame declaration | Literal IntendedFor inventory check |
| --- | --- | --- |
| 1 | ACPC using VISTASOFT | Named ACPC T1 path exists |
| 2 | Native T1 scanner frame | Named path absent; a ses-mri01 filename is only a candidate |
| 3 | Native T1 scanner frame | Named T1 path exists |
| 4 | Native T1 scanner frame | Named T1 path exists |
| 5 | Native space | Named path absent; a ses-mri01 filename is only a candidate |

No filenames are automatically aliased. A matching path, shared NIfTI header, or millimetre unit does not establish physical electrode-to-atlas registration. Separate ACPC tables for subjects 2–4 are not the default tables selected by the author’s localization code.

The executed VISTASOFT version and `readFileNifti` backend are unpinned. The inspected mutable upstream `niftiRead` wrapper delegates NIfTI-1 reading; it does not establish the backend’s qform/sform selection, axis orientation or MATLAB index-origin treatment. This component therefore supplies no affine/index conversion and makes no known-affine numerical parity claim. It must not insert or omit a +1 by assumption.

The original source computes midpoint Destrieux anatomy and documents a manual subject-1 `LA1-LA2` correction to `Left_Amygdala` after visual CT/T1 inspection. That correction is retained as documentary provenance, not applied by this gate. Completeness of the override inventory and original corrected outputs remain unverified. The exact 3 mm stencil, branch thresholds and ordered name lookup remain unchanged and unexecuted.

## Evidence and remaining work

[provenance.json](provenance.json) records the five default frame/path findings, exact source identities and unresolved semantics without machine-specific evidence paths. Name normalization and pair matching follow the author repository at revision `b83e2c6b75f548848eca546566f86bef909257ca`: [readtableRmHyphens.m](https://github.com/hharveygit/VTCBPC_JNS_Manu/blob/b83e2c6b75f548848eca546566f86bef909257ca/external/mnl_ieegBasics-20230417/utilities/readtableRmHyphens.m) and [ieeg_getPairXyzs.m](https://github.com/hharveygit/VTCBPC_JNS_Manu/blob/b83e2c6b75f548848eca546566f86bef909257ca/external/mnl_ieegBasics-20230417/functions/ieeg_getPairXyzs.m). [assignStimDestrieux.m](https://github.com/hharveygit/VTCBPC_JNS_Manu/blob/b83e2c6b75f548848eca546566f86bef909257ca/assignStimDestrieux.m) selects the default coordinate tables; [the localization helper](https://github.com/hharveygit/VTCBPC_JNS_Manu/blob/b83e2c6b75f548848eca546566f86bef909257ca/external/mnl_ieegBasics-20230417/functions/ieeg_getLabelXyzDestrieux.m) and [main.m](https://github.com/hharveygit/VTCBPC_JNS_Manu/blob/b83e2c6b75f548848eca546566f86bef909257ca/main.m) document the original localization and correction context. Dataset identities are [OpenNeuro ds004457 version1.0.2](https://doi.org/10.18112/openneuro.ds004457.v1.0.2), Git commit `1bbd3a0696c56b7dfd87020bc61092644a702d0a` and root tree `f9c83bd55ce96fdb3ab0976a7b2f213ac959b7ad`. This is a portable summary of prior metadata findings, not new source qualification.

Native midpoint/label construction requires an authenticated reader/index convention and per-subject frame binding. Four-class collapse and mixed/unknown handling, waveform packets, all-channel CAR, highpass lineage, calibration and protected evaluation remain unresolved. Passing endpoint validation never establishes scientific readiness.

## Generated controls

From the repository root, run the unchanged standard-library test entrypoint with Python 3.11:

```sh
python3.11 -I -S -B benchmarks/neural/clinical-ccep-stimulation-attribution/implementations/clinical-ccep-coordinate-binding/test_coordinate_gate.py
```

The existing suite has 27 generated tests and pins the sibling `coordinate_gate.py` by its byte count and SHA256. The prior 27-test run passed; this documentation-only revision does not rerun it. CI should fail on a nonzero exit and preserve the output. No installations, authentic inputs, network access or scientific qualification are part of this recipe.
