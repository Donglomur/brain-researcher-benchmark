# Fixed AlexNet ReLU7 environment for NEURAL-055

This recipe targets only the existing `prepare-features` producer. It preserves
torch 1.10.1, torchvision 0.11.2, CPU float32, the exact 4,096-feature ReLU7 path,
the original image order and all scientific source. It is separate from the
NumPy-2 ingestion environment, numerical-reference environment and language-model
environment. Do not run ingestion or the campaign in this feature environment.

No download, package installation, image build, native import, checkpoint load,
image decode, model forward or benchmark execution occurred while authoring
these files. The recipe is prospective provisioning source, not an existing
image or empirical compatibility result.

## Exact producer and current compatibility prerequisite

The installed producer is
`complete_study/n055/features.py`, 19,589 bytes, SHA-256
`5e828b2aaa283e98a5dc28f59e89298d0ad4476c25ccccbb2de8b77e15cf2bd6`.
The real route is `central_entry.py prepare-features` to
`n055.central.execute`, then `n055.features.execute` and `produce`.

The selected environment uses Linux x86_64 and CPython 3.9.18. This provides
`Path.is_relative_to`, used by the actual bootstrap, and the older CPython ABI
appropriate to the fixed library generation. All 74 Python bodies in the
installed manifest parse under Python 3.9 grammar. That is not a runtime proof.
The current `central_entry.py` has two **real compatibility blockers**:
unconditional `first.add_note(...)` in source-close and captured-module cleanup
failure handling. Python 3.9 does not provide that method. The raw secondary
exceptions are already retained in `cleanup_failures` before those calls.

The lead's selected non-scientific companion `central_entry.py` is 7,671 bytes,
SHA-256 `b662f740f12426fbd9d972a53f494381c43ac6da7c5bc721a241e77f137a9b3a`.
It retains the raw secondary exceptions and makes annotation optional without
replacing the original failure. The complete source-manifest binding must include
that exact companion after independent review and root installation. This
package does not change installed bootstrap or scientific source, monkeypatch
exceptions, or claim native compatibility from static inspection.

## Concrete dependency selection

The two requirements files choose exactly eight distributions:

| Distribution | Version | Role |
|---|---|---|
| torch | 1.10.1+cpu | Required original network implementation; CPU build |
| torchvision | 0.11.2+cpu | Required original architecture and transforms |
| numpy | 1.21.6 | Explicit NumPy-1 choice for the old torch/feature path |
| Pillow | 8.4.0 | Explicit image conversion/resize dependency |
| typing_extensions | 4.7.1 | Torch runtime dependency |
| cryptography | 41.0.7 | Actual producer's independent Ed25519 qualification verification |
| cffi | 1.16.0 | Selected cryptography runtime dependency |
| pycparser | 2.21 | Selected CFFI runtime dependency |

The producer compares torch/torchvision versions after stripping local `+cpu`
suffixes; the provisioning observer checks the complete distribution/module
versions and verifies that torch was built without CUDA. No SciPy or
scikit-learn dependency is introduced. The exact remaining versions are a
prospective environment selection, not a claim about an original paper's full
environment. Actual wheel metadata and `pip check` must agree; failure is not
permission to select an unreviewed replacement version.

## Future acquisition and content locking

Perform these steps only in a separately selected, bounded provisioning phase
on Linux x86_64 with the selected CPython 3.9.18 executable. All shell variables
denote explicit ordinary absolute paths or actual observed image identities.
Use a fresh build context and a fresh `wheelhouse` directory. Copy the Dockerfile,
`feature_environment.py` and `WHEEL_ARTIFACTS.json` into that context. Keep the
exact selected `requirements-artifacts.lock` at `N055_FEATURE_RECIPE`.

```sh
"$N055_FEATURE_PYTHON" -m pip --isolated download --only-binary=:all: \
  --no-deps --no-cache-dir --no-index --require-hashes \
  --dest "$N055_FEATURE_BUILD/wheelhouse" \
  -r "$N055_FEATURE_RECIPE/requirements-artifacts.lock"
"$N055_FEATURE_PYTHON" -I -B "$N055_FEATURE_RECIPE/feature_environment.py" lock \
  "$N055_FEATURE_BUILD/wheelhouse" "$N055_FEATURE_BUILD/wheel-lock.json" \
  "$N055_FEATURE_BUILD/requirements.lock"
```

