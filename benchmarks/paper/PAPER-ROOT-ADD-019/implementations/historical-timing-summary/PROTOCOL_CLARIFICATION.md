# Prospective clarification of benchmark conventions

**Public protocol revision, pending exact root adoption before empirical evaluation.** This document supplies benchmark reporting conventions that were incompletely specified in the original common public packet. They are not quotations from, or additional findings of, the paper. Original public files and previous reports remain unchanged. The same adopted text must be supplied to both access conditions before their programs are frozen or evaluated. No empirical target values are disclosed here.

For this specified reconstruction, distinguish a scientifically meaningful result from a literal source-format placeholder. An entirely NaN 242-sample latency segment has `status: "all_nan_scientific_latency_undefined"`, zero finite samples and 242 NaNs. Its literal placeholder is `segment_index1: 1` and `absolute_sample_index0: 2409`. Compute its `source_latency_ms` as one sample interval in milliseconds and its separate physical-grid diagnostic from that absolute index, using the same public formulas as other rows. Both `amplitude` and `scientific_latency_ms` are null. The placeholder is not a detected peak/trough or biological latency. Partial NaNs do not remove or renumber original positions; a defined extremum uses the first global finite maximum for DA or minimum for ACh.

Each within-rat table row retains the full number of prescribed conditions: two for volume or four for delay. `defined_conditions` counts latency rows whose status is `defined`. `source_equal_condition_mean_ms` averages all prescribed source-latency entries, including the explicitly labeled literal placeholder above; it is null if any required source-latency entry is unanswered. `scientific_equal_condition_mean_ms` averages all prescribed scientific-latency entries only when every condition is scientifically defined and answered; otherwise it is null. It does not silently change to a mean over the available subset. The matched `DA_minus_ACh_ms` is the difference of the two scientific within-rat means, or null if either is null. These fixed-support conventions distinguish incomplete/undefined support from a changed estimand; an available-case mean may be scientifically useful in a separately declared analysis but is not this field.

For the explicitly labeled modern source-pooled rank description, let `n_D` and `n_A` be the full prescribed DA and ACh vector lengths, `N=n_D+n_A`, and rank the combined source-latency vectors in ascending value order with average ranks for exact ties. Let `R_D` be the DA rank sum and `U_D=R_D−n_D(n_D+1)/2`. For every ascending-value tie group, including singletons, record its size `t`. Define

```
mu = n_D*n_A/2
V = n_D*n_A/12 * ((N+1) - sum(t**3-t)/(N*(N-1)))
d = U_D-mu
z = sign(d)*max(abs(d)-0.5, 0)/sqrt(V)
p_two_sided = erfc(abs(z)/sqrt(2))
```

Here `sign(0)=0`. `normal_variance` is `V`, and the reported z retains the DA direction. If `V` is nonpositive (including zero), retain the other well-defined quantities, use `normal_status: "undefined_zero_rank_variance"`, and set z and p to null. Do not drop unanswered vector entries and recalculate the test on a smaller pool: preserve the full vector lengths and report the affected rank quantities as unanswered. This convention does not establish historical MATLAB defaults, independent condition rows, population inference or validity of a significance claim.

Different defensible missing-data or continuity conventions are not automatically invalid scientific analyses. The existing scorer is a continuous comparison to one frozen reconstruction, not a validator of every possible estimand. Accordingly, a discrepancy confined to an ambiguously specified field must be labeled as such; it must not be used to discredit the candidate's scientific reasoning or to claim a failed independent reconstruction without the clarification and its provenance being recorded first. The full signed curves, original latency identities and support are assessed separately.


The public override wire format is also explicit in this revision. `OVERRIDES.json` has exactly `schema_version` (integer 1), `candidate_id` (`PAPER-ROOT-ADD-019`) and `members` (a list). The original case has an empty list. A supported changed-input case has one member record with exactly these fields:

```json
{
  "member": "<exact selected member name from INPUT_MANIFEST.json>",
  "file": "replacement.mat",
  "bytes": "<positive integer byte length, at most 2000000>",
  "sha256": "<64 lowercase hexadecimal characters>"
}
```

This is a schema illustration with placeholders, not a valid case or empirical value. The filename key is **`file`**; no alternative filename key is required. Resolve it relative to `/input`, require an ordinary contained relative path and verify its exact bytes and SHA256 before use. Replace precisely the named archive member, not the ZIP itself. The active `INPUT_MANIFEST.json`, declarations and public contract carry the replacement member's bytes/hash where applicable; the original ZIP pin stays unchanged. A whole member hash applies to every selected condition in that member, even when only one sample in one condition changes. All other selected members still come from the original ZIP. Do not infer the replacement file's name from an empty original override list, silently ignore an override, or require the archive checksum to change.

The admitted signal domain is real floating-point traces containing finite values and/or NaNs. Positive or negative infinity in an input trace is unsupported and must stop that reconstruction; do not drop, saturate or impute it. NaNs retain their original positions and the prescribed missingness treatment. Undefined derived averages or zero/overflow correlation energy retain their separate declared statuses; the absence of input infinities does not imply every derived quantity is scientifically defined.
