# PFC clean runtime source delivery

This package supplies the exact eleven-file clean build context used to construct the locally admitted Linux ARM64 science runtime. It also records all seventeen wheel URLs, lengths and hashes, the immutable official Python base, and the existing public Full99 inputs. It contains no wheels, image layers, scientific data, credentials or numerical answers.

The recorded local image is `sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff`. Its historical build, installed inventory and small ABI checks were accepted. A downloadable immutable distribution of this image is not supplied here. The original Full99 image `385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156` and its validated public task remain unchanged.

## Reconstruct the pinned dependency stack

Use `DELIVERY_MANIFEST.json` and its externally supplied digest to authenticate every ordinary source member before executing a verifier. The unchanged `context/SOURCE_LOCK.json` then authenticates the exact build-context sources and wheel descriptors. Its prospective status fields describe the original source stage; later accepted construction does not rewrite those historical bytes.

1. On a separately admitted Linux ARM64 Docker target, obtain the seventeen exact wheels in `ARTIFACTS.json` into a new `context/wheels/` directory. Their total is 84,435,444 bytes. Use the listed HTTPS URLs, sizes and SHA-256 values; do not re-resolve dependencies, substitute platform wheels or add other files.
2. Obtain the exact base platform manifest `docker.io/library/python@sha256:608e6ed31df49009fa6c242fb61b5386a1c002e40c2b9cb1958e0f1041aaf06a`. Its four compressed layers total 44,933,770 bytes; their complete ordered descriptors are in `ARTIFACTS.json`. Admit the exact base config `70a416d0c62354c379ea7f473f5affd19f23c917adeb3a9c9b7ce39e6f97f3c9`, architecture and layer chain on that target, under a fresh local tag.
3. With the complete wheel set present, run the unchanged verifier from this package:

```sh
python3 -I -S -B context/verify_artifacts.py --root context/wheels --lock context/WHEELS.json
```

It requires the exact complete directory, ordinary single-link files, stable full hashes and the whole byte sum. It downloads and imports no packages.

4. The recorded build used Docker/Engine 28.3.2, Buildx 0.29.1, BuildKit 0.23.2 and the existing default Docker driver. The following is its build argument structure, with absolute paths and fresh admitted tags supplied by the operator:

```sh
PFC_CONTEXT=/absolute/path/to/context
PFC_BASE_TAG=neuro-shared-base:owned-REPLACE_WITH_FRESH_20_HEX
PFC_OUTPUT_TAG=neuro-shared-science:owned-REPLACE_WITH_FRESH_20_HEX
PFC_BUILD_OUTPUT=/absolute/fresh/build-output
docker buildx build --builder default --platform linux/arm64 \
  --network=none --pull=false --no-cache --load \
  --provenance=false --sbom=false --progress=plain \
  --build-context "python@sha256:608e6ed31df49009fa6c242fb61b5386a1c002e40c2b9cb1958e0f1041aaf06a=docker-image://$PFC_BASE_TAG" \
  --tag "$PFC_OUTPUT_TAG" --iidfile "$PFC_BUILD_OUTPUT/iid.txt" \
  --metadata-file "$PFC_BUILD_OUTPUT/metadata.json" "$PFC_CONTEXT"
```

Before execution, replace both example tag suffixes with fresh values consisting of exactly twenty lowercase hexadecimal characters after owned-. The example strings are valid Docker tag syntax; the raw shell recipe does not enforce the original owner's tag pattern or freshness checks. Create the output directory freshly as well. This is a command recipe, not the original bounded owner or a current execution selection. The original selected owner additionally authenticated the complete archive/context, fresh tag absence, builder/daemon identities, current capacity, natural termination, output configuration/history and all staged files.

The Dockerfile uses hash-required offline installation and preserves all seventeen dependencies. The build network flag isolates RUN commands; it is not a daemon firewall, and an unavailable local base can still cause source-resolution failure or remote lookup. Preserve a failed build rather than substituting a base. A rebuild with identical dependencies is not promised to reproduce the exact historical image ID: timestamps, image construction and tool state remain relevant. Do not change the Full99 image constant to an arbitrary rebuilt ID without a separately reviewed runtime binding and compatibility qualification.

## Resources and validation

The complete source context is 268,162 bytes; with all wheels it is 84,703,606 bytes in 28 files. Base plus wheel compressed payload is 129,369,214 bytes, excluding small registry metadata. Historical decoded base and declared wheel extents are 154,751,488 and 295,910,621 bytes respectively. Those are artifact extents, not free-space, export-size or RAM estimates.

The historical bounded construction booked 8 GiB free disk, 512 MiB host memory, a planned 1 GiB/one-CPU VM slot and a 900-second owner horizon (45 seconds for load and 420 for build). These are historical scheduling bounds, not a new target capacity observation or a portable hard daemon quota. An external target must account for its own build cache, Docker store, output archive and other work.

The unchanged runtime verifier checks CPython 3.12.8 and all locked distribution versions. The recorded later inventory and tiny NumPy/SciPy/h5py/pandas/sklearn ABI checks provide stronger local evidence, but neither source verification nor those tiny checks establish Full99 compatibility on a new image or host.

## Full99 inputs and remaining delivery gaps

The four existing Full99 inputs are publicly available at the [versioned input release](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/pfc-full99-inputs-v1), totaling 5,565,161 bytes. The unchanged `PFC_PUBLIC_INPUTS.json` supplies their complete identities. Follow the task’s [input provisioning](../pfc-conditional-portable-profile-v1/PROVISIONING.md) and [seven-stage operator guide](../pfc-conditional-portable-profile-v1/OPERATOR_GUIDE.md). The released packet is the complete prepared task input; the old private nine-input collection is unnecessary for its owner-local identity descriptor.

Full99 preserves all 99 recordings, 19,186 fitting units, 68 fitting animals and 69 full/deletion cases. Its separately scored PFC population is 10,243 units from 65 animals. It reconstructs conditional statistics of a supplied fixed map, not the broader original learned-map or held-animal prediction question. The new two-constant 9aaf source successor is reviewed, but its full seven-stage compatibility operation remains unrun. Within-runtime candidate/reference agreement would not by itself prove bitwise equality to every historical continuous-geometry result.

An external operator still lacks (a) a distributed immutable copy of the admitted 9aaf image, or a separately qualified rebuild; (b) fresh host/daemon/image/mount admission and full compatibility; and (c) a completed runtime redistribution notice/privacy assessment. `NOTICE_STATUS.json` records a recovered MIT notice at the maintainer's pinned current 0.6.5 source. It is not evidence that the exact installed 0.3.5 wheel/sdist shipped or corresponds to that notice. No blanket prohibition on local research use is inferred.

This source package does not acquire artifacts, build/export an image or run Full99 by itself. Runtime provisioning and qualification remain separate operator steps; the public task’s image binding and historical validation remain unchanged.

