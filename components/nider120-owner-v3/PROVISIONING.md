# Provisioning the accepted Linux engine

This is an operator checklist with exact operands, not an installer or an execution selection. Reuse an already admitted target when available. Do not repeat accepted reference fits or the historical complete run merely to acknowledge them.

## Runtime distribution

The scientific candidate image is `sha256:b82e5a50cb664399e56006773c2c6be71d9024e82d35af31f4d9d4bcfcfeb0d4`, Linux ARM64, R 4.3.2/meta 7.0-0. Its existing Docker-save archive is 1,089,059,840 bytes, SHA-256 `355254a3315e1d86a03c28b61ea97a9a19f1fef96977cf7db7cb592ad176cd41`. Preserve the complete dependency artifact and all provenance bodies listed in `RUNTIME_REQUIREMENTS.json`. The archive digest is not the Docker image ID. Permission and a distribution channel for another operator must be resolved separately; none is invented here.

The historical V3 compatibility wrapper uses a distinct trusted-owner image, `sha256:2290454c56bfeb8cf7830a2d88f2b036a3781382847d60d4aa8b9b652a8d3974`. Its accepted Python/Docker/ps capability and bootstrap facts belong to that exact retained image. No owner-image save artifact or public distribution URL is selected here. The 40-file owner kit cannot substitute for the V3 host wrapper's complete source, staging, process-group and cleanup contract.

A new target must separately establish the exact images, numeric UID/GID, local socket mapping, daemon identity, runtime bytes and live candidate constraints. Do not accept a similar image or rewrite historical build facts. Do not run these owner commands directly on macOS. If using the historical host wrapper, preserve its `--init` predicate and closed-creator recovery barriers; its complete 75-role source graph, 68 staged source members and private staging operands are separate deployment requirements.

## Relocate existing provenance without rewriting it

V3 includes the accepted `relocate_build_evidence` operation in `engine/owner/admit_runtime.py`. Supply a private request with exactly these keys:

```json
{
  "schema": "nider_dependency_evidence_relocation_request_v1",
  "configuration_anchor": "/absolute/kit/engine/configuration",
  "source_anchor": "/absolute/kit/engine/runtime",
  "artifact_root": "/private/exact-expanded-dependency",
  "artifact_manifest": {"path": "/private/exact-expanded-dependency/ARTIFACT_MANIFEST.json", "bytes": 63762, "sha256": "3c63025713835469b3d95558ce995cf0b70bac6361b6933b863919fabea09784"},
  "output": "/private/new/IMAGE_EVIDENCE.local.json",
  "receipt_output": "/private/new/RELOCATION_RECEIPT.json"
}
```

On the selected Linux owner, invoke the actual admitted Python with `-B engine/owner/admit_runtime.py REQUEST_PATH EXACT_REQUEST_SHA256`. This existing command checks unchanged evidence bodies and writes new local locators; it does not load an image or prove live compatibility. Never rewrite historical lifecycle, inspection, inventory or filesystem-audit bodies.

## Admit the owner policy

Use the same entrypoint with a new request whose exact keys are `schema`, `configuration_anchor`, `source_anchor`, `image_evidence`, and `output`. The schema is `nider_portable_runtime_admission_request_v1`; `image_evidence` is the observed path/bytes/SHA-256 descriptor of the successfully relocated top document. The command requires the actual Linux ARM64 owner identity and empty Docker override environment. It writes a fresh policy; live daemon/mount checks still occur at dispatch.

Bind that exact policy, owner interpreter and lawful material paths in `LOCATIONS.template.json`. Follow the unchanged `OPERATIONS.md` setup/gateway/frozen-program/protected-assessment sequence. The private full120 reference remains separate; only candidate feedback may cross the owner boundary.

The historical V3 route selected two VM CPUs, 2.5 GiB VM plus 512 MiB host, with a 1,960-second whole outer deadline and 9,395,240,960-byte available-host-memory floor including other work/headroom. These are the historical complete-route limits, not measured new-target requirements. Its observed outer run was 34.133 seconds. Do not drop any field or case to fit capacity. Fresh target validation and any native operation need their own explicit complete selection.
