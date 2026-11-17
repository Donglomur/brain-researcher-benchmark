# Existing owner admission, unchanged

`configure.py` writes source and a configuration payload only. Neither its deployment record nor the candidate gate's source review is an execution grant. An operator must separately select the exact prospective operation and retain real current evidence. This document describes the unchanged schema; it supplies no fabricated observation or positive request.

The complete owner is `source/authoring/delivery-20261105/common/remaining-builds-wave40/dmfc-complete-four-cell-owner-source-20261115-v1/operation_owner.py`. Its `admit()` function is authoritative. The same relative file is copied under the deployment root. `OPERATION_PROFILE.json`, the 45-member source freeze (or exact 52-member external-candidate extension) and the complete payload must be pinned by path, byte count and SHA256. Paths refer to the deployed source, not this template package. An operator cannot reuse a historical request or refresh its timestamps to avoid a new selection.

The request has exactly these fields:

```text
schema = dmfc-complete-four-cell-root-request/v1
decision = admit_one_complete_dmfc_four_cell_operation
candidate_id = NEURAL-095
configuration_payload_sha256
source_freeze
profile
output_root
actor_contexts
runtime_identity
capacity
issued_at_unix
expires_at_unix
prior_known_seconds
family_ceiling_seconds
```

`configuration_payload_sha256` is SHA256 over sorted-key, compact UTF-8 JSON with nonfinite values forbidden, excluding only the later `request` descriptor. It is distinct from the indented payload file's SHA256. The helper/gate reports both. `source_freeze`, `profile` and `capacity` are exact `{path, bytes, sha256}` descriptors. Output path, all four actor contexts and runtime identity must equal the selected payload. The validity interval is at most one hour, and admission checks its current time. The prospective family accounting must cover all prior known cost plus the complete 4,800-second reservation.

The capacity witness has exactly these fields:

```text
schema = dmfc-complete-four-cell-capacity/v1
observed_at_unix
repository_root
output_parent
available_memory_bytes
other_disk_reserve_bytes
memory_pressure
swap_growth_bytes
pageout_growth_bytes
```

The witness must describe the actual deployed root and output parent and be at most 120 seconds old at admission. The original profile requires at least 6 GiB available memory, NORMAL pressure, no swap/pageout growth, and at least 1 GiB other disk reserve. The owner additionally checks actual current free disk against its artifact allocation plus that reserve. These are runtime observations, not constants to copy from this document. The source helper intentionally does not measure or invent them.

The operation keeps its original start clock, 4,200-second work interval plus 600-second recovery/finalization tail, 4 GiB per-cell upper bound, 900-second cell bound, 120-second preparation bound, 46-unit ceiling, token/cost reservations and complete ownership/recovery rules. No retry, shortened cohort, dropped reference, changed Docker/image binding or larger budget is silently admitted. Failure and incomplete cleanup must be preserved.

The owner probes the exact daemon and image only after valid admission. A separately recorded daemon identity supplied to the helper is a prospective expected value, not proof of current compatibility. A clean-target full positive/negative compatibility qualification still needs a separately selected bounded operation before this export can be described as portable and ready to run.
