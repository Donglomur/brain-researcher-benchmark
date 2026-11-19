# Typed partial-layout continuation

The full-census package can import an explicitly selected, authenticated subset of saved **layout metadata** and inspect a finite number of remaining planes. This applies only to the `layouts` stage. It preserves the original cohort of 107 mice, 703 sessions and 1,936 planes and the 73/15/19 mouse split. It does not project neural values, run a predictor, or change the forecasting target.

A directory of old outputs is insufficient. The selected operation profile must contain the exact `partial_layouts` fields: pinned seed manifest and census report, seed count and body bytes, maximum new-plane count, seed-read allowance and provenance allowance. The entrypoint also requires `--partial-layouts` and `--partial-root` together. The repository's example profiles remain disabled proposals; this source change selects no authentic-data invocation.

## Admission and custody

Before constructing the provider/range budget, the entrypoint authenticates the seed manifest and report against their pinned sizes and SHA256 digests. It binds the complete inventory and asset snapshot, then verifies every selected seed's bytes, schema, experiment identity and canonical asset identity. A malformed final seed refuses the entire import before provider access. An imported layout does not bypass identity checks because another layout was accepted.

Successful admission copies the exact authenticated bytes into fresh owned output files, seals them read-only through the real file descriptor, and records explicit copy provenance. Original seed files are not overwritten or made writable. Host-specific staging, caller authentication, container mounts and activation are separate operator responsibilities; they are not scientific dependencies published by this package.

The continuation schedules only unseeded experiment IDs in the unchanged canonical inventory order, up to the selected `max_new_planes`. Imported seeds generate zero new provider requests. Historical request and body totals remain historical evidence and are not inserted into the new range ledger. Failed new work remains failed, with explicit unattempted tail dispositions and retained charged artifacts.

## Two different completion fields

A bounded step can finish its selected new-plane allowance while the cohort remains incomplete. Its process can return success for that finite step, but the report still has `complete: false`, `cohort_status: "held_incomplete"`, and no complete layout bank. Callers must inspect `bounded_step_complete` and full-cohort completion separately. The package emits a complete layout bank only when all 1,936 original planes are covered. A partial layout set cannot stand in for the complete predecessor bank required by `metadata_support` or `chunks`.

Saved layout coverage is structural evidence. It does not establish valid event support, a physical chunk census, finite dF/F values, decoding equivalence, model performance, direct neural understanding, or benchmark readiness.

## Public generated controls

The public entry in `tests/test_partial_resume.py` selects 53 named generated controls: 23 artifact/sealing controls, 21 admission controls, six continuation controls and three entrypoint controls. They preserve the portable semantic cases from a 69-control private construction campaign. Eight host-verifier and eight host-staging/path controls are outside this public entry; they are not silently skipped or counted among its 53 controls.

These controls use generated metadata and dependency/runtime oracles. They exercise actual owned-file sealing where declared, but do not acquire original data or qualify native library, container or provider execution. The public command uses the maintained exact JSON-controls result interface with zero skipped controls. It is enrolled separately from the existing six full-census generated tests.

The public entry is authored and statically reviewed at this source cutoff. Its fresh hosted execution must be assessed from the exact commit's CI result; the private 69-control result is not a hosted result for this 53-control entry. No local public-control replay or authentic/model run is claimed by this documentation.
