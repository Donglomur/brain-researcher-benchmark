# N170 public status, null and documentary-field contract

Companion to the public method/output schema. No endpoint
values or historical bake/reference targets are part of this contract.

Both n170.json and run_metadata.json use schema_version n170-output-v1.
Metadata task_id is N170PROFILE-001 and complete-run status is complete.
resource_pilot is distinct and cannot pass full-cohort production validation.
Exactly the 37 literal subject IDs in the method appear, each once. Scientific
IDs/axes and keyed rows may be coherently reordered; original metadata list
order (channel records, source field lists, filter segments) retains meaning.

## Primitive/source support and trials

condition_defined is a Boolean S×2 mask in the named face/car axis, exactly
source-defined accepted count>0. Missing condition storage is an exact finite
zero waveform; it is translated to logical None and never measured. Defined
condition waveforms and their derived measurement-rebaselined difference must
pass the three frozen supnorm comparisons. No submitted difference input exists.

Every original event row is retained. Annotation event_role is
face|car|boundary|other, fixed by the source method. normalized_event_code is an
integral value or CSV blank. The type_json,latency_json,duration_json,urevent_json
cells are JSON-encoded original selected values, compared after parsing;
whitespace/object-key order is irrelevant. Missing is JSON null. Documentary
nonfinite values are tagged {"__nonfinite__":"NaN"|"Infinity"|"-Infinity"},
never nonfinite JSON numbers. Target/boundary invalid latency is a source
failed precondition, not an omitted event or an invented trial null.

Every target event has a trials.csv row, keyed original subject/event index:

- condition: face|car.
- epoch_status: ok|out_of_bounds|duplicate_target_sample|crosses_boundary.
  ok means geometric eligibility, including epochs subsequently rejected by PTP.
- rejection_reason: out_of_bounds|duplicate_target_sample|crosses_boundary|
  peak_to_peak|accepted, in that precise precedence.
- accepted: true iff rejection_reason is accepted; CSV true/false or 1/0 are
  accepted case-insensitively. All other Boolean tokens fail.
- Sample indices and all counts are exact integral real values, not Booleans;
  subject IDs remain exact literal strings, never numerically normalized.

Every geometrically eligible epoch appears exactly once in the NPZ epoch keys,
including artifact rejects. PTP values are finite/nonnegative source-bound
receipts, not inputs for recomputing trial rejection from rounded values.

## Participant statuses and null patterns

waveform_status is ok if both conditions are defined, otherwise missing_condition.

For missing_condition: amplitude_status=onset_status=missing_condition.
amp_po8_uv,onset_ms,measurement_baseline_uv,peak_selection,peak_sample_offset,
peak_time_ms,peak_uv,half_height_uv,crossing_sample_offset are all null.

For both conditions defined: amplitude_status=ok, with finite signed amp_po8_uv
and measurement_baseline_uv computed from accepted face minus car and the one
declared measurement baseline. Onset is one of:

- numerical_zero_difference: canonical numerical-resolution rule holds. Onset
  and all peak/crossing/half-height diagnostics are null. Amplitude and baseline
  remain defined from accepted replay; bypass all onset-only arithmetic.
- no_negative_peak: selected peak is nonnegative. Selected peak fields remain
  defined; onset_ms,half_height_uv,crossing_sample_offset are null.
- no_in_window_half_height_sample: chosen negative peak has no eligible
  preceding in-window half-height sample. Peak and half_height_uv are defined;
  onset_ms and crossing_sample_offset are null.
- ok: all peak/half/crossing/onset fields are defined. Crossing identity is an
  exact source sample offset; its milliseconds are a tolerance-checked receipt.

Where defined, peak_selection is deepest_local_peak|in_window_global_minimum.
Null CSV fields are empty cells, not strings null/NaN or zero placeholders.
Statuses and offsets follow one accepted-wave replay, not canonical source
peak/onset matches. Positive amplitudes and waveform-dependent onset nulls pass.

## Complete-cohort summaries

amplitude_summary and onset_summary are computed separately from unrounded
participant replay, never rounded per_subject.csv receipts. With all37 defined:
status=ok,n_expected=n_defined=37,n_missing=0,missing_subject_ids=[],df=36;
finite mean/sample_sd/standard_error and ordered two-sided95% CI. Exact constants
have sample_sd=standard_error=0, a point CI and interval_kind=constant_point;
otherwise interval_kind=student_t. No minimum across-person variance is required.

If any required participant endpoint is missing: status=incomplete_support,
correct n_defined/n_missing and exact missing_subject_ids, with mean,sample_sd,
standard_error,df,ci95 all null and interval_kind=unavailable. All37 identities
remain. No available-case estimate is substituted. Headline amp_po8_uv/
amp_po8_ci95 and onset_latency_ms/onset_ci95 are corresponding rounded summary
receipts. SD/SE are nonnegative independently of numeric tolerance.

## Required metadata fields and matching

source_files is the closed74 list keyed (subject_id,role), each record containing
subject_id,role(set|fdt),path,size_bytes,sha256. cohort is the exact literal37
list. Metadata pins are source_manifest_sha256,method_contract_sha256,
output_schema_sha256,measurement_kernel_sha256 and match private frozen authority.

source_observed.persons is a keyed subject_id list. Each record contains:
subject_id,set_path,fdt_path,literal_data_pointer,mat_layout,header_fields,
channel_labels,channel_records,event_fields,n_events,boundary_event_indices,
boundary_cut_samples,filter_segments,fdt_size_bytes,ica_field_shapes.
header_fields preserves selected original scalars; channel_records preserves
original chanlocs dictionaries; event_fields is the sorted original field-name
union. Boundary cuts include0 and pnts; ICA fields report shapes, not applied
weights. The source reader provides this public documentary view, not private
arrays/debug diagnostics or source-derived endpoint targets.

analysis_observed.persons is a keyed subject_id list. Each record contains:
subject_id,n_face_candidates,n_face_accepted,n_face_rejected,n_car_candidates,
n_car_accepted,n_car_rejected,condition_defined(face,car),rejection_counts(all
five reason keys, including zero counts),n_eligible_epochs. No amplitude or
onset source targets belong in analysis_observed.

Required documentary values bind to the independent source view: integer
counts/indices, Booleans, strings and raw list ordering exact; finite real header
values use atol=rtol=1e-9. Descriptive extra dictionary keys remain allowed.
software_versions is a nonempty dictionary of nonempty string names/values,
reported honestly but not version-fingerprint scored. warnings is a list of
strings; it need not be empty. Findings are nonempty bounded UTF-8 without
keyword, sign, specific-number or cluster-outcome gates.

An existing or newly appearing failure_report.json blocks success, regardless
of stale complete artifacts. Malformed/nonrepresentable data are failures, not
manufactured biological nulls. Positive perturbation/mutation authoring QA stays
outside production acceptance; arbitrary valid submissions need no extra
rounding or byte-cap headroom.