The direct URLs and full SHA-256 values come from complete primary release/index
metadata captured in a separately selected metadata-only phase. This author
read those captures; no wheel payload was accessed or downloaded. The earlier
capped Pillow response remains partial and is not used as complete metadata;
the separately selected complete response supplies its wheel identity.
`WHEEL_ARTIFACTS.json` contains all eight selected identities. Six PyPI records
also advertise byte counts; the two CPU index links do not, so their future
actual complete byte counts remain unobserved.

The locker requires actual complete local wheel bytes to match the preselected
filenames, versions, SHA-256 values and any advertised byte counts. It captures
actual Requires-Dist/Requires-Python metadata and produces a complete hash-locked
offline installation. The CPU wheel dependency metadata has **not** been read:
its complete dependency compatibility must be confirmed from the actual pinned
wheels and the offline `pip check`; an index link alone does not establish it.
An eight-wheel directory with a wrong hash/version, extra member, missing binary
or unsupported ABI fails. No source distribution or alternate version is selected
automatically. `requirements-torch.txt` and `requirements-support.txt` remain
human-readable version declarations, not the acquisition authority.

Select a real immutable `python:3.9.18-bullseye@sha256:<64 lowercase hex>`
Linux-amd64 base, retain its actual platform identity and terms, and acquire it
within the selected provisioning scope before building. No base digest is
invented or tag-only default supplied. The fixed base is an external artifact
operand; source-only authoring cannot certify its presence.

```sh
docker image inspect "$N055_FEATURE_BASE"
docker build --platform linux/amd64 --network none --pull=false \
  --build-arg "BASE_IMAGE=$N055_FEATURE_BASE" \
  --iidfile "$N055_FEATURE_BUILD/image-id.txt" "$N055_FEATURE_BUILD"
```

The Dockerfile reauthenticates every wheel and installs offline with
`--require-hashes`, followed by `pip check`. Build RUN instructions have no
network. Select a bounded build owner separately; these commands do not
implement a build supervisor or report whole-machine resource usage. Record
the actual resulting image ID independently. The image contains neither neural
data nor scientific source, checkpoint weights or stimulus images.

## Future inspection and actual entrypoint

Inside that exact image, use the real ordinary executable
`/usr/local/bin/python3.9`, not its `python` symlink. A separately selected,
bounded inspection container should use no network, read-only root, no added
capabilities, a fresh writable metadata output directory and externally selected
memory/CPU/process limits. Its command is:

```sh
/usr/local/bin/python3.9 -I -B /opt/n055/feature_environment.py inspect \
  /out/feature-environment-observation.json \
  --memory-bytes "$N055_FEATURE_MEMORY_BYTES" \
  --maximum-image-bytes "$N055_FEATURE_IMAGE_BYTES" \
  --maximum-image-pixels "$N055_FEATURE_IMAGE_PIXELS"
```

Inspection imports the fixed libraries but never constructs AlexNet, loads a
checkpoint, decodes an image or performs a model forward. It records complete
installed distribution hashes, the actual interpreter and required API
signatures. Its `environment` member has exactly the ten fields accepted by
`features.validate_plan`. `network_isolated: true` is the required prospective
plan declaration, expressly **not** an attestation from this helper. Independent
runtime qualification must establish the actual offline/native deployment and
bind the complete source, input descriptors, recipe, environment and limits.
This tool does not generate a signing key, signature or positive qualification.

After the bootstrap compatibility companion, actual provisioning and genuine
runtime qualification are selected and verified, the existing invocation is:

```sh
"$N055_FEATURE_PYTHON" -I -B "$N055_FEATURE_SOURCE/central_entry.py" prepare-features \
  --source-root "$N055_FEATURE_SOURCE" \
  --source-manifest "$N055_FEATURE_SOURCE/RUNTIME_SOURCE_MANIFEST.json" \
  --manifest-bytes "$N055_FEATURE_SOURCE_BYTES" \
  --manifest-sha256 "$N055_FEATURE_SOURCE_SHA256" \
  --plan "$N055_FEATURE_PLAN" --plan-bytes "$N055_FEATURE_PLAN_BYTES" \
  --plan-sha256 "$N055_FEATURE_PLAN_SHA256" \
  --operator-root "$N055_FEATURE_OPERATOR_ROOT" --output "$N055_FEATURE_OUTPUT"
```

