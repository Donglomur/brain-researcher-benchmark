# PFC Full99 input provisioning

Download the four fixed inputs from the [PFC Full99 input release](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/pfc-full99-inputs-v1). Together they are **5,565,161 bytes (5.57 MB)**. [PUBLIC_INPUTS.json](PUBLIC_INPUTS.json) records every filename, role, length and SHA-256.

The release contains the complete participant packet, selected article XML, official method and its full BSD-2-Clause license, with attribution and versioned provenance notices. It excludes numerical reference answers, evaluator reports, private preparation authority and the container image.

## Download and verify

Choose absolute paths for this profile's source directory, a new input directory, and a private owner directory. The source directory contains this guide, `package/` and `provisioning/`.

```sh
PFC_SOURCE=/absolute/repository/benchmarks/neuroscience/pfc-conditional-portable-profile-v1
PFC_ASSETS=/absolute/pfc-inputs
PFC_OWNER_DIR=/absolute/private/pfc-owner
mkdir -p "$PFC_ASSETS" "$PFC_OWNER_DIR"
gh release download pfc-full99-inputs-v1 \
  --repo Donglomur/brain-researcher-benchmark --dir "$PFC_ASSETS"

python3 -I -S -B - "$PFC_SOURCE" "$PFC_ASSETS" <<'PFC_VERIFY'
import hashlib, json, sys
from pathlib import Path
source, assets = map(Path, sys.argv[1:])
manifest = json.loads((source / 'PUBLIC_INPUTS.json').read_text())
for entry in manifest['assets']:
    body = (assets / entry['release_name']).read_bytes()
    assert len(body) == entry['bytes'], entry['release_name']
    assert hashlib.sha256(body).hexdigest() == entry['sha256'], entry['release_name']
print('Verified all four fixed inputs.')
PFC_VERIFY

python3 -I -S -B "$PFC_SOURCE/provisioning/audit_packet_release.py" \
  --packet "$PFC_ASSETS/participant-packet.json"
```

Keep the downloaded notices with the inputs. The packet is a derived benchmark artifact under CC BY 4.0, with its transformations documented in the release notes. The article and official method retain their separate notices. See [attribution](provisioning/ATTRIBUTION.md) and [versioned DANDI notices](provisioning/DANDI_VERSION_NOTICES.md).

## Create the owner-local provenance descriptor

Generate the deployment's identity descriptor for the nine historical prepared inputs from the fixed public lineage manifest:

```sh
python3 -I -S -B "$PFC_SOURCE/provisioning/make_owner_provenance.py" \
  --output "$PFC_OWNER_DIR/input-provenance.json" \
  --locator-root "$PFC_OWNER_DIR/input-identities"
```

The command prints the path, byte count and SHA-256 to place in `assets.source_input_selection` in your deployment configuration. It writes one new metadata file and refuses to overwrite an existing file. Its nine `.identity-only` paths are inert labels; no scientific file is created, required or opened there. This descriptor is accepted by the unchanged deployment metadata interface. The original private manifest is unnecessary.

Fill the four other asset paths in [deployment.example.json](deployment.example.json) using the downloaded files and their fixed identities. Then follow the [operator guide](OPERATOR_GUIDE.md) for source, host, runtime and compatibility admission. The pinned `PUBLIC_LINEAGE.json` records the earlier source stage; its `publication_selected=false` is historical metadata, not the current availability of this release or execution authority.

## Scientific scope and information conditions

The packet contains all 19,186 fitting units, 99 recordings and 68 fitting animals, with twelve families and sixteen contexts. A complete read-only audit on 15 November 2026 verified its fixed identity and every declared field, found no protected answer fields, and made no new fit or benchmark run. Opaque identifiers do not guarantee anonymization. Declared historical status metadata and an owner-derived report digest are preserved as provenance.

The benchmark reconstructs conditional statistics for the supplied fixed map and all 68 fitting-animal deletions: 69 full/deletion cases. Its scored PFC population is separately 10,243 units from 65 animals. Reuse the saved map and UUID mapping; refitting or substituting another map changes the task. This endpoint does not establish held-animal prediction or reproduction of the entire paper.

Both conditions receive the packet, paper, task and schema. Only condition B receives `category_matching.py` and `LICENSE` inside its evaluation container. The evaluator must enforce those mounts; public discoverability and possible prior model exposure remain separate considerations.

## Runtime availability

The exact admitted image must be available on the selected local Docker daemon. Configuration and participant execution do not pull, build or export images. A reproducible image distribution/build route and fresh admission on another host remain outstanding; downloading these inputs does not establish new-host compatibility. Existing selected-host validation remains the evidence for this profile.
