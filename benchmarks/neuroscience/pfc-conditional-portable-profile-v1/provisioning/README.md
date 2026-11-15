# PFC exact-packet provisioning plan

For current availability and setup, see [PROVISIONING.md](../PROVISIONING.md). The plan below records the source-stage design; pending labels describe that stage. Versioned DANDI notices are recorded in [DANDI_VERSION_NOTICES.md](DANDI_VERSION_NOTICES.md).

The minimal route is to release the already accepted 5,368,996-byte participant packet with its attribution and public provenance identities, after a complete content audit. Reuse the accepted fixed map and UUID mapping. Rebuilding the published preprocessing and refitting a new map is unnecessary for this conditional benchmark and would not guarantee the same packet.

This source package supplies the missing content auditor and a small metadata materializer. It does not download, copy, publish or reopen an authentic scientific input. It does not change the existing benchmark, score, participant programs, reference or runtime. Publication and the exact authentic audit are not performed by authoring this package.

## What the provenance establishes

Zenodo record 17559037 identifies the published intermediate dataset and frozen official source. Its saved primary metadata declares open access and CC BY 4.0. The four admitted data-file names, sizes and MD5 identifiers match the existing preparation lineage. The selected official source has a separate BSD-2-Clause notice, which must remain intact. See ATTRIBUTION.md.

PUBLIC_LINEAGE.json contains only the nine prepared roles, their byte counts and SHA-256 identities, the exact packet identity, public upstream identifiers and a description of the transformations. It contains no original absolute paths, private execution selection, array values or hidden answers. It is deliberately distinct from the private historical preparation manifest.

The first three roles preserve complete source lineage, explicit recording-to-animal joins and eligibility. The join was derived from public DANDI metadata: 25 recording assets in 000473/0.230417.1502 and 74 in 001260/0.250911.0744. It uses explicit Session and Participant identifiers, not animal inference from recording names. The original authoring binder generated unit IDs with uuid.uuid4(); their saved mapping is therefore part of the exact packet identity. Record and animal IDs are deterministic SHA-256 encodings. Neither convention is a guarantee of anonymization.

The saved seed-zero original-method run supplies fitting order, map categories and two ROI encodings. Its historical statistics authenticate axes/count support and select fixed context rows. Numerical historical null means and standard deviations go only to the separate owner diagnostic, not to the participant packet. The packet retains an owner-derived report byte count/digest and declared historical status counts; these provenance identifiers are explicit and are not numerical reference answers. Do not strip them silently, because that changes the accepted packet.

## Complete content audit, selected separately

Freeze this source and run exactly one audit against the accepted packet, with no network and no output data copy:

```sh
"$PFC_PYTHON" -I -S -B "$PFC_PROVISIONING/audit_packet_release.py" \
  --packet "/absolute/authorized/participant-packet.json"
```

PFC_PYTHON and PFC_PROVISIONING are operator-selected canonical paths. The auditor reads exactly the fixed-size packet plus one EOF check and verifies SHA-256 before JSON parsing. It rejects duplicate/nonfinite JSON, undeclared top-level or nested fields, nonopaque identifier formats, incomplete rosters or joins, incompatible family/context coordinates, private report paths and unexpected historical metadata/prose. It checks all 19,186 units, 99 records, 68 fitting animals, twelve families and sixteen contexts. It emits only a small metadata result. Its label-character whitelist is a release boundary in addition to the established scientific schema; a refusal requires examining the exact cause, never dropping rows or quietly editing the packet.

Prospective one-audit envelope: 1 CPU, 256 MiB planning memory, 30 CPU seconds, 45 seconds whole wall time, 64 MiB managed read allocation including source/metadata and complete JSON parsing, 1 MiB receipt retention. Actual memory and duration remain unobserved. Use the existing owned-command/capture mechanism; no new owner framework is needed. Preserve the complete result and any refusal. A positive content audit is not a legal opinion, public upload, benchmark rerun or stronger scientific claim.

## Owner-local provenance without exporting private authority

The current public deployment accepts a caller-pinned lineage descriptor. It checks the schema, all nine role names, their declared descriptors and total 22,183,624 bytes; it does not follow the nine scientific paths or require the old private manifest's byte hash. This permits a smaller honest provenance descriptor without changing the runtime.

After source adoption, create a fresh owner-local metadata file:

```sh
"$PFC_PYTHON" -I -S -B "$PFC_PROVISIONING/make_owner_provenance.py" \
  --output "/absolute/owner/pfc-provenance.json" \
  --locator-root "/absolute/owner/pfc-provenance-identities"
```

The output parent must exist. The locator root and its nine `.identity-only` paths need not exist; they are explicitly inert identity labels, not assertions that the scientific files were copied or are available there. The helper follows none of them and writes only one fresh metadata file. It prints the exact output descriptor to use as `assets.source_input_selection` in the existing deployment configuration. The role bytes/digests come unchanged from the pinned public lineage manifest. The selected packet hash remains the existing scientific identity.

This generated file has no preparation readers, execution authority or hidden source paths. Do not give it to the original prepare_packet.py or advertise it as a complete upstream preparation recipe. It cannot rebuild a missing packet. The source phase tested the current unmodified deployment metadata function against the materializer and confirmed that the nine paths are not opened; this is metadata compatibility evidence, not a new complete Docker run.

## Finishing the public release

The root owner should retain the content-audit result, bind applicable upstream attribution/terms, and select the exact packet as a public input asset. Publish it through the chosen data-release channel with its fixed SHA-256 and length; do not copy the original owner manifest, private diagnostics, evaluator reports or hidden reference JSONL. The selected article XML, official method and complete license also need their already pinned identities and notices. A release location and checksum command can then replace the current owner-provided-asset placeholder.

Preserve the current benchmark's information conditions: both participants receive the same packet, article, task and method specification; only B receives the official method source and license. The public source distribution is not evidence that model training never encountered these materials. The exact packet was a declared participant input in the accepted local run, not a newly selected subset.

The current image still needs a reproducible, licensed distribution/build route for another evaluator. This data-provisioning package does not supply or authenticate an image export. Existing local validation remains valid; a later supported-host run uses fresh runtime admission. No full SOM refit, alternate published SOM, repeated acquisition, extra biological inference or paid model campaign is required to complete this exact-packet release route.