Every path is absolute. `N055_FEATURE_SOURCE_BYTES/SHA256` describe the **whole
current runtime manifest**, including any independently accepted bootstrap
companion. The scientific producer body must remain the exact source pin above.
`--output` is fresh and inside the operator namespace. The actual plan requires
the existing schema/task/source_manifest/limits/trust/checkpoint/image_metadata/
image_index/image_root/environment/runtime_qualification/closure_reserve_seconds
fields; its descriptors and independent evidence are actual external operands.
No example receipt or default data descriptor is supplied as authority.

## Required scientific assets and unchanged result interface

Both upstream ordinary-source identities in the existing recipe are now joined
to complete captured bodies: [the original extractor at its fixed commit](https://github.com/gifale95/eeg_encoding/blob/101997d4f14c41b615bcaf8c0907740106d260c5/03_dnn_feature_maps_extraction/extract_feature_maps_alexnet.py)
is 4,530 bytes, SHA-256
`8dcb281793e567e53ec891ae27ef13b0c0a7c60d4c46e6569a17156901eceaef`;
[official torchvision 0.11.2 AlexNet](https://github.com/pytorch/vision/blob/v0.11.2/torchvision/models/alexnet.py)
is 2,283 bytes, SHA-256
`4d878918c40544618f613fba5c2d2484b6659b58f7308b3d198cbdda78efad56`.
The former names ReLU7 and its preprocessing; the latter fixes its 4,096-unit
architecture and conditional pretrained downloader. These matches establish
source identity, not empirical CPU/GPU parity or a checkpoint identity.

The exact checkpoint must already exist locally, have a full byte count/SHA-256
and be at most 512 MiB. The producer calls
`alexnet(pretrained=False, progress=False)` and strictly loads that captured
state dictionary on CPU. It never downloads pretrained weights. A URL filename
hash prefix is not a full checkpoint hash; this source phase has not observed
checkpoint bytes, a complete publisher hash or its provenance-equivalence.

The image metadata fixes 16,540 training images (1,654 concepts × ten exemplars)
and 200 disjoint assessment images/concepts. The image index requires every
ordered original ID and complete file descriptor, with no duplicate paths across
partitions. No image body, archive member, EEG header, target or historical
intake evidence was inspected in this authoring task. Image acquisition and
event/image joins remain separately qualified external inputs.

The preserved transform is RGB, Resize((224,224)), ToTensor and original ImageNet
mean/std, then AlexNet features, adaptive 6×6 pooling, flattening and classifier
modules 0 through 5 inclusive. It processes one image per forward and writes
little-endian float32 matrices of shape 16,540×4,096 and 200×4,096, with the
unchanged strict feature manifest for the original builders. No PCA, fitting on
EEG, layer substitution or classifier-output substitution is introduced.
Require the complete original terminal and output identities, not only the
presence of a feature-manifest file. No such output was produced here.

## Bounds, custody and rights

The helper bounds explicit wheel/package/executable hashing to 2 GiB per step,
1 GiB per file, 30,000 installed members and 8 MiB per JSON output. These are
future managed-body limits, not measurements of imports, native memory,
package-manager work, image building or OS I/O. Trusted immutable provisioning
inputs are required. Output files are exclusive; if the second lock output
fails, preserve the first and the original failure rather than overwrite/retry.

Preserve actual Python/base-image, torch/torchvision, dependency, checkpoint and
stimulus license notices and attribution when separately provisioning or
redistributing those artifacts. The benchmark software license does not grant
rights to weights or images. This package ships source recipes only. Current
missing primary weight/base and CPU-wheel dependency metadata is itemized in
`SOURCE_AND_ARTIFACT_BINDINGS.json`; no empty pin is represented as verified.


The source successor preserves body-first failures when closing output files and source handles; raw close exceptions are attached to the original error. Wheel hashing and ZIP metadata now use one held ordinary file handle, with descriptor and pathname identity checked before and after metadata extraction.

The 2 GiB total bounds explicit streaming hashes, with one possible growth-detection byte per failed file; it is not a whole-process I/O or memory limit. ZipFile reads and allocates its central directory before the 30,000-member check. Metadata decoding adds up to 256 KiB per wheel, and ZIP metadata/internal reads are additional, unmetered here. Provisioning must run within its separately selected process/resource envelope. This source review does not turn those costs into measured zeroes.
