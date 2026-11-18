# OPM spatial source kernel

This component fills the spatial-map arithmetic between qualified sensor covariance/lead-field operands and the existing downstream beta-envelope evaluator. It preserves both finger conditions and the supplied voxel order. It does not produce a paper-reproduction or improvement score.

The pinned [author spatial script](https://raw.githubusercontent.com/LukasRier/RierRhodes_2024_Neurodevelopmental_OPMMEG/0eb3a56af3d0e3a44b0f65c364e999f69cd4563f/index_pinky_Tstat_func.m) defines two tangential source orientations, covariance loading, an SVD-selected orientation, pseudo-T maps and minimum-voxel selection. [The broadband script](https://raw.githubusercontent.com/LukasRier/RierRhodes_2024_Neurodevelopmental_OPMMEG/0eb3a56af3d0e3a44b0f65c364e999f69cd4563f/index_pinky_peak_TFS_func.m) uses separate trial-condition covariances for own-finger and opposite-finger virtual electrodes. These were browser observations of commit-addressed source, not authenticated raw-file acquisitions. See `SOURCE.json` for exact locations and limitations.

`spatial.py` provides:

- `covariance_from_trials`: sample covariance across the complete supplied channel × sample × trial array, retaining variation between trials.
- `tangential_lead_fields`: project Cartesian fields into the two source tangent directions about the supplied mesh-vertex centroid.
- `pseudo_t_map`: evaluate every supplied voxel using its condition's covariance and both active/rest operands.
- `select_peak`: keep the first minimum in the supplied source order; return its identity, coordinate and exact tie count.
- `virtual_electrode`: apply the source weight and its Euclidean normalization, retaining sample × trial order.
- `condition_maps`: require both index and pinky inputs and retain separate maps and peaks. Scientific scores remain null.

The kernel uses NumPy only. Its arrays are already prepared operands, not original MEG files. The caller must bind the participant, sensor identities/order, cleaned trial identities/order, bandpass, active/rest sample selections, full retained voxel list, coordinate frame and upstream source provenance. `condition_maps` checks voxel identities and dimensions but does not establish their anatomical or source authenticity. No input files, arrays, or source code are opened by the kernel itself.

The primary spatial path requires the original 13–30 Hz preparation. The separate broadband extraction path has different filtering; its covariance must not be reused from the beta path. For an opposite-finger companion, keep the chosen source location but use the companion trial condition's covariance. Virtual electrodes are signed; the overall SVD sign is not a numerical-parity claim. Hilbert amplitudes and the existing downstream evaluator are sign-invariant, but this module does not perform their extraction.

Numerical policy: linear solves replace explicit inverses. Nonfinite, incompatible, non-PSD and zero-denominator inputs fail. A singular or numerically tied minimum orientation also fails; this is an explicit unresolved native-basis boundary, not a source exclusion or an automatic repair. The entire map fails if any supplied voxel is unresolved. Exact pseudo-T peak ties keep the first source voxel. Near ties and cross-platform floating-point/SVD differences still require independent native comparison.

No raw import, bad-channel selection, artifact masks, ICA, MRI segmentation, forward-model construction, outside-brain pruning, filtering, Hilbert transform, NIfTI writing, full-cohort assembly, age analysis or protected execution is performed. The original normalization-order discrepancy, pinky-window repair, original spatial/spectral result matching and same-result improvement criterion remain unresolved. Existing geometry and beta-envelope packages and canonical task contracts are unchanged.

Run the generated controls from this component directory using the existing environment:

```sh
python3.11 -B -m unittest discover -s tests -v
```

During concurrent construction, use the project's shared test pool. The 13 controls use analytic/generated inputs only: signed pseudo-T and first-minimum behavior, covariance aggregation, channel/scale invariance, condition-specific weights, tangent axes, full identity support and rejection of undefined arithmetic. They do not establish authentic-data execution, MATLAB parity or scientific success. A new integrity-enrollment row is proposed in the private handoff; public CI has not run for this component.
