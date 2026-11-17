# Local image preparation for the PFC task

This optional adapter materializes the same single PFC task as `materialize.py`.
It accepts complete local Docker image configuration IDs for the two Dockerfile
`FROM` operands. The existing repository-plus-manifest-digest mode is unchanged.
Neither mode proves image contents, platform compatibility, availability or a
successful benchmark run. The task's 69 cases and 12 families are unchanged.

Use Python 3.11 or later. Keep these files beside the existing `materialize.py`,
`SOURCE_MANIFEST.json` and `task/` tree. The adapter authenticates the exact base
materializer and the existing source/asset manifest. It performs no download,
Docker call, package installation, native numerical execution or model request.

Prepare an ordinary, non-symlink release directory containing exactly the four
released assets, four notices and `PUBLIC_ASSET_MANIFEST.json`. The additional
manifest is authenticated but excluded from the eight-file staging directory.
Use the release associated with this component; see its existing README for
provenance, access and rights. The adapter does not grant redistribution rights.

The request JSON must contain exactly these fields:

| Field | Value |
| --- | --- |
| `schema` | `PFC_SCIENCE2_LOCAL_CONFIG_MATERIALIZE_V1` |
| `execution_selected` | Boolean `true` after selecting the operation |
| `release_root` | Absolute existing nine-file release directory |
| `asset_stage` | Absolute nonexistent staging directory with existing parent |
| `output_root` | Absolute nonexistent path ending in `tasks/life-sciences/neuroscience/pfc-conditional-reconstruction`, with existing parent |
| `agent_image_id` | Exact `sha256:` followed by 64 lowercase hexadecimal characters, for the participant Dockerfile base |
| `verifier_image_id` | Same syntax, for the verifier Dockerfile base |

The release, staging and task directories must be pairwise disjoint and must
not overlap either protected source tree. Source trees may coincide or nest.
Invoke `python3 -I -S -B local_materialize.py REQUEST_PATH EXACT_BYTES SHA256`
using the exact request length and SHA-256. The operation preserves a failed
partial output; do not reuse or overwrite that directory. Successful staging
contains eight files and the generated task contains 28 files. Staged files are
read-only. The JSON receipt records content hashes and explicitly leaves native
validation, image admission and submission readiness false.

Local IDs are daemon-specific configuration identities, not registry manifest
digests. They cannot be published as portable image references. A separately
reviewed local build must establish complete agent and verifier task images
before running a harness. `bind_local_images.py` offers a pure function to add
those two distinct complete image IDs to the exact unchanged task TOML. It does
not build, admit, write or run images. Never pass the base IDs to that function
as substitutes for complete task images.

Harbor lifecycle and helper containers require their own complete review,
including platform/dependency admission, network behavior, resource bounds,
cleanup and separate oracle/negative-agent outcomes. This source addition makes
no claim that those steps have completed or that its Dockerfiles are runnable
on every builder. Public-network agent access also requires explicit treatment
of solution exposure when interpreting difficulty.

The narrow tests use invented asset bytes and the existing source tree; they do
not read the released neural packet. Set `PFC_LOCAL_FIXTURE_ROOT` to a fresh
absolute directory outside the component, then run
`python3 -I -S -B test_local_materialize.py`. Fixtures are retained for review.
These controls check local-ID syntax, complete staging, input failures, protected
source ancestry, preservation of registry mode and exact two-field TOML overlay.
They establish construction behavior, not scientific or model performance.
